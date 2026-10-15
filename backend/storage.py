"""Stockage objet : conservation précieuse des fichiers audio.

Deux fournisseurs possibles, choisis par les variables d'environnement :
- S3 compatible (Scaleway, Cloudflare R2, Railway Buckets…) dès que
  S3_BUCKET est renseigné ;
- sinon Emergent Object Storage (INTEGRATION_PROXY_URL + EMERGENT_LLM_KEY).

L'application ne contacte jamais le stockage directement ; tout passe par
l'API, qui vérifie l'établissement et les droits avant chaque lecture.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

INTEGRATION_PROXY_URL = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip()
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
STORAGE_BASE = INTEGRATION_PROXY_URL
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage" if STORAGE_BASE else ""
APP_NAME = "racontelle-care"
_storage_key: Optional[str] = None

S3_BUCKET = (os.environ.get("S3_BUCKET") or "").strip()
S3_ENDPOINT = (os.environ.get("S3_ENDPOINT") or "").strip()
S3_REGION = (os.environ.get("S3_REGION") or "").strip() or None
S3_ACCESS_KEY_ID = (os.environ.get("S3_ACCESS_KEY_ID") or "").strip()
S3_SECRET_ACCESS_KEY = (os.environ.get("S3_SECRET_ACCESS_KEY") or "").strip()
_s3_client = None


def _use_s3() -> bool:
    return bool(S3_BUCKET)


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.config import Config

        if not (S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY):
            raise RuntimeError("S3_ACCESS_KEY_ID et S3_SECRET_ACCESS_KEY doivent être configurés avec S3_BUCKET")
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT or None,
            region_name=S3_REGION,
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
        )
    return _s3_client


def storage_ready() -> bool:
    if _use_s3():
        return bool(S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY)
    return bool(STORAGE_BASE and EMERGENT_KEY)


def init_storage() -> str:
    """Initialise une fois la clé de stockage, réutilisable ensuite."""
    global _storage_key
    if _storage_key:
        return _storage_key
    if _use_s3():
        # Vérifie l'accès au bucket dès le démarrage : une mauvaise clé est
        # signalée dans les logs plutôt qu'au premier enregistrement.
        _s3().head_bucket(Bucket=S3_BUCKET)
        _storage_key = f"s3:{S3_BUCKET}"
        return _storage_key
    if not storage_ready():
        raise RuntimeError("INTEGRATION_PROXY_URL et EMERGENT_LLM_KEY doivent être configurés pour le stockage objet")
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    if _use_s3():
        _s3().put_object(Bucket=S3_BUCKET, Key=path, Body=data, ContentType=content_type)
        return {"path": path, "size": len(data)}
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": init_storage(), "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    if _use_s3():
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=path)
        return obj["Body"].read(), obj.get("ContentType") or "application/octet-stream"
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": init_storage()},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def delete_object(path: str) -> bool:
    """Suppression RGPD de l'audio. Si le stockage ne sait pas supprimer, on
    écrase le fichier par un contenu vide : l'audio devient inaccessible dans
    tous les cas (l'API ne le sert plus de toute façon, la fiche est effacée)."""
    if _use_s3():
        try:
            _s3().delete_object(Bucket=S3_BUCKET, Key=path)
            return True
        except Exception as exc:  # noqa: BLE001 - journalisé, la fiche reste supprimée
            logger.warning("suppression audio impossible (%s) : %s", path, exc)
            return False
    try:
        resp = requests.delete(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": init_storage()},
            timeout=60,
        )
        if resp.status_code < 400:
            return True
    except requests.RequestException as exc:
        logger.warning("suppression audio impossible (%s) : %s", path, exc)
    try:
        put_object(path, b"", "application/octet-stream")
        return True
    except Exception as exc:  # noqa: BLE001 - journalisé, la fiche reste supprimée
        logger.warning("effacement audio impossible (%s) : %s", path, exc)
        return False
