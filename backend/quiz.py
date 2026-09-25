"""Module d'animation « Qui a dit ça ? » (cahier des charges bêta §8, annexe B).

Deux variantes : citations (« Qui a dit ça ? ») et musique (« Qui chante ça ? »).
Règles de droits : un contenu `blocked` ne peut jamais être actif, et un
extrait musical n'est actif qu'avec un fichier fourni et un statut de droits
explicite (BT-19). Un item se désactive sans être supprimé (BT-18). Aucun score
individuel de résident n'est enregistré (BT-17) : seule la session d'animation
peut porter un score facultatif.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from beta import audit, ensure_feature
from security import AuthUser, current_user, require_admin
from storage import APP_NAME, get_object, put_object

db = None
quiz_router = APIRouter(prefix="/api/quiz", tags=["quiz"])

RIGHTS = ("public_domain", "licensed", "provided_by_client", "blocked")
DIFFICULTIES = ("facile", "moyen", "difficile")
MAX_QUIZ_AUDIO_BYTES = 15 * 1024 * 1024
QUIZ_AUDIO_TYPES = {"audio/mpeg", "audio/mp3", "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/aac", "audio/ogg", "audio/wav", "audio/x-wav", "audio/webm"}

PUBLIC_DOMAIN_NOTE = "Auteur décédé depuis plus de 70 ans ; citation courte d’usage courant."

# Citations d'auteurs du domaine public, pour démarrer l'animation dès le
# premier jour. Aucun extrait musical n'est fourni : ils doivent être importés
# avec leur statut de droits (annexe B).
SEED_QUOTES: list[dict[str, Any]] = [
    {"prompt_text": "Le cœur a ses raisons que la raison ne connaît point.", "correct_answer": "Blaise Pascal", "choices": ["Blaise Pascal", "Voltaire", "Molière", "Victor Hugo"], "era": "XVIIe siècle", "theme": "philosophie", "difficulty": "facile", "source_reference": "Pensées (1670)"},
    {"prompt_text": "Rien ne sert de courir ; il faut partir à point.", "correct_answer": "Jean de La Fontaine", "choices": ["Jean de La Fontaine", "Charles Perrault", "Molière", "Jean Racine"], "era": "XVIIe siècle", "theme": "littérature", "difficulty": "facile", "source_reference": "Fables, « Le Lièvre et la Tortue » (1668)"},
    {"prompt_text": "Il faut cultiver notre jardin.", "correct_answer": "Voltaire", "choices": ["Voltaire", "Jean-Jacques Rousseau", "Denis Diderot", "Montesquieu"], "era": "XVIIIe siècle", "theme": "littérature", "difficulty": "moyen", "source_reference": "Candide (1759)"},
    {"prompt_text": "Je pense, donc je suis.", "correct_answer": "René Descartes", "choices": ["René Descartes", "Blaise Pascal", "Montaigne", "Voltaire"], "era": "XVIIe siècle", "theme": "philosophie", "difficulty": "facile", "source_reference": "Discours de la méthode (1637)"},
    {"prompt_text": "Tous pour un, un pour tous !", "correct_answer": "Alexandre Dumas", "choices": ["Alexandre Dumas", "Victor Hugo", "Jules Verne", "Honoré de Balzac"], "era": "XIXe siècle", "theme": "littérature", "difficulty": "facile", "source_reference": "Les Trois Mousquetaires (1844)"},
    {"prompt_text": "Que diable allait-il faire dans cette galère ?", "correct_answer": "Molière", "choices": ["Molière", "Pierre Corneille", "Jean Racine", "Beaumarchais"], "era": "XVIIe siècle", "theme": "théâtre", "difficulty": "moyen", "source_reference": "Les Fourberies de Scapin (1671)"},
    {"prompt_text": "Il faut manger pour vivre, et non pas vivre pour manger.", "correct_answer": "Molière", "choices": ["Molière", "François Rabelais", "Jean de La Fontaine", "Voltaire"], "era": "XVIIe siècle", "theme": "théâtre", "difficulty": "moyen", "source_reference": "L’Avare (1668)"},
    {"prompt_text": "Va, je ne te hais point.", "correct_answer": "Pierre Corneille", "choices": ["Pierre Corneille", "Jean Racine", "Molière", "Marivaux"], "era": "XVIIe siècle", "theme": "théâtre", "difficulty": "difficile", "source_reference": "Le Cid (1637)"},
    {"prompt_text": "Heureux qui, comme Ulysse, a fait un beau voyage…", "correct_answer": "Joachim du Bellay", "choices": ["Joachim du Bellay", "Pierre de Ronsard", "François Villon", "Clément Marot"], "era": "XVIe siècle", "theme": "poésie", "difficulty": "moyen", "source_reference": "Les Regrets (1558)"},
    {"prompt_text": "Mignonne, allons voir si la rose…", "correct_answer": "Pierre de Ronsard", "choices": ["Pierre de Ronsard", "Joachim du Bellay", "François Villon", "Jean de La Fontaine"], "era": "XVIe siècle", "theme": "poésie", "difficulty": "moyen", "source_reference": "Ode à Cassandre (XVIe siècle)"},
    {"prompt_text": "Demain, dès l’aube, à l’heure où blanchit la campagne…", "correct_answer": "Victor Hugo", "choices": ["Victor Hugo", "Alphonse de Lamartine", "Charles Baudelaire", "Alfred de Musset"], "era": "XIXe siècle", "theme": "poésie", "difficulty": "moyen", "source_reference": "Les Contemplations (1856)"},
    {"prompt_text": "Les sanglots longs des violons de l’automne…", "correct_answer": "Paul Verlaine", "choices": ["Paul Verlaine", "Arthur Rimbaud", "Charles Baudelaire", "Stéphane Mallarmé"], "era": "XIXe siècle", "theme": "poésie", "difficulty": "moyen", "source_reference": "Poèmes saturniens (1866)"},
    {"prompt_text": "Science sans conscience n’est que ruine de l’âme.", "correct_answer": "François Rabelais", "choices": ["François Rabelais", "Montaigne", "Blaise Pascal", "Voltaire"], "era": "XVIe siècle", "theme": "philosophie", "difficulty": "difficile", "source_reference": "Pantagruel (1532)"},
    {"prompt_text": "On a souvent besoin d’un plus petit que soi.", "correct_answer": "Jean de La Fontaine", "choices": ["Jean de La Fontaine", "Charles Perrault", "Molière", "Nicolas Boileau"], "era": "XVIIe siècle", "theme": "littérature", "difficulty": "facile", "source_reference": "Fables, « Le Lion et le Rat » (1668)"},
    {"prompt_text": "Ce que l’on conçoit bien s’énonce clairement.", "correct_answer": "Nicolas Boileau", "choices": ["Nicolas Boileau", "Blaise Pascal", "Jean de La Bruyère", "René Descartes"], "era": "XVIIe siècle", "theme": "littérature", "difficulty": "difficile", "source_reference": "L’Art poétique (1674)"},
    {"prompt_text": "Être ou ne pas être, telle est la question.", "correct_answer": "William Shakespeare", "choices": ["William Shakespeare", "Molière", "Goethe", "Cervantès"], "era": "XVIIe siècle", "theme": "théâtre", "difficulty": "facile", "source_reference": "Hamlet (vers 1600)"},
    {"prompt_text": "Je suis venu, j’ai vu, j’ai vaincu.", "correct_answer": "Jules César", "choices": ["Jules César", "Napoléon Bonaparte", "Alexandre le Grand", "Charlemagne"], "era": "Antiquité", "theme": "histoire", "difficulty": "facile", "source_reference": "Veni, vidi, vici — rapporté par Plutarque et Suétone"},
    {"prompt_text": "Il faut rire avant d’être heureux, de peur de mourir sans avoir ri.", "correct_answer": "Jean de La Bruyère", "choices": ["Jean de La Bruyère", "François de La Rochefoucauld", "Molière", "Voltaire"], "era": "XVIIe siècle", "theme": "humour", "difficulty": "difficile", "source_reference": "Les Caractères (1688)"},
]


def configure_quiz(database) -> None:
    global db
    db = database


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def ensure_quiz_indexes() -> None:
    await db.quiz_items.create_index([("tenant_id", 1), ("id", 1)], unique=True)
    await db.quiz_sessions.create_index([("tenant_id", 1), ("started_at", -1)])


def activation_problem(item: dict[str, Any]) -> Optional[str]:
    """Raison pour laquelle un item ne peut pas être actif, ou None."""
    if item.get("rights_status") not in RIGHTS:
        return "Statut de droits inconnu."
    if item.get("rights_status") == "blocked":
        return "Contenu bloqué : il ne peut pas être activé."
    choices = item.get("choices") or []
    if not 2 <= len(choices) <= 4 or item.get("correct_answer") not in choices:
        return "Il faut entre 2 et 4 choix, dont la bonne réponse."
    if item.get("type") == "music" and not (item.get("storage_path") or item.get("audio_url")):
        return "Extrait musical manquant : ajoutez le fichier autorisé avant d’activer."
    return None


async def ensure_seed(tenant_id: str) -> None:
    if await db.quiz_items.count_documents({"tenant_id": tenant_id}):
        return
    stamp = now_iso()
    await db.quiz_items.insert_many([
        {
            "id": f"SEED{index:03d}",
            "tenant_id": tenant_id,
            "type": "quote",
            "audio_file": None,
            "audio_url": None,
            "storage_path": None,
            "rights_status": "public_domain",
            "license_note": PUBLIC_DOMAIN_NOTE,
            "active": True,
            "created_at": stamp,
            "updated_at": stamp,
            **quote,
        }
        for index, quote in enumerate(SEED_QUOTES, start=1)
    ])


def public_item(item: dict[str, Any], admin: bool = False) -> dict[str, Any]:
    out = {key: item.get(key) for key in (
        "id", "type", "prompt_text", "correct_answer", "choices", "era", "theme", "difficulty",
        "source_reference", "rights_status", "license_note", "active", "created_at", "updated_at",
    )}
    # Extrait stocké chez nous (servi par /items/{id}/audio) ou URL privée fournie à l'import.
    out["has_stored_audio"] = bool(item.get("storage_path"))
    out["audio_url"] = item.get("audio_url")
    if admin:
        out["audio_file"] = item.get("audio_file")
        out["activation_problem"] = activation_problem(item)
    return out


@quiz_router.get("/items")
async def list_items(
    type: Optional[Literal["quote", "music"]] = None,
    era: Optional[str] = None,
    theme: Optional[str] = None,
    difficulty: Optional[str] = None,
    user: AuthUser = Depends(current_user),
):
    await ensure_feature(user, "quiz")
    await ensure_seed(user.tenant_id)
    query: dict[str, Any] = {"tenant_id": user.tenant_id, "active": True, "rights_status": {"$ne": "blocked"}}
    for key, value in (("type", type), ("era", era), ("theme", theme), ("difficulty", difficulty)):
        if value:
            query[key] = value
    items = await db.quiz_items.find(query, {"_id": 0}).to_list(2000)
    # Double sécurité : un item devenu non conforme n'est jamais servi.
    return [public_item(item) for item in items if activation_problem(item) is None]


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def era_order(era: str) -> tuple:
    """Époques dans l'ordre chronologique : Antiquité, Moyen Âge, XVIe siècle…
    XXe siècle, puis les périodes datées (« 1960-1970 »), puis le reste."""
    label = era.strip().lower()
    if label.startswith("antiq"):
        return (0, 0, label)
    if label.startswith("moyen"):
        return (1, 0, label)
    numeral = label.split("e", 1)[0].upper()
    if numeral and all(ch in ROMAN for ch in numeral):
        values = [ROMAN[ch] for ch in numeral]
        century = sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))
        return (2, century, label)
    digits = "".join(ch for ch in label[:4] if ch.isdigit())
    if len(digits) == 4:
        return (3, int(digits), label)
    return (4, 0, label)


@quiz_router.get("/filters")
async def list_filters(user: AuthUser = Depends(current_user)):
    await ensure_feature(user, "quiz")
    await ensure_seed(user.tenant_id)
    query = {"tenant_id": user.tenant_id, "active": True}
    return {
        "eras": sorted((v for v in await db.quiz_items.distinct("era", query) if v), key=era_order),
        "themes": sorted(v for v in await db.quiz_items.distinct("theme", query) if v),
        "difficulties": list(DIFFICULTIES),
    }


@quiz_router.get("/admin/items")
async def list_all_items(admin: AuthUser = Depends(require_admin)):
    await ensure_seed(admin.tenant_id)
    items = await db.quiz_items.find({"tenant_id": admin.tenant_id}, {"_id": 0}).sort("id", 1).to_list(5000)
    return [public_item(item, admin=True) for item in items]


class ItemPatch(BaseModel):
    active: Optional[bool] = None
    rights_status: Optional[Literal["public_domain", "licensed", "provided_by_client", "blocked"]] = None
    license_note: Optional[str] = Field(default=None, max_length=500)


@quiz_router.patch("/items/{item_id}")
async def update_item(item_id: str, body: ItemPatch, admin: AuthUser = Depends(require_admin)):
    item = await db.quiz_items.find_one({"tenant_id": admin.tenant_id, "id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Élément du quiz introuvable")
    changes = body.model_dump(exclude_none=True)
    candidate = {**item, **changes}
    if candidate.get("active") and (problem := activation_problem(candidate)):
        if changes.get("active"):
            # Demande explicite d'activation : on explique le refus.
            raise HTTPException(status_code=400, detail=problem)
        # Changement de droits (ex. passage en « bloqué ») : l'item se désactive.
        changes["active"] = False
    changes["updated_at"] = now_iso()
    await db.quiz_items.update_one({"tenant_id": admin.tenant_id, "id": item_id}, {"$set": changes})
    await audit(admin, "quiz.update", "quiz_item", item_id, {k: v for k, v in changes.items() if k != "updated_at"})
    return public_item({**item, **changes}, admin=True)


class ImportRequest(BaseModel):
    format: Literal["json", "csv"]
    content: str = Field(min_length=2, max_length=2_000_000)


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in ("true", "1", "oui", "yes", "vrai")


def _rows_from(body: ImportRequest) -> list[dict[str, Any]]:
    if body.format == "json":
        try:
            data = json.loads(body.content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"JSON invalide : {exc.msg}") from exc
        if isinstance(data, dict):
            data = data.get("items", [])
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="Le JSON doit contenir une liste d’éléments.")
        return [row for row in data if isinstance(row, dict)]
    sample = body.content[:2000]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(body.content.lstrip("﻿")), delimiter=delimiter)
    return [dict(row) for row in reader]


@quiz_router.post("/import")
async def import_items(body: ImportRequest, admin: AuthUser = Depends(require_admin)):
    """Import CSV/JSON selon le gabarit de l'annexe B (colonnes id, type,
    prompt_text, audio_file, correct_answer, choice_a…d, era, theme,
    difficulty, source_reference, rights_status, license_note, active)."""
    rows = _rows_from(body)
    # Les citations fournies sont posées avant tout import, sinon un premier
    # import (établissement neuf) empêcherait leur ajout.
    await ensure_seed(admin.tenant_id)
    if len(rows) > 2000:
        raise HTTPException(status_code=400, detail="2000 éléments maximum par import.")
    report = {"created": 0, "updated": 0, "inactive": [], "errors": []}
    for line, row in enumerate(rows, start=1):
        row = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        item_type = str(row.get("type") or "").lower()
        prompt = str(row.get("prompt_text") or "").strip()
        answer = str(row.get("correct_answer") or "").strip()
        if item_type not in ("quote", "music") or not prompt or not answer:
            report["errors"].append({"line": line, "id": row.get("id"), "error": "type, prompt_text et correct_answer sont obligatoires."})
            continue
        choices = row.get("choices") if isinstance(row.get("choices"), list) else [row.get(f"choice_{k}") for k in "abcd"]
        choices = [str(choice).strip() for choice in choices if choice and str(choice).strip()]
        rights = str(row.get("rights_status") or "blocked").strip().lower()
        difficulty = str(row.get("difficulty") or "moyen").strip().lower()
        audio_value = str(row.get("audio_file") or "").strip() or None
        item_id = str(row.get("id") or "").strip() or f"IMP{uuid.uuid4().hex[:8].upper()}"
        existing = await db.quiz_items.find_one({"tenant_id": admin.tenant_id, "id": item_id}, {"_id": 0})
        item = {
            "id": item_id,
            "tenant_id": admin.tenant_id,
            "type": item_type,
            "prompt_text": prompt[:1000],
            "correct_answer": answer[:200],
            "choices": [choice[:200] for choice in choices][:4],
            "era": (str(row.get("era") or "").strip() or None),
            "theme": (str(row.get("theme") or "").strip() or None),
            "difficulty": difficulty if difficulty in DIFFICULTIES else "moyen",
            "source_reference": (str(row.get("source_reference") or "").strip()[:500] or None),
            "rights_status": rights if rights in RIGHTS else "blocked",
            "license_note": (str(row.get("license_note") or "").strip()[:500] or None),
            "audio_file": audio_value if audio_value and not audio_value.startswith("http") else (existing or {}).get("audio_file"),
            "audio_url": audio_value if audio_value and audio_value.startswith("https://") else (existing or {}).get("audio_url"),
            "storage_path": (existing or {}).get("storage_path"),
            "updated_at": now_iso(),
        }
        if item["correct_answer"] not in item["choices"] and len(item["choices"]) < 4:
            item["choices"].append(item["correct_answer"])
        wanted_active = _as_bool(row.get("active", "true"))
        problem = activation_problem(item)
        item["active"] = wanted_active and problem is None
        if wanted_active and problem:
            report["inactive"].append({"line": line, "id": item_id, "reason": problem})
        if existing:
            await db.quiz_items.update_one({"tenant_id": admin.tenant_id, "id": item_id}, {"$set": item})
            report["updated"] += 1
        else:
            await db.quiz_items.insert_one({**item, "created_at": now_iso()})
            report["created"] += 1
    await audit(admin, "quiz.import", "quiz_item", None, {"created": report["created"], "updated": report["updated"], "errors": len(report["errors"])})
    return report


@quiz_router.post("/items/{item_id}/audio")
async def upload_item_audio(item_id: str, file: UploadFile = File(...), admin: AuthUser = Depends(require_admin)):
    item = await db.quiz_items.find_one({"tenant_id": admin.tenant_id, "id": item_id}, {"_id": 0})
    if not item or item.get("type") != "music":
        raise HTTPException(status_code=404, detail="Extrait musical introuvable")
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in QUIZ_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Format audio non pris en charge")
    data = await file.read(MAX_QUIZ_AUDIO_BYTES + 1)
    if not data or len(data) > MAX_QUIZ_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Fichier audio vide ou trop volumineux (15 Mo max)")
    path = f"{APP_NAME}/{admin.tenant_id}/quiz/{item_id}"
    try:
        await run_in_threadpool(put_object, path, data, content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Stockage audio momentanément indisponible") from exc
    await db.quiz_items.update_one(
        {"tenant_id": admin.tenant_id, "id": item_id},
        {"$set": {"storage_path": path, "audio_content_type": content_type, "audio_file": file.filename, "updated_at": now_iso()}},
    )
    await audit(admin, "quiz.audio_upload", "quiz_item", item_id, {"filename": file.filename})
    return {"uploaded": True}


@quiz_router.get("/items/{item_id}/audio")
async def item_audio(item_id: str, user: AuthUser = Depends(current_user)):
    await ensure_feature(user, "quiz")
    item = await db.quiz_items.find_one({"tenant_id": user.tenant_id, "id": item_id}, {"_id": 0})
    if not item or not item.get("storage_path"):
        raise HTTPException(status_code=404, detail="Extrait introuvable")
    if user.role != "admin" and (not item.get("active") or activation_problem(item)):
        raise HTTPException(status_code=404, detail="Extrait introuvable")
    try:
        data, _ = await run_in_threadpool(get_object, item["storage_path"])
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Extrait introuvable") from exc
    media_type = item.get("audio_content_type") if item.get("audio_content_type") in QUIZ_AUDIO_TYPES else "application/octet-stream"
    return Response(content=data, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


class SessionCreate(BaseModel):
    quiz_type: Literal["quote", "music"]
    item_count: int = Field(ge=0, le=500)
    # Score facultatif de la session d'animation, jamais rattaché à un résident.
    score: Optional[int] = Field(default=None, ge=0, le=500)
    comment: Optional[str] = Field(default=None, max_length=1000)


@quiz_router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, user: AuthUser = Depends(current_user)):
    await ensure_feature(user, "quiz")
    doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": user.tenant_id,
        "user_id": user.id,
        "started_at": now_iso(),
        **body.model_dump(),
    }
    await db.quiz_sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc
