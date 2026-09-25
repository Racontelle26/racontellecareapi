"""Emergent Object Storage : conservation précieuse des fichiers audio.

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

STORAGE_BASE = os.environ["INTEGRATION_PROXY_URL"].strip()
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
APP_NAME = "racontelle-care"
_storage_key: Optional[str] = None


def init_storage() -> str:
    """Initialise une fois la clé de stockage, réutilisable ensuite."""
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": init_storage(), "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
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
