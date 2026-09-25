"""API Racontelle Care — bêta établissement.

Modules :
- security.py : comptes, sessions, rôles, quotas, récupération du mot de passe
- beta.py     : interrupteurs de fonctions, journal d'audit, retours, indicateurs
- quiz.py     : module d'animation « Qui a dit ça ? »
- storage.py  : stockage objet des fichiers audio
- carnet.py   : carnet PDF (hors bêta, activable)
"""
from datetime import datetime, timedelta, timezone
import hashlib
import html as _html
import io
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import List, Literal, Optional
import uuid
import zipfile

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

from beta import MAX_RESIDENTS, audit, beta_router, configure_beta, ensure_beta_indexes, ensure_feature, get_settings
from carnet import build_carnet_pdf
from quiz import configure_quiz, ensure_quiz_indexes, quiz_router
from security import (
    AuthUser,
    auth_router,
    configure_security,
    consume_quota,
    current_user,
    ensure_security_indexes,
    require_admin,
)
from storage import APP_NAME, EMERGENT_KEY, delete_object, get_object, init_storage, put_object

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
configure_security(db)
configure_beta(db)
configure_quiz(db)
app = FastAPI(title="Racontelle Care API")
api_router = APIRouter(prefix="/api")

# Environ 2 h 30 d'enregistrement en qualité haute (AAC ~1 Mo/min) : une
# narration n'est jamais coupée (BT-09) et doit pouvoir être sauvegardée.
MAX_AUDIO_BYTES = 150 * 1024 * 1024
# La transcription Whisper n'accepte que 25 Mo : au-delà, elle est refusée
# proprement sans empêcher la sauvegarde de l'audio.
MAX_TRANSCRIBE_BYTES = 25 * 1024 * 1024
CONSENT_TEXT_VERSION = "beta-2026-09"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------


class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


ConsentStatus = Literal["obtained", "pending", "withdrawn"]


class ResidentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    last_initial: Optional[str] = Field(default=None, max_length=40)
    unit: Optional[str] = Field(default=None, max_length=60)
    consent_status: ConsentStatus = "pending"
    consent_reference: Optional[str] = Field(default=None, max_length=200)


class ResidentPatch(BaseModel):
    # `active` n'est volontairement pas modifiable ici : le retrait passe par
    # DELETE (administrateur) et une réactivation contournerait la limite de 5.
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    last_initial: Optional[str] = Field(default=None, max_length=40)
    unit: Optional[str] = Field(default=None, max_length=60)
    consent_status: Optional[ConsentStatus] = None
    consent_reference: Optional[str] = Field(default=None, max_length=200)


class ResidentOut(BaseModel):
    id: str
    display_name: str
    last_initial: Optional[str] = None
    unit: Optional[str] = None
    consent_status: str
    consent_updated_at: Optional[str] = None
    active: bool
    created_at: str


class QuestionOut(BaseModel):
    id: str
    number: Optional[int] = None
    theme: str
    text: str
    level: Optional[str] = None
    usage: Optional[str] = None
    tags: List[str] = []
    sensitive: bool = False
    active: bool = True


class CapsuleCreate(BaseModel):
    resident_id: Optional[str] = None
    question_id: Optional[str] = None
    mode: Literal["free", "question"] = "free"
    theme: Optional[str] = Field(default=None, max_length=120)
    title: Optional[str] = Field(default=None, max_length=200)
    # Aucune coupure automatique : une narration peut durer bien plus de 5 minutes.
    duration_sec: int = Field(default=0, ge=0, le=6 * 3600)
    # Heure d'enregistrement sur l'appareil : conservée telle quelle pour qu'un
    # souvenir envoyé plus tard (réseau faible) garde sa date d'origine.
    recorded_at: str = Field(max_length=40)
    # Champs historiques acceptés mais jamais stockés : l'audio passe par
    # POST /capsules/{id}/audio (taille et type contrôlés).
    audio_uri: Optional[str] = None
    audio_base64: Optional[str] = None


class CapsuleOut(BaseModel):
    id: str
    resident_id: Optional[str] = None
    question_id: Optional[str] = None
    mode: str
    capsule_type: str = "spontaneous"
    theme: Optional[str] = None
    title: Optional[str] = None
    duration_sec: int
    recorded_at: str
    created_at: Optional[str] = None
    created_by_name: Optional[str] = None
    consent_status: Optional[str] = None
    classified_at: Optional[str] = None
    status: str
    synced: bool = True
    transcription: Optional[str] = None
    share_id: Optional[str] = None
    share_expires_at: Optional[str] = None
    # Vrai quand une copie de l'audio est conservée dans le stockage serveur :
    # l'application s'en sert avant d'effacer les fichiers locaux.
    audio_stored: bool = False
    upload_status: str = "pending"


def present_capsule(capsule: dict) -> dict:
    capsule["audio_stored"] = bool(capsule.get("storage_path"))
    capsule["upload_status"] = "saved" if capsule["audio_stored"] else "pending"
    capsule["capsule_type"] = "guided" if capsule.get("mode") == "question" else "spontaneous"
    return capsule


CAPSULE_PROJECTION = {"_id": 0, "audio_base64": 0, "audio_uri": 0}


# ---------------------------------------------------------------------------
# Banque de 400 questions (annexe A du cahier des charges bêta)
# ---------------------------------------------------------------------------

QUESTIONS_FILE = ROOT_DIR / "data" / "questions.json"


def load_question_bank() -> list[dict]:
    themes = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    bank, number = [], 0
    for theme in themes:
        for text in theme["questions"]:
            number += 1
            bank.append({
                "id": f"q{number:03d}",
                "number": number,
                "theme": theme["theme"],
                "text": text,
                "level": theme["level"],
                "usage": theme["usage"],
                "tags": theme["tags"],
                "sensitive": bool(theme["sensitive"]),
            })
    return bank


async def ensure_questions() -> None:
    bank = load_question_bank()
    for question in bank:
        await db.questions.update_one(
            {"id": question["id"]},
            {"$set": {**question, "active": True}, "$setOnInsert": {"created_at": now_iso()}},
            upsert=True,
        )
    # Les 30 questions de la première version restent en base (des souvenirs y
    # sont rattachés) mais ne sont plus proposées.
    await db.questions.update_many({"number": {"$exists": False}}, {"$set": {"active": False}})
    await db.question_states.create_index([("tenant_id", 1), ("question_id", 1)], unique=True)


async def tenant_questions(tenant_id: str, include_disabled: bool = False) -> list[dict]:
    settings = await get_settings(tenant_id)
    query: dict = {"active": True}
    if not settings["sensitive_themes"] and not include_disabled:
        query["sensitive"] = False
    questions = await db.questions.find(query, {"_id": 0}).sort("number", 1).to_list(1000)
    states = {
        state["question_id"]: state["active"]
        for state in await db.question_states.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(2000)
    }
    for question in questions:
        question["active"] = states.get(question["id"], True)
    return questions if include_disabled else [question for question in questions if question["active"]]


# ---------------------------------------------------------------------------
# Démarrage
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_seed() -> None:
    await ensure_security_indexes()
    await ensure_beta_indexes()
    await ensure_quiz_indexes()
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


# ---------------------------------------------------------------------------
# Résidents (5 profils maximum) et consentement
# ---------------------------------------------------------------------------


async def log_consent(user: AuthUser, resident_id: str, status: str, reference: Optional[str]) -> None:
    await db.consent_logs.insert_one(
        {
            "id": str(uuid.uuid4()),
            "tenant_id": user.tenant_id,
            "resident_id": resident_id,
            "type": "enregistrement_vocal",
            "status": status,
            "date": now_iso(),
            "text_version": CONSENT_TEXT_VERSION,
            "reference": reference,
            "recorded_by": user.id,
        }
    )


@api_router.get("/residents", response_model=List[ResidentOut])
async def get_residents(user: AuthUser = Depends(current_user)):
    return await db.residents.find(
        {"tenant_id": user.tenant_id, "active": True}, {"_id": 0}
    ).sort("created_at", 1).to_list(MAX_RESIDENTS)


