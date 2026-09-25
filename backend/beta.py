"""Pilotage de la bêta Racontelle Care (cahier des charges bêta, §2, §11 à §14).

- Interrupteurs de fonctions par établissement (activables sans redéploiement).
- Journal des actions sensibles (AuditLog).
- Retours des testeurs (Feedback, avec version de l'application).
- Événements d'usage et indicateurs exportables.
"""
from __future__ import annotations

import csv
import io
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from security import AuthUser, current_user, require_admin

db = None
beta_router = APIRouter(prefix="/api", tags=["beta"])

MAX_RESIDENTS = 5

# Valeurs par défaut conformes au cahier des charges bêta : le quiz fait partie
# du périmètre ; transcription, partage famille et carnet PDF sont hors bêta
# (§16) et restent désactivés tant qu'un administrateur ne les active pas ; les
# thèmes sensibles sont inactifs par défaut (§6, BT-07).
DEFAULT_SETTINGS: dict[str, bool] = {
    "quiz": True,
    "sensitive_themes": False,
    "voice_reading": True,
    "family_share": False,
    "transcription": False,
    "carnet_pdf": False,
}

FEATURE_OFF_MESSAGES = {
    "quiz": "Le module « Qui a dit ça ? » est désactivé pour cet établissement.",
    "sensitive_themes": "Les thèmes sensibles ne sont pas activés.",
    "voice_reading": "La lecture vocale est désactivée pour cet établissement.",
    "family_share": "Le partage famille n’est pas activé pendant la bêta.",
    "transcription": "La transcription n’est pas activée pendant la bêta.",
    "carnet_pdf": "Le carnet PDF n’est pas activé pendant la bêta.",
}


def configure_beta(database) -> None:
    global db
    db = database


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


async def ensure_beta_indexes() -> None:
    await db.tenant_settings.create_index("tenant_id", unique=True)
    await db.audit_logs.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.feedback.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.usage_events.create_index([("tenant_id", 1), ("type", 1)])
    await db.consent_logs.create_index([("tenant_id", 1), ("resident_id", 1)])


async def get_settings(tenant_id: str) -> dict[str, bool]:
    doc = await db.tenant_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
    stored = {key: bool(value) for key, value in (doc or {}).items() if key in DEFAULT_SETTINGS}
    return {**DEFAULT_SETTINGS, **stored}


async def ensure_feature(user: AuthUser, name: str) -> None:
    if not (await get_settings(user.tenant_id)).get(name):
        raise HTTPException(status_code=403, detail=FEATURE_OFF_MESSAGES[name])


