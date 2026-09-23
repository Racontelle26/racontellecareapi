from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
from pathlib import Path
from typing import List, Optional
import tempfile
import uuid

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

from security import (
    AuthUser,
    auth_router,
    configure_security,
    consume_quota,
    current_user,
    ensure_security_indexes,
    require_admin,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
configure_security(db)
app = FastAPI(title="Racontelle Care API")
api_router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Emergent Object Storage : conservation précieuse des fichiers audio.
# L'app ne contacte jamais le stockage directement ; tout passe par ici.
# ---------------------------------------------------------------------------
STORAGE_BASE = os.environ["INTEGRATION_PROXY_URL"].strip()
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
APP_NAME = "racontelle-care"
storage_key: Optional[str] = None
MAX_AUDIO_BYTES = 25 * 1024 * 1024


def init_storage() -> str:
    """Initialise une fois la clé de stockage, réutilisable ensuite."""
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


class ResidentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    consent_status: str = "obtained"


class ResidentPatch(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    consent_status: Optional[str] = None
    active: Optional[bool] = None


class ResidentOut(BaseModel):
    id: str
    display_name: str
    consent_status: str
    active: bool
    created_at: str


class QuestionOut(BaseModel):
    id: str
    theme: str
    text: str
    sensitive: bool = False


class CapsuleCreate(BaseModel):
    resident_id: Optional[str] = None
    question_id: Optional[str] = None
    mode: str = "free"
    theme: Optional[str] = None
    title: Optional[str] = None
    duration_sec: int = 0
    recorded_at: str
    audio_uri: Optional[str] = None
    audio_base64: Optional[str] = None


class CapsuleOut(BaseModel):
    id: str
    resident_id: Optional[str] = None
    question_id: Optional[str] = None
    mode: str
    theme: Optional[str] = None
    title: Optional[str] = None
    duration_sec: int
    recorded_at: str
    status: str
    synced: bool = True
    transcription: Optional[str] = None
    share_id: Optional[str] = None
    share_expires_at: Optional[str] = None


QUESTIONS = [
    ("Enfance", "Quel est votre tout premier souvenir ?"),
    ("Enfance", "À quoi ressemblait la maison de votre enfance ?"),
    ("Enfance", "Quel souvenir vous fait encore sourire aujourd’hui ?"),
    ("Famille", "Qui vous faisait le plus rire dans votre famille ?"),
    ("Famille", "Y avait-il une tradition importante chez vous ?"),
    ("Famille", "Quel conseil reçu dans votre famille avez-vous gardé ?"),
    ("École et jeunesse", "Vous souvenez-vous de votre premier jour d’école ?"),
    ("École et jeunesse", "Quel était votre rêve quand vous étiez jeune ?"),
    ("École et jeunesse", "Comment occupiez-vous vos vacances ?"),
    ("Travail", "Quel a été votre premier travail ?"),
    ("Travail", "Quel moment de votre vie professionnelle vous rend fier ?"),
    ("Travail", "Quel conseil donneriez-vous à quelqu’un qui débute aujourd’hui ?"),
    ("Amour et rencontres", "Vous souvenez-vous de votre premier amour ?"),
    ("Amour et rencontres", "Quel beau geste d’amour avez-vous reçu ?"),
    ("Amour et rencontres", "Qu’est-ce qui fait, selon vous, qu’un couple dure ?"),
    ("Cuisine et traditions", "Quel plat vous rappelle le plus votre famille ?"),
    ("Cuisine et traditions", "Quelle recette aimeriez-vous transmettre ?"),
    ("Cuisine et traditions", "Quelle odeur de cuisine vous ramène dans le passé ?"),
    ("Musique et loisirs", "Quelle chanson vous rappelle votre jeunesse ?"),
    ("Musique et loisirs", "Sur quelle musique aimiez-vous danser ?"),
    ("Musique et loisirs", "Quel plaisir simple vous a toujours rendu heureux ?"),
    ("Voyages et lieux", "Quel voyage vous a laissé le plus beau souvenir ?"),
    ("Voyages et lieux", "Quel lieu de votre jeunesse aimeriez-vous revoir ?"),
    ("Voyages et lieux", "À quoi ressemblait votre quartier autrefois ?"),
    ("Moments heureux", "De quoi êtes-vous le plus fier ?"),
    ("Moments heureux", "Quel moment vous a rendu particulièrement heureux ?"),
    ("Moments heureux", "Quel fou rire n’avez-vous jamais oublié ?"),
    ("Transmission", "Quel conseil aimeriez-vous transmettre aux plus jeunes ?"),
    ("Transmission", "Qu’est-ce qui compte vraiment dans la vie selon vous ?"),
    ("Transmission", "Qu’aimeriez-vous que l’on retienne de vous ?"),
]


async def ensure_questions() -> None:
    if await db.questions.count_documents({}):
        return
    await db.questions.insert_many([
        {"id": str(uuid.uuid4()), "theme": theme, "text": text, "sensitive": False, "created_at": now_iso()}
        for theme, text in QUESTIONS
    ])


@app.on_event("startup")
async def startup_seed() -> None:
    await ensure_security_indexes()
    await ensure_questions()
    try:
        await run_in_threadpool(init_storage)
    except Exception as exc:
        logger.warning("stockage objet indisponible au démarrage : %s", exc)


@api_router.get("/")
async def root():
    return {"message": "Racontelle Care API", "offline_first": True}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate, user: AuthUser = Depends(current_user)):
    status_obj = StatusCheck(**input.model_dump())
    await db.status_checks.insert_one({**status_obj.model_dump(), "tenant_id": user.tenant_id})
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks(user: AuthUser = Depends(current_user)):
    docs = await db.status_checks.find({"tenant_id": user.tenant_id}, {"_id": 0}).to_list(1000)
    return [StatusCheck(**doc) for doc in docs]


@api_router.get("/residents", response_model=List[ResidentOut])
async def get_residents(user: AuthUser = Depends(current_user)):
    return await db.residents.find(
        {"tenant_id": user.tenant_id, "active": True}, {"_id": 0}
    ).sort("created_at", 1).to_list(10)


@api_router.post("/residents", response_model=ResidentOut, status_code=201)
async def create_resident(input: ResidentCreate, user: AuthUser = Depends(current_user)):
    if await db.residents.count_documents({"tenant_id": user.tenant_id, "active": True}) >= 10:
        raise HTTPException(status_code=400, detail="Limite de 10 profils atteinte")
    resident = {
        "id": str(uuid.uuid4()),
        "display_name": input.display_name.strip(),
        "consent_status": input.consent_status,
        "active": True,
        "created_at": now_iso(),
        "tenant_id": user.tenant_id,
        "created_by": user.id,
    }
    await db.residents.insert_one(resident)
    return resident


@api_router.patch("/residents/{resident_id}", response_model=ResidentOut)
async def update_resident(
    resident_id: str, input: ResidentPatch, user: AuthUser = Depends(current_user)
):
    changes = input.model_dump(exclude_none=True)
    if "display_name" in changes:
        changes["display_name"] = changes["display_name"].strip()
    doc = await db.residents.find_one_and_update(
        {"id": resident_id, "tenant_id": user.tenant_id},
        {"$set": changes},
        return_document=True,
        projection={"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    return doc


@api_router.get("/questions", response_model=List[QuestionOut])
async def get_questions(
    theme: Optional[str] = Query(default=None),
    limit: int = Query(default=30, le=100),
    user: AuthUser = Depends(current_user),
):
    query = {"sensitive": False}
    if theme and theme != "Tous":
        query["theme"] = theme
    return await db.questions.find(query, {"_id": 0}).limit(limit).to_list(limit)


@api_router.post("/capsules", response_model=CapsuleOut, status_code=201)
async def create_capsule(input: CapsuleCreate, user: AuthUser = Depends(current_user)):
    if input.resident_id:
        resident = await db.residents.find_one(
            {"id": input.resident_id, "tenant_id": user.tenant_id}, {"_id": 0}
        )
        if not resident:
            raise HTTPException(status_code=404, detail="Profil introuvable")
        if resident.get("consent_status") != "obtained":
            raise HTTPException(status_code=403, detail="Consentement requis")
    capsule = {
        "id": str(uuid.uuid4()),
        **input.model_dump(),
        "status": "assigned" if input.resident_id else "unclassified",
        "synced": True,
        "created_at": now_iso(),
        "tenant_id": user.tenant_id,
        "created_by": user.id,
    }
    await db.capsules.insert_one(capsule)
    capsule.pop("_id", None)
    capsule.pop("audio_uri", None)
    capsule.pop("audio_base64", None)
    return capsule


@api_router.get("/capsules", response_model=List[CapsuleOut])
async def get_capsules(user: AuthUser = Depends(current_user)):
    capsules = await db.capsules.find(
        {"tenant_id": user.tenant_id}, {"_id": 0, "audio_base64": 0, "audio_uri": 0}
    ).sort("recorded_at", -1).to_list(1000)
    return await attach_active_shares(capsules, user.tenant_id)


async def attach_active_shares(capsules: list[dict], tenant_id: str) -> list[dict]:
    capsule_ids = [capsule["id"] for capsule in capsules]
    if not capsule_ids:
        return capsules
    shares = await db.share_tokens.find(
        {
            "tenant_id": tenant_id,
            "capsule_id": {"$in": capsule_ids},
            "revoked_at": None,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        },
        {"_id": 0, "id": 1, "capsule_id": 1, "expires_at": 1},
    ).sort("created_at", -1).to_list(1000)
    by_capsule = {}
    for share in shares:
        by_capsule.setdefault(share["capsule_id"], share)
    for capsule in capsules:
        share = by_capsule.get(capsule["id"])
        if share:
            capsule["share_id"] = share["id"]
            capsule["share_expires_at"] = share["expires_at"].isoformat()
    return capsules


@api_router.get("/residents/{resident_id}/capsules", response_model=List[CapsuleOut])
async def get_resident_capsules(resident_id: str, user: AuthUser = Depends(current_user)):
    if not await db.residents.find_one(
        {"id": resident_id, "tenant_id": user.tenant_id}, {"_id": 0, "id": 1}
    ):
        raise HTTPException(status_code=404, detail="Profil introuvable")
    capsules = await db.capsules.find(
        {"resident_id": resident_id, "tenant_id": user.tenant_id},
        {"_id": 0, "audio_base64": 0, "audio_uri": 0},
    ).sort("recorded_at", -1).to_list(1000)
    return await attach_active_shares(capsules, user.tenant_id)


@api_router.get("/capsules/unclassified", response_model=List[CapsuleOut])
async def get_unclassified_capsules(user: AuthUser = Depends(current_user)):
    return await db.capsules.find(
        {"status": "unclassified", "tenant_id": user.tenant_id},
        {"_id": 0, "audio_base64": 0, "audio_uri": 0},
    ).sort("recorded_at", -1).to_list(1000)


class CapsulePatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@api_router.patch("/capsules/{capsule_id}", response_model=CapsuleOut)
async def update_capsule(
    capsule_id: str, input: CapsulePatch, user: AuthUser = Depends(current_user)
):
    """Renommage d'un souvenir sur le vif."""
    doc = await db.capsules.find_one_and_update(
        {"id": capsule_id, "tenant_id": user.tenant_id},
        {"$set": {"title": input.title.strip()}},
        return_document=True,
        projection={"_id": 0, "audio_base64": 0, "audio_uri": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    return doc


@api_router.delete("/capsules/{capsule_id}")
async def delete_capsule(capsule_id: str, admin: AuthUser = Depends(require_admin)):
    result = await db.capsules.delete_one({"id": capsule_id, "tenant_id": admin.tenant_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    return {"deleted": True}


@api_router.patch("/capsules/{capsule_id}/assign", response_model=CapsuleOut)
async def assign_capsule(
    capsule_id: str, resident_id: str, user: AuthUser = Depends(current_user)
):
    if not await db.residents.find_one(
        {"id": resident_id, "tenant_id": user.tenant_id}, {"_id": 0}
    ):
        raise HTTPException(status_code=404, detail="Profil introuvable")
    doc = await db.capsules.find_one_and_update(
        {"id": capsule_id, "tenant_id": user.tenant_id},
        {"$set": {"resident_id": resident_id, "status": "assigned", "classified_at": now_iso()}},
        return_document=True,
        projection={"_id": 0, "audio_base64": 0, "audio_uri": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    return doc


async def read_audio_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Fichier audio trop volumineux")
    if not data:
        raise HTTPException(status_code=400, detail="Fichier audio vide")
    return data


@api_router.post("/capsules/{capsule_id}/audio")
async def upload_capsule_audio(
    capsule_id: str,
    file: UploadFile = File(...),
    user: AuthUser = Depends(current_user),
):
    """Conserve précieusement l'audio d'une capsule dans le stockage objet."""
    doc = await db.capsules.find_one(
        {"id": capsule_id, "tenant_id": user.tenant_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    if doc.get("resident_id"):
        resident = await db.residents.find_one(
            {"id": doc["resident_id"], "tenant_id": user.tenant_id}, {"_id": 0}
        )
        if not resident or resident.get("consent_status") != "obtained":
            raise HTTPException(status_code=403, detail="Consentement requis")
    data = await read_audio_upload(file)
    remaining = await consume_quota(user, "upload")
    content_type = (file.content_type or "audio/m4a").lower()
    path = f"{APP_NAME}/{user.tenant_id}/audio/{capsule_id}.m4a"
    try:
        await run_in_threadpool(put_object, path, data, content_type)
    except Exception as exc:
        logger.warning("audio upload failed: %s", exc)
        raise HTTPException(status_code=502, detail="Stockage audio momentanément indisponible")
    await db.capsules.update_one(
        {"id": capsule_id, "tenant_id": user.tenant_id},
        {"$set": {"storage_path": path, "audio_content_type": content_type}},
    )
    return {"uploaded": True, "path": path, "remaining": remaining}


@api_router.post("/capsules/{capsule_id}/transcribe")
async def transcribe_capsule(
    capsule_id: str,
    file: UploadFile = File(...),
    user: AuthUser = Depends(current_user),
):
    doc = await db.capsules.find_one(
        {"id": capsule_id, "tenant_id": user.tenant_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    if doc.get("transcription"):
        return {"transcription": doc["transcription"]}
    if doc.get("resident_id"):
        resident = await db.residents.find_one(
            {"id": doc["resident_id"], "tenant_id": user.tenant_id}, {"_id": 0}
        )
        if not resident or resident.get("consent_status") != "obtained":
            raise HTTPException(status_code=403, detail="Consentement requis")
    data = await read_audio_upload(file)
    await consume_quota(user, "stt")
    from emergentintegrations.llm.openai.speech_to_text import OpenAISpeechToText

    suffix = ".webm" if "webm" in (file.content_type or "") else ".m4a"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        stt = OpenAISpeechToText(api_key=EMERGENT_KEY)
        # litellm attend un objet fichier (pas un chemin) pour l'upload.
        with open(tmp_path, "rb") as audio_file:
            result = await stt.transcribe(
                file=audio_file,
                model="whisper-1",
                response_format="json",
                language="fr",
                prompt="Souvenir raconté en français par une personne âgée pendant un atelier mémoire en EHPAD.",
            )
        text = (getattr(result, "text", None) or str(result)).strip()
    except Exception as exc:
        logger.warning("transcription failed: %s", exc)
        raise HTTPException(status_code=502, detail="Transcription momentanément indisponible")
    finally:
        os.unlink(tmp_path)
    await db.capsules.update_one(
        {"id": capsule_id, "tenant_id": user.tenant_id},
        {"$set": {"transcription": text, "transcribed_at": now_iso()}},
    )
    return {"transcription": text}


@api_router.post("/capsules/{capsule_id}/share")
async def share_capsule(capsule_id: str, user: AuthUser = Depends(current_user)):
    doc = await db.capsules.find_one(
        {"id": capsule_id, "tenant_id": user.tenant_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    if not doc.get("storage_path"):
        raise HTTPException(status_code=400, detail="Audio pas encore conservé sur le serveur")
    token = uuid.uuid4().hex + uuid.uuid4().hex
    share_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    await db.share_tokens.update_many(
        {
            "capsule_id": capsule_id,
            "tenant_id": user.tenant_id,
            "revoked_at": None,
        },
        {"$set": {"revoked_at": datetime.now(timezone.utc), "revoked_by": user.id}},
    )
    await db.share_tokens.insert_one(
        {
            "id": share_id,
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": user.tenant_id,
            "capsule_id": capsule_id,
            "created_by": user.id,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "revoked_at": None,
        }
    )
    return {
        "token": token,
        "share_id": share_id,
        "path": f"/api/share/{token}",
        "expires_at": expires_at.isoformat(),
    }


@api_router.get("/capsules/{capsule_id}/shares")
async def list_capsule_shares(capsule_id: str, admin: AuthUser = Depends(require_admin)):
    if not await db.capsules.find_one(
        {"id": capsule_id, "tenant_id": admin.tenant_id}, {"_id": 0, "id": 1}
    ):
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    docs = await db.share_tokens.find(
        {
            "capsule_id": capsule_id,
            "tenant_id": admin.tenant_id,
            "revoked_at": None,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        },
        {"_id": 0, "token_hash": 0},
    ).to_list(100)
    for doc in docs:
        for key in ("created_at", "expires_at"):
            if isinstance(doc.get(key), datetime):
                doc[key] = doc[key].isoformat()
    return docs


@api_router.delete("/shares/{share_id}")
async def revoke_share(share_id: str, admin: AuthUser = Depends(require_admin)):
    result = await db.share_tokens.update_one(
        {"id": share_id, "tenant_id": admin.tenant_id, "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(timezone.utc), "revoked_by": admin.id}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Lien introuvable")
    return {"revoked": True}


import html as _html

SHARE_PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Un souvenir partagé — Racontelle Care</title>
<style>
  body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; background:#FFFFFF; color:#2F3E52; }}
  main {{ max-width: 560px; margin: 0 auto; padding: 48px 24px 64px; }}
  .brand {{ font-style: italic; color:#A65F5B; font-size: 30px; margin-bottom: 4px; }}
  .tagline {{ color:#7C8698; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; }}
  h1 {{ font-size: 26px; font-weight: 600; margin: 24px 0 4px; }}
  .meta {{ color:#7C8698; font-size: 14px; margin-bottom: 24px; }}
  .card {{ background:#F7F3EE; border:1px solid #E9E1D7; border-radius:20px; padding:24px; }}
  audio {{ width:100%; }}
  blockquote {{ font-size:19px; line-height:1.55; margin:24px 0 0; padding-left:16px; border-left:3px solid #E7A7A5; }}
  .footer {{ margin-top:32px; font-size:13px; color:#7C8698; }}
</style></head>
<body><main>
  <div class="brand">Racontelle Care</div>
  <div class="tagline">Écouter · Préserver · Transmettre</div>
  <h1>{title}</h1>
  <div class="meta">{subtitle}</div>
  <div class="card">
    <audio controls src="/api/share/{token}/audio">Votre navigateur ne lit pas cet audio.</audio>
    {transcription_block}
  </div>
  <p class="footer">Ce lien privé a été créé pendant un atelier mémoire. Merci de préserver sa confidentialité.</p>
</main></body></html>"""


@api_router.get("/share/{token}", response_class=HTMLResponse)
async def share_page(token: str):
    share = await db.share_tokens.find_one(
        {
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "revoked_at": None,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        },
        {"_id": 0},
    )
    if not share:
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré")
    doc = await db.capsules.find_one(
        {"id": share["capsule_id"], "tenant_id": share["tenant_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    resident = None
    if doc.get("resident_id"):
        resident = await db.residents.find_one(
            {"id": doc["resident_id"], "tenant_id": share["tenant_id"]}, {"_id": 0}
        )
    title = _html.escape(doc.get("title") or "Souvenir vocal")
    who = f"raconté par {resident['display_name']}" if resident else "souvenir de l'atelier mémoire"
    date_label = datetime.fromisoformat(doc["recorded_at"].replace("Z", "+00:00")).strftime("%d/%m/%Y")
    transcription_block = f"<blockquote>{_html.escape(doc['transcription'])}</blockquote>" if doc.get("transcription") else ""
    return SHARE_PAGE.format(
        title=title,
        subtitle=f"{_html.escape(who)} · {date_label}",
        token=token,
        transcription_block=transcription_block,
    )


@api_router.get("/share/{token}/audio")
async def share_audio(token: str):
    share = await db.share_tokens.find_one(
        {
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "revoked_at": None,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        },
        {"_id": 0},
    )
    if not share:
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré")
    doc = await db.capsules.find_one(
        {"id": share["capsule_id"], "tenant_id": share["tenant_id"]}, {"_id": 0}
    )
    if not doc or not doc.get("storage_path"):
        raise HTTPException(status_code=404, detail="Audio introuvable")
    try:
        data, content_type = await run_in_threadpool(get_object, doc["storage_path"])
    except Exception:
        raise HTTPException(status_code=404, detail="Audio introuvable")
    return Response(content=data, media_type=content_type)


import io
import re
import zipfile


@api_router.get("/residents/{resident_id}/export")
async def export_resident(resident_id: str, admin: AuthUser = Depends(require_admin)):
    """Export équipe soignante : un ZIP regroupant les audios conservés et les
    transcriptions du résident, pour les transmissions du service."""
    resident = await db.residents.find_one(
        {"id": resident_id, "tenant_id": admin.tenant_id}, {"_id": 0}
    )
    if not resident:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    capsules = await db.capsules.find(
        {"resident_id": resident_id, "tenant_id": admin.tenant_id}, {"_id": 0}
    ).sort("recorded_at", 1).to_list(1000)
    buffer = io.BytesIO()
    lines = [
        f"Souvenirs de {resident['display_name']}",
        f"Export réalisé le {datetime.now(timezone.utc).strftime('%d/%m/%Y')}",
        "",
    ]
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, capsule in enumerate(capsules, start=1):
            date_label = str(capsule.get("recorded_at", ""))[:10]
            title = capsule.get("title") or "Souvenir vocal"
            lines.append(f"{index}. {date_label} — {title} ({capsule.get('duration_sec', 0)} s)")
            if capsule.get("transcription"):
                lines.append(f"   Transcription : {capsule['transcription']}")
            if capsule.get("storage_path"):
                filename = f"audio/{index:02d}-{date_label}.m4a"
                try:
                    data, _ = await run_in_threadpool(get_object, capsule["storage_path"])
                    archive.writestr(filename, data)
                    lines.append(f"   Fichier : {filename}")
                except Exception:
                    lines.append("   Fichier : non synchronisé sur le serveur")
            else:
                lines.append("   Fichier : conservé sur l'appareil uniquement")
            lines.append("")
        archive.writestr("souvenirs.txt", "\n".join(lines))
    safe_name = re.sub(r"[^a-z0-9]+", "-", resident["display_name"].lower()).strip("-") or "resident"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="racontelle-{safe_name}.zip"'},
    )


@api_router.delete("/residents/{resident_id}")
async def delete_resident(resident_id: str, admin: AuthUser = Depends(require_admin)):
    """Retrait du profil (départ de l'établissement). Suppression douce : les
    capsules restent conservées côté serveur, le profil est désactivé."""
    result = await db.residents.update_one(
        {"id": resident_id, "tenant_id": admin.tenant_id},
        {"$set": {"active": False, "removed_at": now_iso(), "removed_by": admin.id}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    return {"deleted": True}


class MergeRequest(BaseModel):
    keep_id: str
    merge_ids: List[str]


@api_router.post("/residents/merge")
async def merge_residents(input: MergeRequest, admin: AuthUser = Depends(require_admin)):
    """Fusionne des profils en doublon : les souvenirs des fiches fusionnées
    sont rattachés à la fiche conservée, les doublons sont désactivés."""
    keep = await db.residents.find_one(
        {"id": input.keep_id, "tenant_id": admin.tenant_id, "active": True}, {"_id": 0}
    )
    if not keep:
        raise HTTPException(status_code=404, detail="Fiche à conserver introuvable")
    merge_ids = [mid for mid in input.merge_ids if mid != input.keep_id]
    if not merge_ids:
        raise HTTPException(status_code=400, detail="Aucun doublon à fusionner")
    merge_count = await db.residents.count_documents(
        {"id": {"$in": merge_ids}, "tenant_id": admin.tenant_id, "active": True}
    )
    if merge_count != len(set(merge_ids)):
        raise HTTPException(status_code=404, detail="Un profil à fusionner est introuvable")
    await db.capsules.update_many(
        {"resident_id": {"$in": merge_ids}, "tenant_id": admin.tenant_id},
        {"$set": {"resident_id": input.keep_id}},
    )
    await db.residents.update_many(
        {"id": {"$in": merge_ids}, "tenant_id": admin.tenant_id},
        {
            "$set": {
                "active": False,
                "merged_into": input.keep_id,
                "removed_at": now_iso(),
                "removed_by": admin.id,
            }
        },
    )
    return {"merged": merge_count}


def _register_pdf_fonts():
    """Polices de la charte Racontelle Care, avec repli sur les polices intégrées."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts_dir = Path(__file__).parent.parent / "frontend" / "assets" / "fonts"
    pairs = {
        "Allura": ("Allura-Regular.ttf", "Times-Italic"),
        "Cormorant": ("CormorantGaramond-Regular.ttf", "Times-Roman"),
        "Cormorant-SemiBold": ("CormorantGaramond-SemiBold.ttf", "Times-Bold"),
        "Montserrat": ("Montserrat-Bold.ttf", "Helvetica-Bold"),
    }
    resolved = {}
    for name, (file_name, fallback) in pairs.items():
        try:
            pdfmetrics.registerFont(TTFont(name, str(fonts_dir / file_name)))
            resolved[name] = name
        except Exception:
            resolved[name] = fallback
    return resolved


@api_router.get("/residents/{resident_id}/carnet")
async def carnet_pdf(resident_id: str, admin: AuthUser = Depends(require_admin)):
    """Impression du carnet : un PDF élégant des transcriptions du résident,
    prêt à offrir à la famille."""
    resident = await db.residents.find_one(
        {"id": resident_id, "tenant_id": admin.tenant_id}, {"_id": 0}
    )
    if not resident:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    capsules = await db.capsules.find(
        {"resident_id": resident_id, "tenant_id": admin.tenant_id}, {"_id": 0}
    ).sort("recorded_at", 1).to_list(1000)

    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen import canvas

    fonts = _register_pdf_fonts()
    ink = HexColor("#2F3E52")
    rose = HexColor("#E7A7A5")
    dark_rose = HexColor("#A65F5B")
    brown = HexColor("#A67C63")
    muted = HexColor("#7C8698")
    paper = HexColor("#F7F3EE")

    def wrap(text: str, font: str, size: float, max_width: float):
        lines, line = [], ""
        for word in text.split():
            trial = (line + " " + word).strip()
            if pdfmetrics.stringWidth(trial, font, size) <= max_width:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines or [""]

    def draw() -> bytes:
        buffer = io.BytesIO()
        page = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        margin = 22 * mm
        max_w = width - 2 * margin

        def footer():
            page.setFont(fonts["Montserrat"], 8)
            page.setFillColor(muted)
            page.drawCentredString(width / 2, 12 * mm, "Écouter · Préserver · Transmettre — Racontelle Care")

        def new_page():
            footer()
            page.showPage()

        # En-tête du carnet
        y = height - 30 * mm
        page.setFont(fonts["Allura"], 42)
        page.setFillColor(dark_rose)
        page.drawString(margin, y, "Racontelle Care")
        y -= 9 * mm
        page.setFont(fonts["Montserrat"], 8)
        page.setFillColor(muted)
        page.drawString(margin, y, "ÉCOUTER · PRÉSERVER · TRANSMETTRE")
        y -= 4 * mm
        page.setStrokeColor(rose)
        page.setLineWidth(1.2)
        page.line(margin, y, width - margin, y)
        y -= 14 * mm
        page.setFont(fonts["Cormorant-SemiBold"], 26)
        page.setFillColor(ink)
        page.drawString(margin, y, f"Le carnet de {resident['display_name']}")
        y -= 8 * mm
        page.setFont(fonts["Cormorant"], 12)
        page.setFillColor(muted)
        page.drawString(margin, y, f"Souvenirs racontés à voix haute · édité le {datetime.now(timezone.utc).strftime('%d/%m/%Y')}")
        y -= 14 * mm

        if not capsules:
            page.setFont(fonts["Cormorant"], 13)
            page.setFillColor(ink)
            page.drawString(margin, y, "Aucun souvenir transcrit pour le moment.")

        for index, capsule in enumerate(capsules, start=1):
            transcription = (capsule.get("transcription") or "").strip()
            title = capsule.get("title") or "Souvenir vocal"
            date_label = str(capsule.get("recorded_at", ""))[:10]
            duration = capsule.get("duration_sec", 0)
            lines = wrap(f"« {transcription} »" if transcription else "(enregistrement non transcrit)", fonts["Cormorant"], 12.5, max_w - 8 * mm)
            needed = 10 * mm + 8 * mm + len(wrap(title, fonts["Cormorant-SemiBold"], 14, max_w - 8 * mm)) * 6 * mm + len(lines) * 5.6 * mm + 10 * mm
            if y - needed < 20 * mm:
                new_page()
                y = height - 24 * mm
            # Carte souvenir
            card_top = y
            page.setFont(fonts["Montserrat"], 8.5)
            page.setFillColor(brown)
            page.drawString(margin + 6 * mm, y - 7 * mm, f"{index}. {date_label} · {duration // 60:02d}:{duration % 60:02d}")
            y -= 14 * mm
            page.setFont(fonts["Cormorant-SemiBold"], 14)
            page.setFillColor(ink)
            for tline in wrap(title, fonts["Cormorant-SemiBold"], 14, max_w - 12 * mm):
                page.drawString(margin + 6 * mm, y, tline)
                y -= 6 * mm
            y -= 1.5 * mm
            page.setStrokeColor(rose)
            page.setLineWidth(2)
            page.line(margin + 6 * mm, y + 3 * mm, margin + 6 * mm, y - len(lines) * 5.6 * mm + 1.5 * mm)
            page.setFont(fonts["Cormorant"], 12.5)
            page.setFillColor(ink)
            for tline in lines:
                page.drawString(margin + 10 * mm, y, tline)
                y -= 5.6 * mm
            y -= 3 * mm
            y -= 6 * mm

        footer()
        page.save()
        return buffer.getvalue()

    pdf_bytes = await run_in_threadpool(draw)
    safe_name = re.sub(r"[^a-z0-9]+", "-", resident["display_name"].lower()).strip("-") or "resident"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="racontelle-carnet-{safe_name}.pdf"'},
    )


class TtsRequest(BaseModel):
    text: str = Field(max_length=4000)


@api_router.post("/tts")
async def text_to_speech(input: TtsRequest, user: AuthUser = Depends(current_user)):
    """Lecture vocale (TTS) : questions et transcriptions lues à voix haute.
    Voix « coral », débit posé pour un public senior. Audio mis en cache dans
    le stockage objet (clé = hash texte+voix+modèle+format)."""
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    text = re.sub(r"https?://\S+", "", input.text)
    text = re.sub(r"[*_#>~|`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texte vide")
    await consume_quota(user, "tts")
    key = hashlib.sha256(f"{text}|coral|0.95|tts-1|mp3".encode()).hexdigest()
    doc = await db.tts_cache.find_one({"key": key}, {"_id": 0})
    if not doc:
        try:
            tts = OpenAITextToSpeech(api_key=EMERGENT_KEY)
            audio = await tts.generate_speech(
                text=text, model="tts-1", voice="coral", speed=0.95, response_format="mp3"
            )
        except Exception as exc:
            logger.warning("tts failed: %s", exc)
            raise HTTPException(status_code=502, detail="Lecture vocale momentanément indisponible")
        path = f"{APP_NAME}/tts/{key}.mp3"
        try:
            await run_in_threadpool(put_object, path, audio, "audio/mpeg")
        except Exception as exc:
            logger.warning("tts storage failed: %s", exc)
            raise HTTPException(status_code=502, detail="Stockage audio momentanément indisponible")
        await db.tts_cache.insert_one({"key": key, "path": path, "created_at": now_iso()})
    return {"path": f"/api/tts/{key}.mp3"}


@api_router.get("/tts/{key}.mp3")
async def get_tts(key: str, user: AuthUser = Depends(current_user)):
    doc = await db.tts_cache.find_one({"key": key}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Audio introuvable")
    try:
        data, _ = await run_in_threadpool(get_object, doc["path"])
    except Exception:
        raise HTTPException(status_code=404, detail="Audio introuvable")
    return Response(
        content=data,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=31536000"},
    )


app.include_router(auth_router)
app.include_router(api_router)
cors_origins = [
    origin.strip()
    for origin in os.environ["CORS_ORIGINS"].split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Client-Platform"],
    max_age=600,
)


@app.middleware("http")
async def normalize_proxy_cors_origin(request, call_next):
    """Le proxy preview remplace l'Origin public par son domaine interne.
    On conserve une allowlist exacte côté API puis on restitue l'origine que le
    navigateur connaît, sans jamais autoriser une origine inconnue.
    """
    response = await call_next(request)
    proxy_origin = os.environ.get("CORS_PROXY_ORIGIN", "")
    public_origin = os.environ.get("CORS_PUBLIC_ORIGIN", "")
    if (
        request.headers.get("origin") == proxy_origin
        and response.headers.get("access-control-allow-origin") == proxy_origin
        and public_origin
    ):
        response.headers["access-control-allow-origin"] = public_origin
    return response

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()