@api_router.post("/residents", response_model=ResidentOut, status_code=201)
async def create_resident(input: ResidentCreate, user: AuthUser = Depends(current_user)):
    if await db.residents.count_documents({"tenant_id": user.tenant_id, "active": True}) >= MAX_RESIDENTS:
        raise HTTPException(status_code=400, detail=f"Limite de {MAX_RESIDENTS} profils atteinte pour la bêta")
    stamp = now_iso()
    resident = {
        "id": str(uuid.uuid4()),
        "display_name": input.display_name.strip(),
        "last_initial": (input.last_initial or "").strip() or None,
        "unit": (input.unit or "").strip() or None,
        "consent_status": input.consent_status,
        "consent_updated_at": stamp,
        "active": True,
        "created_at": stamp,
        "tenant_id": user.tenant_id,
        "created_by": user.id,
    }
    await db.residents.insert_one(resident)
    resident.pop("_id", None)
    await log_consent(user, resident["id"], input.consent_status, input.consent_reference)
    await audit(user, "resident.create", "resident", resident["id"], {"consent_status": input.consent_status})
    return resident


@api_router.patch("/residents/{resident_id}", response_model=ResidentOut)
async def update_resident(
    resident_id: str, input: ResidentPatch, user: AuthUser = Depends(current_user)
):
    current = await db.residents.find_one({"id": resident_id, "tenant_id": user.tenant_id}, {"_id": 0})
    if not current:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    changes = input.model_dump(exclude_none=True)
    reference = changes.pop("consent_reference", None)
    for key in ("display_name", "last_initial", "unit"):
        if key in changes:
            changes[key] = changes[key].strip() or None
    if changes.get("display_name") is None:
        changes.pop("display_name", None)
    if not changes:
        return current
    consent_changed = "consent_status" in changes and changes["consent_status"] != current.get("consent_status")
    if consent_changed:
        changes["consent_updated_at"] = now_iso()
    doc = await db.residents.find_one_and_update(
        {"id": resident_id, "tenant_id": user.tenant_id},
        {"$set": changes},
        return_document=True,
        projection={"_id": 0},
    )
    if consent_changed:
        await log_consent(user, resident_id, changes["consent_status"], reference)
        await audit(user, "resident.consent_change", "resident", resident_id, {"from": current.get("consent_status"), "to": changes["consent_status"]})
    return doc


@api_router.get("/residents/{resident_id}/consents")
async def resident_consents(resident_id: str, user: AuthUser = Depends(current_user)):
    return await db.consent_logs.find(
        {"tenant_id": user.tenant_id, "resident_id": resident_id}, {"_id": 0}
    ).sort("date", -1).to_list(100)


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
    await audit(admin, "resident.archive", "resident", resident_id)
    return {"deleted": True}


async def erase_capsule(capsule: dict, admin: AuthUser) -> None:
    """Rend un souvenir définitivement inaccessible : audio effacé du stockage,
    liens familiaux révoqués, fiche supprimée."""
    if capsule.get("storage_path"):
        await run_in_threadpool(delete_object, capsule["storage_path"])
    await db.share_tokens.update_many(
        {"tenant_id": admin.tenant_id, "capsule_id": capsule["id"], "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(timezone.utc), "revoked_by": admin.id}},
    )
    await db.capsules.delete_one({"id": capsule["id"], "tenant_id": admin.tenant_id})


@api_router.delete("/residents/{resident_id}/purge")
async def purge_resident(resident_id: str, admin: AuthUser = Depends(require_admin)):
    """Suppression RGPD à la demande du résident, d'un proche ou d'un
    représentant : tous les souvenirs et audios sont effacés, le profil est
    anonymisé. Seule la trace de l'opération reste dans le journal."""
    resident = await db.residents.find_one({"id": resident_id, "tenant_id": admin.tenant_id}, {"_id": 0})
    if not resident:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    capsules = await db.capsules.find({"resident_id": resident_id, "tenant_id": admin.tenant_id}, {"_id": 0}).to_list(5000)
    for capsule in capsules:
        await erase_capsule(capsule, admin)
    await db.residents.update_one(
        {"id": resident_id, "tenant_id": admin.tenant_id},
        {"$set": {"active": False, "display_name": "Profil supprimé", "last_initial": None, "unit": None, "purged_at": now_iso(), "removed_by": admin.id}},
    )
    await db.consent_logs.update_many({"tenant_id": admin.tenant_id, "resident_id": resident_id}, {"$set": {"reference": None}})
    await audit(admin, "resident.purge", "resident", resident_id, {"capsules_erased": len(capsules)})
    return {"purged": True, "capsules_erased": len(capsules)}


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
        {"$set": {"active": False, "merged_into": input.keep_id, "removed_at": now_iso(), "removed_by": admin.id}},
    )
    await audit(admin, "resident.merge", "resident", input.keep_id, {"merged": merge_ids})
    return {"merged": merge_count}


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


@api_router.get("/questions", response_model=List[QuestionOut])
async def get_questions(
    theme: Optional[str] = Query(default=None),
    limit: int = Query(default=400, le=400),
    user: AuthUser = Depends(current_user),
):
    questions = await tenant_questions(user.tenant_id)
    if theme and theme != "Tous":
        questions = [question for question in questions if question["theme"] == theme]
    return questions[:limit]


@api_router.get("/questions/themes")
async def get_themes(user: AuthUser = Depends(current_user)):
    settings = await get_settings(user.tenant_id)
    questions = await tenant_questions(user.tenant_id, include_disabled=True)
    themes: dict[str, dict] = {}
    for question in questions:
        entry = themes.setdefault(question["theme"], {"theme": question["theme"], "sensitive": question["sensitive"], "active_count": 0, "total": 0})
        entry["total"] += 1
        entry["active_count"] += 1 if question["active"] else 0
    for entry in themes.values():
        entry["enabled"] = entry["active_count"] > 0 and (settings["sensitive_themes"] or not entry["sensitive"])
    return list(themes.values())


@api_router.get("/questions/admin", response_model=List[QuestionOut])
async def admin_questions(theme: Optional[str] = None, admin: AuthUser = Depends(require_admin)):
    questions = await tenant_questions(admin.tenant_id, include_disabled=True)
    return [question for question in questions if not theme or question["theme"] == theme]


class QuestionToggle(BaseModel):
    active: bool


@api_router.patch("/questions/{question_id}")
async def toggle_question(question_id: str, body: QuestionToggle, admin: AuthUser = Depends(require_admin)):
    if not await db.questions.find_one({"id": question_id, "active": True}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=404, detail="Question introuvable")
    await db.question_states.update_one(
        {"tenant_id": admin.tenant_id, "question_id": question_id},
        {"$set": {"active": body.active, "updated_at": now_iso(), "updated_by": admin.id}},
        upsert=True,
    )
    await audit(admin, "question.toggle", "question", question_id, {"active": body.active})
    return {"id": question_id, "active": body.active}


# ---------------------------------------------------------------------------
# Capsules vocales
# ---------------------------------------------------------------------------


def spontaneous_title(recorded_at: str) -> str:
    try:
        stamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        return f"Souvenir spontané — {stamp.strftime('%d/%m/%Y %H:%M')}"
    except ValueError:
        return "Souvenir spontané"


@api_router.post("/capsules", response_model=CapsuleOut, status_code=201)
async def create_capsule(input: CapsuleCreate, user: AuthUser = Depends(current_user)):
    resident = None
    if input.mode == "question" and not input.resident_id:
        raise HTTPException(status_code=400, detail="Un souvenir guidé doit être rattaché à un résident")
    if input.resident_id:
        resident = await db.residents.find_one(
            {"id": input.resident_id, "tenant_id": user.tenant_id}, {"_id": 0}
        )
        if not resident:
            raise HTTPException(status_code=404, detail="Profil introuvable")
        if resident.get("consent_status") != "obtained":
            raise HTTPException(status_code=403, detail="Consentement requis")
    title = (input.title or "").strip() or None
    if not title:
        if input.mode == "question" and input.question_id:
            question = await db.questions.find_one({"id": input.question_id}, {"_id": 0, "text": 1})
            title = (question or {}).get("text")
        title = title or spontaneous_title(input.recorded_at)
    capsule = {
        "id": str(uuid.uuid4()),
        **input.model_dump(exclude={"audio_uri", "audio_base64", "title"}),
        "title": title,
        "status": "assigned" if input.resident_id else "unclassified",
        "synced": True,
        "consent_status": resident.get("consent_status") if resident else None,
        "created_at": now_iso(),
        "tenant_id": user.tenant_id,
        "created_by": user.id,
        "created_by_name": user.full_name,
    }
    await db.capsules.insert_one(capsule)
    capsule.pop("_id", None)
    return present_capsule(capsule)