async def audit(
    user: AuthUser,
    action: str,
    object_type: str,
    object_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Journalise une action sensible (suppression, réaffectation, consentement,
    accès administrateur…). Aucune donnée de santé, aucun contenu audio."""
    await db.audit_logs.insert_one(
        {
            "id": str(uuid.uuid4()),
            "tenant_id": user.tenant_id,
            "user_id": user.id,
            "user_name": user.full_name,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "details": details or {},
            "created_at": now_iso(),
        }
    )


# ---------------------------------------------------------------------------
# Interrupteurs de fonctions
# ---------------------------------------------------------------------------


class SettingsPatch(BaseModel):
    quiz: Optional[bool] = None
    sensitive_themes: Optional[bool] = None
    voice_reading: Optional[bool] = None
    family_share: Optional[bool] = None
    transcription: Optional[bool] = None
    carnet_pdf: Optional[bool] = None


@beta_router.get("/settings")
async def read_settings(user: AuthUser = Depends(current_user)):
    return {"features": await get_settings(user.tenant_id), "max_residents": MAX_RESIDENTS}


@beta_router.patch("/settings")
async def update_settings(body: SettingsPatch, admin: AuthUser = Depends(require_admin)):
    changes = body.model_dump(exclude_none=True)
    if changes:
        await db.tenant_settings.update_one(
            {"tenant_id": admin.tenant_id},
            {"$set": {**changes, "updated_at": now_iso(), "updated_by": admin.id}},
            upsert=True,
        )
        await audit(admin, "settings.update", "settings", admin.tenant_id, changes)
    return {"features": await get_settings(admin.tenant_id), "max_residents": MAX_RESIDENTS}


# ---------------------------------------------------------------------------
# Journal d'audit
# ---------------------------------------------------------------------------


@beta_router.get("/audit")
async def list_audit(limit: int = Query(default=100, le=500), admin: AuthUser = Depends(require_admin)):
    return await db.audit_logs.find({"tenant_id": admin.tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(limit)


# ---------------------------------------------------------------------------
# Retours des testeurs (BT-22)
# ---------------------------------------------------------------------------

FeedbackCategory = Literal["bug", "micro", "reseau", "sauvegarde", "question", "quiz", "idee", "autre"]


class FeedbackCreate(BaseModel):
    category: FeedbackCategory
    message: Optional[str] = Field(default=None, max_length=2000)
    app_version: str = Field(min_length=1, max_length=40)
    platform: Optional[str] = Field(default=None, max_length=20)
    screen: Optional[str] = Field(default=None, max_length=40)


@beta_router.post("/feedback", status_code=201)
async def create_feedback(body: FeedbackCreate, user: AuthUser = Depends(current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": user.tenant_id,
        "user_id": user.id,
        "user_name": user.full_name,
        **body.model_dump(),
        "message": (body.message or "").strip() or None,
        "created_at": now_iso(),
    }
    await db.feedback.insert_one(doc)
    doc.pop("_id", None)
    return doc


@beta_router.get("/feedback")
async def list_feedback(admin: AuthUser = Depends(require_admin)):
    return await db.feedback.find({"tenant_id": admin.tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


# ---------------------------------------------------------------------------
# Événements d'usage et indicateurs (§13)
# ---------------------------------------------------------------------------

EventType = Literal[
    "session_start",
    "theme_selected",
    "question_change",
    "question_surprise",
    "recording_abandoned",
    "mic_denied",
    "recording_failed",
    "upload_failed",
    "save_failed",
    "quiz_item_played",
]


class EventCreate(BaseModel):
    type: EventType
    theme: Optional[str] = Field(default=None, max_length=80)
    question_id: Optional[str] = Field(default=None, max_length=80)
    item_id: Optional[str] = Field(default=None, max_length=80)
    value: Optional[float] = None
    app_version: Optional[str] = Field(default=None, max_length=40)


@beta_router.post("/events", status_code=201)
async def create_event(body: EventCreate, user: AuthUser = Depends(current_user)):
    await db.usage_events.insert_one(
        {
            "id": str(uuid.uuid4()),
            "tenant_id": user.tenant_id,
            "user_id": user.id,
            **body.model_dump(exclude_none=True),
            "created_at": now_iso(),
        }
    )
    return {"ok": True}


def _parse(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def compute_indicators(tenant_id: str) -> dict[str, Any]:
    capsules = await db.capsules.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "resident_id": 1, "mode": 1, "theme": 1, "question_id": 1, "duration_sec": 1, "created_at": 1, "classified_at": 1, "storage_path": 1},
    ).to_list(20000)
    events = await db.usage_events.find({"tenant_id": tenant_id}, {"_id": 0, "type": 1, "item_id": 1, "value": 1}).to_list(50000)
    quiz_sessions = await db.quiz_sessions.find({"tenant_id": tenant_id}, {"_id": 0, "quiz_type": 1, "item_count": 1}).to_list(5000)
    feedback = await db.feedback.find({"tenant_id": tenant_id}, {"_id": 0, "category": 1}).to_list(5000)
    residents_active = await db.residents.count_documents({"tenant_id": tenant_id, "active": True})

    guided = [c for c in capsules if c.get("mode") == "question"]
    spontaneous = [c for c in capsules if c.get("mode") == "free"]
    durations = [int(c.get("duration_sec") or 0) for c in capsules]
    delays = []
    for capsule in spontaneous:
        created, classified = _parse(capsule.get("created_at")), _parse(capsule.get("classified_at"))
        if created and classified:
            delays.append((classified - created).total_seconds() / 3600)
    event_counts = Counter(event.get("type") for event in events)
    question_counts = Counter(c.get("question_id") for c in guided if c.get("question_id"))
    top_questions = []
    for question_id, count in question_counts.most_common(5):
        question = await db.questions.find_one({"id": question_id}, {"_id": 0, "text": 1, "theme": 1})
        top_questions.append({"question_id": question_id, "text": (question or {}).get("text"), "theme": (question or {}).get("theme"), "count": count})
    quiz_items = Counter(event.get("item_id") for event in events if event.get("type") == "quiz_item_played" and event.get("item_id"))
    top_quiz = []
    for item_id, count in quiz_items.most_common(5):
        item = await db.quiz_items.find_one({"id": item_id, "tenant_id": tenant_id}, {"_id": 0, "prompt_text": 1, "type": 1})
        top_quiz.append({"item_id": item_id, "prompt_text": (item or {}).get("prompt_text"), "type": (item or {}).get("type"), "count": count})
    return {
        "generated_at": now_iso(),
        "usage": {
            "sessions": event_counts.get("session_start", 0),
            "capsules": len(capsules),
            "average_duration_sec": round(sum(durations) / len(durations), 1) if durations else 0,
            "residents_active_profiles": residents_active,
            "residents_with_capsules": len({c.get("resident_id") for c in capsules if c.get("resident_id")}),
        },
        "guided": {
            "capsules": len(guided),
            "top_themes": [{"theme": theme, "count": count} for theme, count in Counter(c.get("theme") for c in guided if c.get("theme")).most_common(5)],
            "top_questions": top_questions,
            "question_changes": event_counts.get("question_change", 0),
            "surprise_questions": event_counts.get("question_surprise", 0),
            "abandoned_before_save": event_counts.get("recording_abandoned", 0),
        },
        "spontaneous": {
            "capsules": len(spontaneous),
            "still_to_classify": sum(1 for c in spontaneous if not c.get("resident_id")),
            "average_hours_before_classification": round(sum(delays) / len(delays), 1) if delays else None,
        },
        "technical": {
            "mic_denied": event_counts.get("mic_denied", 0),
            "recording_failed": event_counts.get("recording_failed", 0),
            "upload_failed": event_counts.get("upload_failed", 0),
            "save_failed": event_counts.get("save_failed", 0),
            "audio_not_yet_on_server": sum(1 for c in capsules if not c.get("storage_path")),
        },
        "quiz": {
            "sessions": len(quiz_sessions),
            "quote_sessions": sum(1 for s in quiz_sessions if s.get("quiz_type") == "quote"),
            "music_sessions": sum(1 for s in quiz_sessions if s.get("quiz_type") == "music"),
            "items_played": sum(int(s.get("item_count") or 0) for s in quiz_sessions),
            "top_items": top_quiz,
        },
        "feedback": dict(Counter(item.get("category") for item in feedback)),
    }


def _flatten(prefix: str, value: Any, rows: list[tuple[str, str]]) -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            _flatten(f"{prefix}.{key}" if prefix else key, inner, rows)
    elif isinstance(value, list):
        for index, inner in enumerate(value, start=1):
            _flatten(f"{prefix}.{index}", inner, rows)
    else:
        rows.append((prefix, "" if value is None else str(value)))


@beta_router.get("/indicators")
async def indicators(format: Literal["json", "csv"] = "json", admin: AuthUser = Depends(require_admin)):
    data = await compute_indicators(admin.tenant_id)
    await audit(admin, "indicators.export", "indicators", None, {"format": format})
    if format == "json":
        return data
    rows: list[tuple[str, str]] = []
    _flatten("", data, rows)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["indicateur", "valeur"])
    writer.writerows(rows)
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="racontelle-indicateurs-beta.csv"'},
    )