async def attach_active_shares(capsules: list[dict], tenant_id: str) -> list[dict]:
    for capsule in capsules:
        present_capsule(capsule)
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


@api_router.get("/capsules", response_model=List[CapsuleOut])
async def get_capsules(user: AuthUser = Depends(current_user)):
    capsules = await db.capsules.find({"tenant_id": user.tenant_id}, CAPSULE_PROJECTION).sort("recorded_at", -1).to_list(2000)
    return await attach_active_shares(capsules, user.tenant_id)


@api_router.get("/residents/{resident_id}/capsules", response_model=List[CapsuleOut])
async def get_resident_capsules(resident_id: str, user: AuthUser = Depends(current_user)):
    if not await db.residents.find_one(
        {"id": resident_id, "tenant_id": user.tenant_id}, {"_id": 0, "id": 1}
    ):
        raise HTTPException(status_code=404, detail="Profil introuvable")
    capsules = await db.capsules.find(
        {"resident_id": resident_id, "tenant_id": user.tenant_id}, CAPSULE_PROJECTION
    ).sort("recorded_at", -1).to_list(1000)
    return await attach_active_shares(capsules, user.tenant_id)


@api_router.get("/capsules/unclassified", response_model=List[CapsuleOut])
async def get_unclassified_capsules(user: AuthUser = Depends(current_user)):
    capsules = await db.capsules.find(
        {"status": "unclassified", "tenant_id": user.tenant_id}, CAPSULE_PROJECTION
    ).sort("recorded_at", -1).to_list(1000)
    return [present_capsule(capsule) for capsule in capsules]


class CapsulePatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    theme: Optional[str] = Field(default=None, max_length=120)
    question_id: Optional[str] = Field(default=None, max_length=80)


@api_router.patch("/capsules/{capsule_id}", response_model=CapsuleOut)
async def update_capsule(
    capsule_id: str, input: CapsulePatch, user: AuthUser = Depends(current_user)
):
    """Titre, thème ou question rattachée (classement d'un souvenir spontané)."""
    changes = input.model_dump(exclude_none=True)
    if "title" in changes:
        changes["title"] = changes["title"].strip()
    if changes.get("question_id"):
        question = await db.questions.find_one({"id": changes["question_id"]}, {"_id": 0, "theme": 1})
        if not question:
            raise HTTPException(status_code=404, detail="Question introuvable")
        changes.setdefault("theme", question["theme"])
    if not changes:
        raise HTTPException(status_code=400, detail="Aucune modification")
    doc = await db.capsules.find_one_and_update(
        {"id": capsule_id, "tenant_id": user.tenant_id},
        {"$set": changes},
        return_document=True,
        projection=CAPSULE_PROJECTION,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    if "theme" in changes or "question_id" in changes:
        await audit(user, "capsule.update", "capsule", capsule_id, {k: v for k, v in changes.items() if k != "title"})
    return present_capsule(doc)


@api_router.delete("/capsules/{capsule_id}")
async def delete_capsule(capsule_id: str, admin: AuthUser = Depends(require_admin)):
    """Suppression contrôlée (RGPD) : l'audio devient inaccessible et l'action
    est journalisée (BT-20)."""
    capsule = await db.capsules.find_one({"id": capsule_id, "tenant_id": admin.tenant_id}, {"_id": 0})
    if not capsule:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    await erase_capsule(capsule, admin)
    await audit(admin, "capsule.delete", "capsule", capsule_id, {"resident_id": capsule.get("resident_id"), "recorded_at": capsule.get("recorded_at")})
    return {"deleted": True}


@api_router.patch("/capsules/{capsule_id}/assign", response_model=CapsuleOut)
async def assign_capsule(
    capsule_id: str, resident_id: str, user: AuthUser = Depends(current_user)
):
    """Classement d'un souvenir « À classer » ou réaffectation d'un souvenir
    mal classé, avec traçabilité (BT-12, BT-13)."""
    resident = await db.residents.find_one(
        {"id": resident_id, "tenant_id": user.tenant_id, "active": True}, {"_id": 0}
    )
    if not resident:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    if resident.get("consent_status") != "obtained":
        raise HTTPException(status_code=403, detail="Consentement requis pour rattacher un souvenir à ce profil")
    previous = await db.capsules.find_one({"id": capsule_id, "tenant_id": user.tenant_id}, {"_id": 0, "resident_id": 1})
    if not previous:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    doc = await db.capsules.find_one_and_update(
        {"id": capsule_id, "tenant_id": user.tenant_id},
        {"$set": {"resident_id": resident_id, "status": "assigned", "classified_at": now_iso(), "consent_status": resident.get("consent_status")}},
        return_document=True,
        projection=CAPSULE_PROJECTION,
    )
    if previous.get("resident_id") != resident_id:
        action = "capsule.classify" if not previous.get("resident_id") else "capsule.reassign"
        await audit(user, action, "capsule", capsule_id, {"from": previous.get("resident_id"), "to": resident_id})
    return present_capsule(doc)


# ---------------------------------------------------------------------------
# Audio des capsules
# ---------------------------------------------------------------------------

# Types audio produits par l'application (m4a natif, webm navigateur). Tout
# autre type est refusé : le fichier est ensuite servi sur le lien public de
# partage et un type « text/html » permettrait d'y injecter une page piégée.
ALLOWED_AUDIO_TYPES = {
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
    "audio/aac",
    "audio/mpeg",
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "video/webm",  # certains navigateurs étiquettent ainsi un enregistrement audio seul
}


def safe_audio_type(file: UploadFile) -> str:
    base = (file.content_type or "").split(";")[0].strip().lower()
    if base in ("", "application/octet-stream"):
        # Blob navigateur sans type : on se fie à l'extension envoyée par l'app.
        base = "audio/webm" if (file.filename or "").lower().endswith(".webm") else "audio/m4a"
    if base not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Format audio non pris en charge")
    return "audio/webm" if base == "video/webm" else base


def served_audio_type(content_type: Optional[str]) -> str:
    """Type renvoyé aux navigateurs : jamais autre chose que de l'audio."""
    base = (content_type or "").split(";")[0].strip().lower()
    return base if base in ALLOWED_AUDIO_TYPES and base.startswith("audio/") else "application/octet-stream"


async def read_audio_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Fichier audio trop volumineux")
    if not data:
        raise HTTPException(status_code=400, detail="Fichier audio vide")
    return data


async def consented_capsule(capsule_id: str, user: AuthUser) -> dict:
    doc = await db.capsules.find_one({"id": capsule_id, "tenant_id": user.tenant_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    if doc.get("resident_id"):
        resident = await db.residents.find_one(
            {"id": doc["resident_id"], "tenant_id": user.tenant_id}, {"_id": 0}
        )
        if not resident or resident.get("consent_status") != "obtained":
            raise HTTPException(status_code=403, detail="Consentement requis")
    return doc


@api_router.post("/capsules/{capsule_id}/audio")
async def upload_capsule_audio(
    capsule_id: str,
    file: UploadFile = File(...),
    user: AuthUser = Depends(current_user),
):
    """Conserve précieusement l'audio d'une capsule dans le stockage objet."""
    await consented_capsule(capsule_id, user)
    content_type = safe_audio_type(file)
    data = await read_audio_upload(file)
    remaining = await consume_quota(user, "upload")
    path = f"{APP_NAME}/{user.tenant_id}/audio/{capsule_id}.m4a"
    try:
        await run_in_threadpool(put_object, path, data, content_type)
    except Exception as exc:
        logger.warning("échec d'envoi audio (capsule %s) : %s", capsule_id, exc)
        raise HTTPException(status_code=502, detail="Stockage audio momentanément indisponible")
    await db.capsules.update_one(
        {"id": capsule_id, "tenant_id": user.tenant_id},
        {"$set": {"storage_path": path, "audio_content_type": content_type, "uploaded_at": now_iso()}},
    )
    return {"uploaded": True, "path": path, "remaining": remaining}


@api_router.get("/capsules/{capsule_id}/audio")
async def capsule_audio(capsule_id: str, user: AuthUser = Depends(current_user)):
    """Lecture de la copie serveur (autre appareil, fichier local perdu)."""
    doc = await db.capsules.find_one({"id": capsule_id, "tenant_id": user.tenant_id}, {"_id": 0})
    if not doc or not doc.get("storage_path"):
        raise HTTPException(status_code=404, detail="Audio introuvable")
    try:
        data, stored_type = await run_in_threadpool(get_object, doc["storage_path"])
    except Exception:
        raise HTTPException(status_code=404, detail="Audio introuvable")
    return Response(
        content=data,
        media_type=served_audio_type(doc.get("audio_content_type") or stored_type),
        headers={"Cache-Control": "private, no-store"},
    )


@api_router.post("/capsules/{capsule_id}/transcribe")
async def transcribe_capsule(
    capsule_id: str,
    file: UploadFile = File(...),
    user: AuthUser = Depends(current_user),
):
    await ensure_feature(user, "transcription")
    doc = await consented_capsule(capsule_id, user)
    if doc.get("transcription"):
        return {"transcription": doc["transcription"]}
    safe_audio_type(file)
    data = await read_audio_upload(file)
    if len(data) > MAX_TRANSCRIBE_BYTES:
        raise HTTPException(status_code=413, detail="Récit trop long pour la transcription automatique (25 minutes environ)")
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


# ---------------------------------------------------------------------------
# Partage famille (hors bêta, activable)
# ---------------------------------------------------------------------------


@api_router.post("/capsules/{capsule_id}/share")
async def share_capsule(capsule_id: str, user: AuthUser = Depends(current_user)):
    await ensure_feature(user, "family_share")
    doc = await consented_capsule(capsule_id, user)
    if not doc.get("resident_id"):
        raise HTTPException(status_code=400, detail="Classez d’abord ce souvenir : un souvenir « À classer » ne peut pas être partagé.")
    if not doc.get("storage_path"):
        raise HTTPException(status_code=400, detail="Audio pas encore conservé sur le serveur")
    token = uuid.uuid4().hex + uuid.uuid4().hex
    share_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    await db.share_tokens.update_many(
        {"capsule_id": capsule_id, "tenant_id": user.tenant_id, "revoked_at": None},
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
    await audit(user, "share.create", "capsule", capsule_id, {"share_id": share_id})
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
    await audit(admin, "share.revoke", "share", share_id)
    return {"revoked": True}


SHARE_PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Un souvenir partagé — Racontelle Care</title>
<style>
  body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; background:#FFFFFF; color:#2F3E52; }}
  main {{ max-width: 560px; margin: 0 auto; padding: 48px 24px 64px; }}
  .brand {{ font-style: italic; color:#2F3E52; font-size: 30px; margin-bottom: 4px; }}
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


async def active_share(token: str) -> dict:
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
    # Un partage désactivé par l'établissement coupe aussi les liens existants.
    if not (await get_settings(share["tenant_id"]))["family_share"]:
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré")
    return share


@api_router.get("/share/{token}", response_class=HTMLResponse)
async def share_page(token: str):
    share = await active_share(token)
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
    try:
        date_label = datetime.fromisoformat(str(doc.get("recorded_at", "")).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        date_label = "date inconnue"
    transcription_block = f"<blockquote>{_html.escape(doc['transcription'])}</blockquote>" if doc.get("transcription") else ""
    page = SHARE_PAGE.format(
        title=title,
        subtitle=f"{_html.escape(who)} · {date_label}",
        token=_html.escape(token),
        transcription_block=transcription_block,
    )
    return HTMLResponse(
        page,
        headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; media-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            "Cache-Control": "private, no-store",
        },
    )


@api_router.get("/share/{token}/audio")
async def share_audio(token: str):
    share = await active_share(token)
    doc = await db.capsules.find_one(
        {"id": share["capsule_id"], "tenant_id": share["tenant_id"]}, {"_id": 0}
    )
    if not doc or not doc.get("storage_path"):
        raise HTTPException(status_code=404, detail="Audio introuvable")
    try:
        data, stored_type = await run_in_threadpool(get_object, doc["storage_path"])
    except Exception:
        raise HTTPException(status_code=404, detail="Audio introuvable")
    # Les audios déposés avant le contrôle des types peuvent porter n'importe
    # quel type : on ne renvoie que de l'audio, et le navigateur ne devine rien.
    return Response(
        content=data,
        media_type=served_audio_type(doc.get("audio_content_type") or stored_type),
        headers={"Cache-Control": "private, no-store"},
    )


# ---------------------------------------------------------------------------
# Export équipe soignante et carnet PDF
# ---------------------------------------------------------------------------


def safe_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "resident"


@api_router.get("/residents/{resident_id}/export")
async def export_resident(resident_id: str, admin: AuthUser = Depends(require_admin)):
    """Export équipe soignante : un ZIP regroupant les audios conservés et les
    métadonnées du résident (préalable au retrait du profil)."""
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
            date_label = str(capsule.get("recorded_at", ""))[:16].replace("T", " ")
            title = capsule.get("title") or "Souvenir vocal"
            lines.append(f"{index}. {date_label} — {title} ({capsule.get('duration_sec', 0)} s)")
            if capsule.get("theme"):
                lines.append(f"   Thème : {capsule['theme']}")
            if capsule.get("transcription"):
                lines.append(f"   Transcription : {capsule['transcription']}")
            if capsule.get("storage_path"):
                filename = f"audio/{index:02d}-{date_label[:10]}.m4a"
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
    await audit(admin, "resident.export", "resident", resident_id, {"capsules": len(capsules)})
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="racontelle-{safe_filename(resident["display_name"])}.zip"'},
    )


@api_router.get("/residents/{resident_id}/carnet")
async def carnet_pdf(resident_id: str, admin: AuthUser = Depends(require_admin)):
    """Impression du carnet : un PDF élégant des souvenirs du résident."""
    await ensure_feature(admin, "carnet_pdf")
    resident = await db.residents.find_one(
        {"id": resident_id, "tenant_id": admin.tenant_id}, {"_id": 0}
    )
    if not resident:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    capsules = await db.capsules.find(
        {"resident_id": resident_id, "tenant_id": admin.tenant_id}, {"_id": 0}
    ).sort("recorded_at", 1).to_list(1000)
    pdf_bytes = await run_in_threadpool(build_carnet_pdf, resident, capsules)
    await audit(admin, "resident.carnet", "resident", resident_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="racontelle-carnet-{safe_filename(resident["display_name"])}.pdf"'},
    )


# ---------------------------------------------------------------------------
# Lecture vocale des questions (TTS)
# ---------------------------------------------------------------------------


class TtsRequest(BaseModel):
    text: str = Field(max_length=4000)


@api_router.post("/tts")
async def text_to_speech(input: TtsRequest, user: AuthUser = Depends(current_user)):
    """Lecture vocale : questions et transcriptions lues à voix haute.
    Voix « coral », débit posé pour un public senior. Audio mis en cache dans
    le stockage objet (clé = hash texte+voix+modèle+format)."""
    await ensure_feature(user, "voice_reading")
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    text = re.sub(r"https?://\S+", "", input.text)
    text = re.sub(r"[*_#>~|`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texte vide")
    key = hashlib.sha256(f"{text}|coral|0.95|tts-1|mp3".encode()).hexdigest()
    doc = await db.tts_cache.find_one({"key": key}, {"_id": 0})
    if not doc:
        await consume_quota(user, "tts")
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
        # Privé : une lecture vocale peut contenir la transcription d'un résident.
        headers={"Cache-Control": "private, max-age=31536000"},
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(beta_router)
app.include_router(quiz_router)
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
    # Le navigateur ne doit jamais « deviner » un type (audio servi en HTML) et
    # les liens de partage, qui portent un jeton, ne fuient pas en Referer.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
