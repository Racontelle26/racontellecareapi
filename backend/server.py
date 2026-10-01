# -*- coding: utf-8 -*-
import os
import re
import logging
import secrets
import hashlib
import ipaddress
import tempfile
import time
from collections import defaultdict, deque
from zoneinfo import ZoneInfo
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List

import jwt
import httpx
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, BackgroundTasks, Request
from fastapi.responses import Response, JSONResponse
from fastapi.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
import requests

try:  # Emergent proxy (optional): only used when no direct provider key is configured
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from emergentintegrations.llm.openai.speech_to_text import OpenAISpeechToText
except ImportError:
    LlmChat = OpenAISpeechToText = None

    class UserMessage:  # same shape as the Emergent message, so the proxy path stays testable without the package
        def __init__(self, text: str):
            self.text = text

from questions_data import parse_questions, THEMES_ORDER
from questions_meta import QUESTION_META

# Theme names used before they were aligned on the editorial annex (commas had been dropped).
LEGACY_THEME_NAMES = {name.replace(",", ""): name for name in THEMES_ORDER if "," in name}

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("racontelle")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
if mongo_url.startswith("mongomock://"):
    # Local test runs only: in-memory MongoDB emulation (pip install mongomock-motor), never in production.
    from mongomock_motor import AsyncMongoMockClient
    client = AsyncMongoMockClient()
else:
    client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# The JWT secret signs every session: a missing or guessable value lets anyone forge a login.
JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()
if len(JWT_SECRET) < 32 or JWT_SECRET == "racontelle-dev-secret-change-me":
    raise RuntimeError("JWT_SECRET manquant ou trop court (32 caractères minimum). "
                       "Générez-en un avec : python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
JWT_ALG = "HS256"
ACCESS_DAYS = 30
CONSENT_VERSION = "beta-2026-09"  # bump when the beta terms text changes
APP_API_VERSION = "1.1.0"
RESET_MIN = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Providers: each integration uses a direct provider when its key is set, otherwise the Emergent proxy.
INTEGRATION_PROXY_URL = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip().rstrip("/")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "racontelle-family"

# Object storage (audio + photos): S3-compatible (Cloudflare R2, Scaleway, AWS…) or Emergent
S3_BUCKET = os.environ.get("S3_BUCKET")
LOCAL_STORAGE_DIR = os.environ.get("LOCAL_STORAGE_DIR")  # local development only (files on disk)
STORAGE_URL = INTEGRATION_PROXY_URL + "/objstore/api/v1/storage"
_storage_key = None
_s3_client = None

# AI: Anthropic (book chapters) and OpenAI Whisper (transcription)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
STT_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_STT_KEY")

MAX_AUDIO_BYTES = 50 * 1024 * 1024
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTOS_PER_CAPSULE = 10
MAX_REQUEST_BYTES = 100 * 1024 * 1024
MAX_AUDIO_DURATION_SEC = 2 * 60 * 60

# Email: Resend directly, or Emergent
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_FROM_ADDRESS = os.environ.get("EMAIL_FROM_ADDRESS")  # e.g. bonjour@racontelle.fr (domain verified in Resend)
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Racontelle")
APP_PUBLIC_URL = os.environ["APP_PUBLIC_URL"].strip().rstrip("/")

if not (LOCAL_STORAGE_DIR or S3_BUCKET or INTEGRATION_PROXY_URL):
    raise RuntimeError("Configurez un stockage : LOCAL_STORAGE_DIR (local), S3_BUCKET (+ S3_*) ou INTEGRATION_PROXY_URL (Emergent)")

# Comma-separated list of web origins allowed to call the API ("*" by default for the Expo preview).
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

TZ_PARIS = ZoneInfo("Europe/Paris")


def now() -> datetime:
    return datetime.now(timezone.utc)


def paris_today() -> str:
    # ZoneInfo handles summer/winter time (a fixed +2h offset was wrong from late October to March).
    return now().astimezone(TZ_PARIS).date().isoformat()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I: codes are typed by hand


def new_invite_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


async def log_event(event_type: str, **fields) -> None:
    """Beta usage journal (section 12 of the MVP spec), exported as CSV by /api/admin/events/export."""
    doc = {"id": oid(), "event_type": event_type, "occurred_at": now().isoformat()}
    doc.update({k: v for k, v in fields.items() if v is not None})
    await db.events.insert_one(doc)


# ---------------------------------------------------------------------------
# Object storage helpers (sync -> run in threadpool)
# ---------------------------------------------------------------------------
class StorageError(Exception):
    def __init__(self, status_code: int = 500):
        super().__init__(f"storage error {status_code}")
        self.status_code = status_code


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.config import Config
        _s3_client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("S3_REGION", "auto"),
            config=Config(retries={"max_attempts": 3}),
        )
    return _s3_client


def _local_file(path: str) -> Path:
    root = Path(LOCAL_STORAGE_DIR).resolve()
    target = (root / path).resolve()
    if root not in target.parents:
        raise StorageError(400)
    return target


def init_storage():
    if LOCAL_STORAGE_DIR:
        Path(LOCAL_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
        return None
    if S3_BUCKET:
        _s3().head_bucket(Bucket=S3_BUCKET)
        return None
    return _init_emergent_storage()


def put_object(path: str, data: bytes, content_type: str) -> dict:
    if LOCAL_STORAGE_DIR:
        target = _local_file(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"path": path}
    if not S3_BUCKET:
        return _put_emergent_object(path, data, content_type)
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        _s3().put_object(Bucket=S3_BUCKET, Key=path, Body=data, ContentType=content_type)
    except (BotoCoreError, ClientError) as e:
        logger.error("S3 put failed for %s: %s", path, e)
        raise StorageError(500)
    return {"path": path}


def get_object(path: str):
    if LOCAL_STORAGE_DIR:
        return _local_file(path).read_bytes(), "application/octet-stream"
    if not S3_BUCKET:
        return _get_emergent_object(path)
    obj = _s3().get_object(Bucket=S3_BUCKET, Key=path)
    return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")


def delete_object(path: str) -> None:
    if LOCAL_STORAGE_DIR:
        _local_file(path).unlink(missing_ok=True)
        return
    if S3_BUCKET:
        _s3().delete_object(Bucket=S3_BUCKET, Key=path)
        return
    raise StorageError(501)  # the Emergent object store exposes no delete endpoint


def _init_emergent_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _put_emergent_object(path: str, data: bytes, content_type: str) -> dict:
    try:
        return _put_emergent_object_raw(path, data, content_type)
    except requests.HTTPError as e:
        raise StorageError(e.response.status_code if e.response is not None else 500)


def _put_emergent_object_raw(path: str, data: bytes, content_type: str) -> dict:
    global _storage_key
    key = _init_emergent_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code == 503:
        _storage_key = None
        key = _init_emergent_storage()
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def _get_emergent_object(path: str):
    key = _init_emergent_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# ---------------------------------------------------------------------------
# AI helpers — Whisper transcription + Claude "roman" chapter
# ---------------------------------------------------------------------------
BOOK_MODEL_PROVIDER = "anthropic"
BOOK_MODEL_NAME = os.environ.get("BOOK_MODEL", "claude-sonnet-5")


async def _speech_to_text(fh) -> str:
    if os.environ.get("OPENAI_API_KEY"):
        from openai import AsyncOpenAI
        stt_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = await stt_client.audio.transcriptions.create(
            file=fh, model="whisper-1", response_format="text", language="fr")
    else:
        if OpenAISpeechToText is None:
            raise RuntimeError("No speech-to-text provider installed")
        stt = OpenAISpeechToText(api_key=STT_API_KEY)
        resp = await stt.transcribe(file=fh, model="whisper-1", response_format="text", language="fr")
    return resp if isinstance(resp, str) else (getattr(resp, "text", None) or str(resp))


def book_ai_available() -> bool:
    """Chapters need either a direct Anthropic key or the Emergent proxy (key + package)."""
    return bool(ANTHROPIC_API_KEY or (EMERGENT_KEY and LlmChat is not None))


async def _write_chapter_text(system: str, prompt: str, circle_id: str) -> str:
    if ANTHROPIC_API_KEY:
        from anthropic import AsyncAnthropic
        llm = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        resp = await llm.messages.create(
            model=BOOK_MODEL_NAME,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("chapter generation refused")
        return "".join(block.text for block in resp.content if block.type == "text")
    if LlmChat is None:
        raise RuntimeError("No chapter-writing provider installed")
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"book-{circle_id}-{secrets.token_hex(4)}",
        system_message=system,
    ).with_model(BOOK_MODEL_PROVIDER, BOOK_MODEL_NAME)
    return await chat.send_message(UserMessage(text=prompt))


async def transcribe_capsule(capsule_id: str, storage_path: str, ext: str):
    """Background task: download the audio, transcribe with Whisper, store the transcript."""
    if not STT_API_KEY:
        await db.capsules.update_one({"id": capsule_id}, {"$set": {"transcript_status": "unavailable"}})
        return
    tmp = None
    try:
        content, _ = await run_in_threadpool(get_object, storage_path)
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
            f.write(content)
            tmp = f.name
        with open(tmp, "rb") as fh:
            text = await _speech_to_text(fh)
        text = (text or "").strip()
        await db.capsules.update_one(
            {"id": capsule_id},
            {"$set": {"transcript": text, "transcript_status": "done" if text else "failed"}},
        )
        logger.info("Transcribed capsule %s (%d chars)", capsule_id, len(text))
    except Exception as e:  # noqa
        logger.error("Transcription failed for %s: %s", capsule_id, e)
        await db.capsules.update_one({"id": capsule_id}, {"$set": {"transcript_status": "failed"}})
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


async def generate_chapter(circle_id: str) -> dict:
    """Weave the circle's memories into one warm, literary French chapter using Claude."""
    circle = await db.circles.find_one({"id": circle_id})
    members = await db.members.find({"circle_id": circle_id, "status": {"$ne": "revoked"}}).to_list(200)
    member_by_id = {m["id"]: m for m in members}
    capsules = await db.capsules.find({"circle_id": circle_id, "status": "saved"}).sort("recorded_at", 1).to_list(500)
    if not capsules:
        raise HTTPException(400, "Ajoutez au moins un souvenir avant de créer un chapitre")
    question_ids = list({c["question_id"] for c in capsules if c.get("question_id")})
    questions = await db.questions.find(
        {"id": {"$in": question_ids}},
        {"_id": 0, "id": 1, "text": 1},
    ).to_list(len(question_ids)) if question_ids else []
    question_by_id = {question["id"]: question for question in questions}

    # Characters
    cast_lines = []
    for m in members:
        if m["status"] == "active" or m["status"] == "pending":
            rel = f" ({m['relationship_label']})" if m.get("relationship_label") else ""
            cast_lines.append(f"- {m['display_name']}{rel}")
    cast = "\n".join(cast_lines) or "- La famille"

    # Memories material
    mem_lines = []
    used_ids = []
    for c in capsules:
        narrator = member_by_id.get(c["narrator_member_id"], {})
        q = question_by_id.get(c.get("question_id"))
        question = q["text"] if q else (c.get("title") or "Souvenir libre")
        transcript = (c.get("transcript") or "").strip()
        body = transcript if transcript else "(souvenir vocal sans transcription — inspire-toi de la question)"
        mem_lines.append(
            f"• Narrateur : {narrator.get('display_name', 'Un proche')}\n"
            f"  Thème : {c.get('theme') or '—'}\n"
            f"  Question : {question}\n"
            f"  Souvenir : {body}"
        )
        used_ids.append(c["id"])

    material = "\n\n".join(mem_lines)
    system = (
        "Tu es un écrivain français au style chaleureux, littéraire et délicat. "
        "Tu écris un chapitre de roman familial à partir de souvenirs RÉELS racontés à voix haute "
        "par les membres d'une même famille. Les membres de la famille sont les personnages principaux. "
        "Règles : reste fidèle aux faits et aux émotions des souvenirs, n'invente pas d'événements majeurs, "
        "mais donne-leur du souffle romanesque, des transitions élégantes et une belle langue. "
        "Écris en français, à la troisième personne, en tissant plusieurs souvenirs en un récit cohérent. "
        "Commence par un titre de chapitre sur la première ligne, précédé de '# '. "
        "Longueur : 500 à 900 mots. N'ajoute aucun commentaire hors du chapitre."
    )
    prompt = (
        f"Famille : {circle['name']}\n\n"
        f"Personnages (à faire vivre par leur prénom) :\n{cast}\n\n"
        f"Souvenirs collectés :\n{material}\n\n"
        f"Écris maintenant le chapitre romancé qui relie ces souvenirs, avec chaque proche en personnage."
    )
    content = await _write_chapter_text(system, prompt, circle_id)
    content = (content or "").strip()

    title = "Chapitre de famille"
    body_text = content
    if content.startswith("#"):
        first_nl = content.find("\n")
        title = content[1:first_nl].strip().lstrip("#").strip() if first_nl != -1 else content[1:].strip()
        body_text = content[first_nl + 1:].strip() if first_nl != -1 else ""

    chapter = {
        "id": oid(),
        "circle_id": circle_id,
        "title": title or "Chapitre de famille",
        "content": body_text or content,
        "used_capsule_ids": used_ids,
        "memory_count": len(used_ids),
        "model": f"{BOOK_MODEL_PROVIDER}/{BOOK_MODEL_NAME}",
        "status": "ready",
        "created_at": now().isoformat(),
    }
    await db.book_chapters.insert_one(chapter)
    await db.events.insert_one({"id": oid(), "event_type": "chapter_generated", "circle_id": circle_id, "occurred_at": now().isoformat()})
    return chapter


# ---------------------------------------------------------------------------
# Email guardrail gate (from playbook)
# ---------------------------------------------------------------------------
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> Optional[str]:
    if RESEND_API_KEY and EMAIL_FROM_ADDRESS:
        url = "https://api.resend.com/emails"
        headers = {"Authorization": f"Bearer {RESEND_API_KEY}"}
        payload = {"from": f"{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>", "to": [to], "subject": subject, "html": html}
    elif EMAIL_KEY and INTEGRATION_PROXY_URL:
        url = f"{INTEGRATION_PROXY_URL}/api/v1/email/send"
        headers = {"X-Email-Key": EMAIL_KEY}
        payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    else:
        logger.warning("No email provider configured; skipping email")
        return None
    _assert_safe_email(subject, html)
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json().get("id") or "sent"
    except Exception as e:  # noqa
        logger.error("Email send error: %s", e)
        return None


def _invite_email_html(circle_name: str, inviter: str, code: str) -> str:
    b = escape(EMAIL_FROM_NAME)
    return (
        f'<table role="presentation" width="100%" style="background:#FFFFFF">'
        f'<tr><td style="padding:32px;font-family:Georgia,serif;color:#2F3E52">'
        f'<h1 style="color:#AE5856;font-weight:500;font-size:26px;margin:0 0 8px">Racontelle</h1>'
        f'<p style="font-size:16px">{escape(inviter)} vous invite à rejoindre le cercle '
        f'<strong>{escape(circle_name)}</strong> pour enregistrer et préserver vos souvenirs de famille.</p>'
        f'<p style="font-size:15px">Ouvrez l’application Racontelle, créez votre compte, puis '
        f'choisissez <strong>« Rejoindre »</strong> et saisissez ce code d’invitation :</p>'
        f'<p style="font-size:30px;letter-spacing:6px;color:#AE5856;font-weight:600;text-align:center;'
        f'background:#F9E6E5;border-radius:16px;padding:18px;margin:20px 0">{escape(code)}</p>'
        f'<p style="font-size:13px;color:#6F6660">Ce code expire dans 7 jours. Si vous n’êtes pas concerné(e), '
        f'ignorez simplement ce message.</p>'
        f'<p style="font-size:12px;color:#6F6660;margin-top:24px">Envoyé par {b}. '
        f'Nous ne vous demanderons jamais votre mot de passe par e-mail.</p>'
        f'</td></tr></table>'
    )


def _daily_email_html(name: str, question: str) -> str:
    b = escape(EMAIL_FROM_NAME)
    return (
        f'<table role="presentation" width="100%" style="background:#FFFFFF">'
        f'<tr><td style="padding:32px;font-family:Georgia,serif;color:#2F3E52">'
        f'<h1 style="color:#AE5856;font-weight:500;font-size:24px;margin:0 0 12px">Votre question du jour</h1>'
        f'<p style="font-size:16px">Bonjour {escape(name)},</p>'
        f'<p style="font-size:20px;font-style:italic;color:#2F3E52;line-height:1.5">« {escape(question)} »</p>'
        f'<p style="font-size:15px;color:#4E5A69">Ouvrez Racontelle pour répondre avec votre voix. '
        f'Chaque souvenir enregistré fait grandir votre arbre de famille.</p>'
        f'<p style="font-size:12px;color:#6F6660;margin-top:24px">Envoyé par {b}. '
        f'Vous pouvez désactiver ces rappels dans votre profil.</p>'
        f'</td></tr></table>'
    )


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
def oid() -> str:
    return str(ObjectId())


def member_avatar_url(member: dict) -> Optional[str]:
    """Public (token-protected) URL of a member's profile photo; the version busts phone caches on change."""
    if not member or not member.get("avatar_path"):
        return None
    version = re.sub(r"\D", "", member.get("avatar_updated_at") or "")[:14] or "1"
    return f"/api/circle/members/{member['id']}/photo?v={version}"


def clean(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    doc.pop("token_hash", None)
    if "avatar_path" in doc or ("circle_id" in doc and "display_name" in doc):
        # Family member: always expose avatar_url (null without photo), never the storage path
        doc["avatar_url"] = member_avatar_url(doc)
        doc.pop("avatar_path", None)
        doc.pop("avatar_mime", None)
    return doc


# ---------------------------------------------------------------------------
# App + auth dependency
# ---------------------------------------------------------------------------
app = FastAPI(title="Racontelle API")
api = APIRouter(prefix="/api")


@app.middleware("http")
async def reject_oversized_requests(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH"}:
        raw_length = request.headers.get("content-length")
        if raw_length:
            try:
                if int(raw_length) > MAX_REQUEST_BYTES:
                    return JSONResponse(status_code=413, content={"detail": "Requête trop volumineuse (100 Mo maximum)"})
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "En-tête Content-Length invalide"})
    return await call_next(request)


def make_token(user_id: str) -> str:
    t = now()
    return jwt.encode(
        {"sub": user_id, "iat": t, "exp": t + timedelta(days=ACCESS_DAYS)},
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None


async def user_from_token(token: str) -> Optional[dict]:
    """Active user for a JWT, rejecting tokens issued before the last password change."""
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        return None
    user = await db.users.find_one({"id": payload["sub"], "active": True})
    if not user:
        return None
    changed_at = user.get("password_changed_at")
    if changed_at and int(payload.get("iat") or 0) < int(datetime.fromisoformat(changed_at).timestamp()):
        return None
    return user


# In-memory sliding-window limiter against password/code guessing (per process; enough for one instance).
_attempts: dict = defaultdict(deque)


def rate_limit(request: Optional[Request], bucket: str, limit: int, window_sec: int, extra: str = "") -> None:
    """request=None limits on `extra` alone, whatever the IP. Client IP comes from uvicorn --proxy-headers."""
    if os.environ.get("RATE_LIMIT_DISABLED") == "1":  # automated test runs only
        return
    ip = "*" if request is None else (request.client.host if request.client else "?")
    key = f"{bucket}:{ip}:{extra}"
    t = time.monotonic()
    if len(_attempts) > 10000:
        for stale in [k for k, v in _attempts.items() if not v or v[-1] < t - 3600]:
            del _attempts[stale]
    hits = _attempts[key]
    while hits and hits[0] < t - window_sec:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(429, "Trop de tentatives. Réessayez dans quelques minutes.")
    hits.append(t)


from fastapi import Header  # noqa: E402


async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Non authentifié")
    user = await user_from_token(authorization.split(" ", 1)[1])
    if not user:
        raise HTTPException(401, "Session expirée")
    return user


async def get_member(user: dict):
    """Return the FamilyMember doc for this user (active membership)."""
    return await db.members.find_one({"user_id": user["id"], "status": "active"})


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=60)
    relationship_label: Optional[str] = Field(None, max_length=60)
    accept_terms: bool = False


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class ResetReqIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    token: str = Field(max_length=64)
    new_password: str = Field(min_length=6, max_length=128)


class FamilyProfileIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    relationship_label: str = Field(min_length=1, max_length=60)


class FamilyProfileUpdateIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    relationship_label: str = Field(min_length=1, max_length=60)


class CircleIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    initial_members: List[FamilyProfileIn] = Field(default_factory=list, max_length=3)


class InviteIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    relationship_label: Optional[str] = Field(None, max_length=60)


class JoinIn(BaseModel):
    code: str = Field(max_length=32)


class DailyStateIn(BaseModel):
    daily_question_id: str
    state: str = Field(pattern="^(viewed|skipped|answered)$")


class PreferencesIn(BaseModel):
    display_name: Optional[str] = Field(None, max_length=60)
    relationship_label: Optional[str] = Field(None, max_length=60)
    initials_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    daily_email: Optional[bool] = None


class FeedbackIn(BaseModel):
    category: str = Field(max_length=40)
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=5000)
    page_context: Optional[str] = Field(None, max_length=200)
    app_version: Optional[str] = Field(None, max_length=40)
    platform: Optional[str] = Field(None, max_length=40)


CLIENT_EVENT_TYPES = {"question_viewed", "theme_selected", "recording_started", "recording_failed"}


class ClientEventIn(BaseModel):
    event_type: str = Field(max_length=40)
    question_id: Optional[str] = Field(None, max_length=40)
    theme: Optional[str] = Field(None, max_length=80)
    source: Optional[str] = Field(None, pattern="^(daily|guided|spontaneous)$")
    error_type: Optional[str] = Field(None, max_length=40)


class DeletionRequestIn(BaseModel):
    scope: str = Field(pattern="^(account|all_family_data)$")
    comment: Optional[str] = Field(None, max_length=2000)


class QuestionImportItem(BaseModel):
    source_number: int = Field(ge=1, le=100000)
    theme: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=500)
    level: Optional[str] = Field(None, max_length=40)
    usage: Optional[str] = Field(None, max_length=80)
    tags: List[str] = Field(default_factory=list)
    sensitive: bool = False
    active: bool = True


class QuestionActiveIn(BaseModel):
    active: bool


class CapsuleUpdateIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    narrator_member_id: str


class CapsuleTranscriptIn(BaseModel):
    transcript: str = Field(min_length=1, max_length=50000)


AVATAR_COLORS = ["#C97B79", "#7F9478", "#A67C63", "#2F3E52", "#AE5856", "#6E8A8A"]  # charte Racontelle


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"message": "Racontelle API", "status": "ok"}


@api.post("/auth/register")
async def register(body: RegisterIn, request: Request):
    rate_limit(request, "register", 10, 3600)
    if body.accept_terms is not True:
        raise HTTPException(400, "Acceptez les conditions de la bêta pour créer votre compte")
    email = str(body.email).lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Un compte existe déjà avec cet e-mail")
    uid = oid()
    user = {
        "id": uid,
        "email": email,
        "password_hash": pwd_context.hash(body.password),
        "display_name": body.display_name.strip(),
        "relationship_label": body.relationship_label,
        "active": True,
        "created_at": now().isoformat(),
        "last_login_at": now().isoformat(),
    }
    await db.users.insert_one(user)
    await db.consents.insert_one(
        {"id": oid(), "user_id": uid, "consent_type": "cgu_beta", "accepted": True, "version": CONSENT_VERSION, "occurred_at": now().isoformat()}
    )
    await db.events.insert_one({"id": oid(), "event_type": "account_created", "user_id": uid, "occurred_at": now().isoformat()})
    return {"access_token": make_token(uid), "user": clean(user)}


@api.post("/auth/login")
async def login(body: LoginIn, request: Request):
    email = str(body.email).lower()
    rate_limit(request, "login", 10, 900, extra=email)
    rate_limit(None, "login-account", 30, 900, extra=email)
    user = await db.users.find_one({"email": email})
    if not user or not pwd_context.verify(body.password, user["password_hash"]):
        raise HTTPException(401, "E-mail ou mot de passe incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now().isoformat()}})
    return {"access_token": make_token(user["id"]), "user": clean(user)}


@api.post("/auth/request-reset")
async def request_reset(body: ResetReqIn, request: Request):
    rate_limit(request, "request-reset", 5, 3600)
    user = await db.users.find_one({"email": str(body.email).lower()})
    if user:
        # Short code delivered by e-mail; only its hash is stored.
        code = new_invite_code()
        await db.reset_tokens.insert_one(
            {"id": oid(), "token_hash": sha(code), "user_id": user["id"], "used": False,
             "expires_at": (now() + timedelta(minutes=RESET_MIN)).isoformat()}
        )
        html = (
            f'<table role="presentation" width="100%" style="background:#FFFFFF"><tr>'
            f'<td style="padding:32px;font-family:Georgia,serif;color:#2F3E52">'
            f'<h1 style="color:#AE5856;font-weight:500">Réinitialisation</h1>'
            f'<p>Votre code de réinitialisation Racontelle :</p>'
            f'<p style="font-size:28px;letter-spacing:5px;color:#AE5856;font-weight:600">{escape(code)}</p>'
            f'<p style="font-size:12px;color:#6F6660">Ce code expire dans 30 minutes. '
            f'Envoyé par {escape(EMAIL_FROM_NAME)}.</p></td></tr></table>'
        )
        await send_email(to=user["email"], subject="Réinitialisation de votre mot de passe", html=html)
    return {"message": "Si l’e-mail existe, un code de réinitialisation a été envoyé."}


@api.post("/auth/reset-password")
async def reset_password(body: ResetConfirmIn, request: Request):
    rate_limit(request, "reset-password", 10, 900)
    rate_limit(None, "reset-password-all", 100, 900)
    token_doc = await db.reset_tokens.find_one({"token_hash": sha(body.token.strip().upper()), "used": False})
    if not token_doc or token_doc["expires_at"] < now().isoformat():
        raise HTTPException(400, "Code invalide ou expiré")
    # password_changed_at invalidates every session opened before the reset (see user_from_token)
    await db.users.update_one({"id": token_doc["user_id"]}, {"$set": {
        "password_hash": pwd_context.hash(body.new_password), "password_changed_at": now().isoformat()}})
    await db.reset_tokens.update_one({"id": token_doc["id"]}, {"$set": {"used": True}})
    return {"message": "Mot de passe réinitialisé"}


@api.post("/auth/refresh")
async def refresh_token(user=Depends(get_current_user)):
    """Sliding session: a still-valid token is exchanged for a fresh 30-day one at each app launch."""
    return {"access_token": make_token(user["id"])}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    member = await get_member(user)
    return {"user": clean(user), "member": clean(member) if member else None, "has_circle": bool(member)}


# ---------------------------------------------------------------------------
# Circle routes
# ---------------------------------------------------------------------------
@api.post("/circles")
async def create_circle(body: CircleIn, user=Depends(get_current_user)):
    existing = await get_member(user)
    if existing:
        raise HTTPException(400, "Vous appartenez déjà à un cercle")
    cid = oid()
    circle = {"id": cid, "name": body.name.strip(), "owner_user_id": user["id"],
              "timezone": "Europe/Paris", "status": "active", "created_at": now().isoformat()}
    await db.circles.insert_one(circle)
    member = {"id": oid(), "circle_id": cid, "user_id": user["id"],
              "display_name": user["display_name"], "relationship_label": user.get("relationship_label"),
              "initials_color": AVATAR_COLORS[0], "status": "active", "role": "owner",
              "daily_email": True, "created_at": now().isoformat()}
    await db.members.insert_one(member)
    created_profiles = []
    for index, profile in enumerate(body.initial_members[:3], start=1):
        direct_member = {
            "id": oid(), "circle_id": cid, "user_id": None,
            "display_name": profile.display_name.strip(),
            "relationship_label": profile.relationship_label.strip(),
            "initials_color": AVATAR_COLORS[index % len(AVATAR_COLORS)],
            "status": "active", "role": "profile", "daily_email": False,
            "managed_profile": True, "created_at": now().isoformat(),
        }
        await db.members.insert_one(direct_member)
        created_profiles.append(clean(direct_member))
    await db.events.insert_one({"id": oid(), "event_type": "circle_created", "circle_id": cid, "user_id": user["id"], "occurred_at": now().isoformat()})
    return {"circle": clean(circle), "member": clean(member), "profiles": created_profiles}


async def circle_summary(circle_id: str) -> dict:
    circle = await db.circles.find_one({"id": circle_id})
    members = await db.members.find({"circle_id": circle_id, "status": {"$ne": "revoked"}}).to_list(100)
    capsule_count = await db.capsules.count_documents({"circle_id": circle_id, "status": "saved"})
    total_seconds = 0
    async for c in db.capsules.find({"circle_id": circle_id, "status": "saved"}, {"duration_sec": 1}):
        total_seconds += int(c.get("duration_sec") or 0)
    return {
        "circle": clean(circle),
        "members": [clean(m) for m in members],
        "member_count": len([m for m in members if m["status"] == "active"]),
        "capsule_count": capsule_count,
        "total_seconds": total_seconds,
        "tree_level": tree_level(capsule_count),
    }


def tree_level(count: int) -> dict:
    # Growing tree stages driven by number of saved capsules.
    milestones = [0, 1, 3, 6, 10, 15, 21, 30, 45, 60]
    level = 0
    for i, m in enumerate(milestones):
        if count >= m:
            level = i
    next_at = milestones[level + 1] if level + 1 < len(milestones) else None
    return {"level": level, "max_level": len(milestones) - 1, "count": count, "next_at": next_at}


@api.get("/circle")
async def get_circle(user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    return await circle_summary(member["circle_id"])


@api.get("/circle/members")
async def list_members(user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    members = await db.members.find({"circle_id": member["circle_id"], "status": {"$ne": "revoked"}}).to_list(100)
    stats = await db.capsules.aggregate([
        {"$match": {"circle_id": member["circle_id"], "status": "saved"}},
        {"$group": {"_id": "$narrator_member_id", "capsule_count": {"$sum": 1},
                    "total_seconds": {"$sum": {"$ifNull": ["$duration_sec", 0]}}}},
    ]).to_list(100)
    stats_by_member = {item["_id"]: item for item in stats}
    out = []
    for m in members:
        m = clean(m)
        member_stats = stats_by_member.get(m["id"], {})
        m["capsule_count"] = int(member_stats.get("capsule_count") or 0)
        m["total_seconds"] = int(member_stats.get("total_seconds") or 0)
        out.append(m)
    return out


@api.post("/circle/members")
async def create_direct_member(body: FamilyProfileIn, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member or member.get("role") != "owner":
        raise HTTPException(403, "Seul le créateur du cercle peut ajouter un profil")
    circle_id = member["circle_id"]
    current_count = await db.members.count_documents({"circle_id": circle_id, "status": "active", "role": {"$in": ["owner", "profile"]}})
    if current_count >= 4:
        raise HTTPException(400, "À partir du 5e membre, utilisez une invitation par e-mail")
    profile = {
        "id": oid(), "circle_id": circle_id, "user_id": None,
        "display_name": body.display_name.strip(),
        "relationship_label": body.relationship_label.strip(),
        "initials_color": AVATAR_COLORS[current_count % len(AVATAR_COLORS)],
        "status": "active", "role": "profile", "daily_email": False,
        "managed_profile": True, "created_at": now().isoformat(),
    }
    await db.members.insert_one(profile)
    await db.events.insert_one({"id": oid(), "event_type": "direct_profile_created", "circle_id": circle_id,
                                "member_id": profile["id"], "user_id": user["id"], "occurred_at": now().isoformat()})
    return clean(profile)


@api.patch("/circle/members/{member_id}")
async def update_direct_member(member_id: str, body: FamilyProfileUpdateIn, user=Depends(get_current_user)):
    owner = await get_member(user)
    if not owner or owner.get("role") != "owner":
        raise HTTPException(403, "Action non autorisée")
    profile = await db.members.find_one({"id": member_id, "circle_id": owner["circle_id"], "status": "active"})
    if not profile or profile.get("user_id") or profile.get("role") == "owner":
        raise HTTPException(400, "Seuls les profils sans compte peuvent être modifiés")
    updates = {"display_name": body.display_name.strip(), "relationship_label": body.relationship_label.strip(),
               "updated_at": now().isoformat()}
    await db.members.update_one({"id": member_id}, {"$set": updates})
    updated = await db.members.find_one({"id": member_id}, {"_id": 0})
    return clean(updated)


@api.delete("/circle/members/{member_id}")
async def delete_direct_member(member_id: str, user=Depends(get_current_user)):
    owner = await get_member(user)
    if not owner or owner.get("role") != "owner":
        raise HTTPException(403, "Action non autorisée")
    profile = await db.members.find_one({"id": member_id, "circle_id": owner["circle_id"], "status": "active"})
    if not profile or profile.get("user_id") or profile.get("role") == "owner":
        raise HTTPException(400, "Seuls les profils sans compte peuvent être supprimés")
    memories = await db.capsules.count_documents({"circle_id": owner["circle_id"], "narrator_member_id": member_id, "status": "saved"})
    if memories:
        raise HTTPException(400, "Rattachez d’abord les souvenirs de ce profil à un autre membre")
    await db.members.update_one({"id": member_id}, {"$set": {"status": "revoked", "deleted_at": now().isoformat()}})
    await db.events.insert_one({"id": oid(), "event_type": "direct_profile_deleted", "circle_id": owner["circle_id"],
                                "member_id": member_id, "user_id": user["id"], "occurred_at": now().isoformat()})
    return {"ok": True}


@api.post("/circle/invitations")
async def create_invitation(body: InviteIn, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member or member.get("role") != "owner":
        raise HTTPException(403, "Seul le créateur du cercle peut inviter")
    circle_id = member["circle_id"]
    current_count = await db.members.count_documents({"circle_id": circle_id, "status": "active", "role": {"$in": ["owner", "profile"]}})
    if current_count < 4:
        raise HTTPException(400, "Créez d’abord vos 4 profils familiaux, puis invitez les membres suivants par e-mail")
    circle = await db.circles.find_one({"id": circle_id})
    # create pending member profile
    new_member = {"id": oid(), "circle_id": circle_id, "user_id": None,
                  "display_name": body.display_name.strip(), "relationship_label": body.relationship_label,
                  "initials_color": AVATAR_COLORS[(await db.members.count_documents({"circle_id": circle_id})) % len(AVATAR_COLORS)],
                  "status": "pending", "role": "member", "daily_email": True, "created_at": now().isoformat()}
    await db.members.insert_one(new_member)
    code = new_invite_code()
    # Only the hash is stored (RG-03): the code itself exists in the e-mail and in this one response.
    invite = {"id": oid(), "circle_id": circle_id, "member_id": new_member["id"], "email": str(body.email).lower(),
              "token_hash": sha(code), "status": "sent",
              "expires_at": (now() + timedelta(days=7)).isoformat(), "sent_at": now().isoformat(), "accepted_at": None}
    await db.invitations.insert_one(invite)
    sent = await send_email(to=str(body.email).lower(), subject=f"{user['display_name']} vous invite sur Racontelle",
                            html=_invite_email_html(circle["name"], user["display_name"], code))
    await log_event("invite_sent" if sent else "invite_email_failed", circle_id=circle_id, member_id=new_member["id"],
                    user_id=user["id"])
    return {"member": clean(new_member), "invitation": clean(invite), "code": code}


@api.get("/circle/invitations")
async def list_invitations(user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    docs = await db.invitations.find({"circle_id": member["circle_id"], "status": {"$in": ["sent"]}}).sort("sent_at", -1).to_list(100)
    out = [clean(d) for d in docs]
    for d in out:
        d.pop("code", None)  # legacy plaintext codes from invitations created before hashing
    return out


@api.post("/circle/invitations/{invite_id}/resend")
async def resend_invitation(invite_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member or member.get("role") != "owner":
        raise HTTPException(403, "Action non autorisée")
    invite = await db.invitations.find_one({"id": invite_id, "circle_id": member["circle_id"], "status": {"$in": ["sent", "expired"]}})
    if not invite:
        raise HTTPException(404, "Invitation introuvable")
    circle = await db.circles.find_one({"id": member["circle_id"]})
    # The stored hash cannot be reversed, so a resend issues a fresh code valid 7 days; the old one stops working.
    code = new_invite_code()
    await db.invitations.update_one({"id": invite_id}, {
        "$set": {"token_hash": sha(code), "status": "sent", "sent_at": now().isoformat(),
                 "expires_at": (now() + timedelta(days=7)).isoformat()},
        "$unset": {"code": ""}})
    sent = await send_email(to=invite["email"], subject="Rappel : invitation Racontelle",
                            html=_invite_email_html(circle["name"], user["display_name"], code))
    await log_event("invite_resent" if sent else "invite_email_failed", circle_id=member["circle_id"],
                    member_id=invite["member_id"], user_id=user["id"])
    return {"ok": True, "code": code}


@api.delete("/circle/invitations/{invite_id}")
async def revoke_invitation(invite_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member or member.get("role") != "owner":
        raise HTTPException(403, "Action non autorisée")
    invite = await db.invitations.find_one({"id": invite_id, "circle_id": member["circle_id"]})
    if not invite:
        raise HTTPException(404, "Invitation introuvable")
    await db.invitations.update_one({"id": invite_id}, {"$set": {"status": "revoked"}, "$unset": {"code": ""}})
    await db.members.update_one({"id": invite["member_id"], "status": "pending"}, {"$set": {"status": "revoked"}})
    await log_event("invite_revoked", circle_id=member["circle_id"], member_id=invite["member_id"], user_id=user["id"])
    return {"ok": True}


@api.post("/invitations/accept")
async def accept_invitation(body: JoinIn, request: Request, user=Depends(get_current_user)):
    rate_limit(request, "accept-invite", 10, 900, extra=user["id"])
    if await get_member(user):
        raise HTTPException(400, "Vous appartenez déjà à un cercle")
    code = body.code.strip().upper()
    invite = await db.invitations.find_one({"token_hash": sha(code), "status": "sent"})
    if not invite:
        raise HTTPException(404, "Code d’invitation invalide")
    if invite["expires_at"] < now().isoformat():
        await db.invitations.update_one({"id": invite["id"]}, {"$set": {"status": "expired"}})
        raise HTTPException(400, "Ce code d’invitation a expiré")
    await db.members.update_one(
        {"id": invite["member_id"]},
        {"$set": {"user_id": user["id"], "status": "active", "display_name": user["display_name"]}},
    )
    await db.invitations.update_one({"id": invite["id"]}, {"$set": {"status": "accepted", "accepted_at": now().isoformat()},
                                                           "$unset": {"code": ""}})
    await db.events.insert_one({"id": oid(), "event_type": "invite_accepted", "circle_id": invite["circle_id"], "member_id": invite["member_id"], "occurred_at": now().isoformat()})
    return await circle_summary(invite["circle_id"])


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
@api.get("/themes")
async def list_themes(user=Depends(get_current_user)):
    out = []
    for t in THEMES_ORDER:
        doc = await db.questions.find_one({"theme": t, "sensitive": False})
        if not doc:
            continue
        count = await db.questions.count_documents({"theme": t, "sensitive": False, "active": True})
        out.append({"theme": t, "question_count": count})
    return out


@api.get("/questions")
async def list_questions(theme: Optional[str] = None, user=Depends(get_current_user)):
    q = {"sensitive": False, "active": True}
    if theme:
        q["theme"] = theme
    docs = await db.questions.find(q).sort("source_number", 1).to_list(500)
    return [clean(d) for d in docs]


@api.get("/questions/surprise")
async def surprise_question(theme: Optional[str] = None, user=Depends(get_current_user)):
    match = {"sensitive": False, "active": True}
    if theme:
        match["theme"] = theme
    docs = await db.questions.aggregate([{"$match": match}, {"$sample": {"size": 1}}]).to_list(1)
    if not docs:
        raise HTTPException(404, "Aucune question")
    return clean(docs[0])


# ---------------------------------------------------------------------------
# Daily questions (up to 3 per circle per day)
# ---------------------------------------------------------------------------
DAILY_COUNT = 3


async def ensure_daily(circle_id: str) -> List[dict]:
    local_date = paris_today()
    existing = await db.daily_questions.find({"circle_id": circle_id, "local_date": local_date}).to_list(10)
    if len(existing) >= DAILY_COUNT:
        return existing
    used_ids = [d["question_id"] for d in await db.daily_questions.find({"circle_id": circle_id}, {"question_id": 1}).to_list(5000)]
    used_today_themes = [d.get("theme") for d in existing]
    yesterday = (now().astimezone(TZ_PARIS).date() - timedelta(days=1)).isoformat()
    yesterday_themes = {d.get("theme") for d in await db.daily_questions.find(
        {"circle_id": circle_id, "local_date": yesterday}, {"theme": 1}).to_list(10)}
    need = DAILY_COUNT - len(existing)
    # Never repeat a question until the active stock is exhausted (RG-09).
    pipeline = [{"$match": {"sensitive": False, "active": True, "id": {"$nin": used_ids}}}, {"$sample": {"size": 60}}]
    candidates = await db.questions.aggregate(pipeline).to_list(60)
    if not candidates:
        pipeline = [{"$match": {"sensitive": False, "active": True}}, {"$sample": {"size": 60}}]
        candidates = await db.questions.aggregate(pipeline).to_list(60)
    picked = []
    # Prefer themes used neither today nor yesterday (RG-10), then relax the rule if the stock is too thin.
    for avoid_yesterday in (True, False):
        for c in candidates:
            if len(picked) >= need:
                break
            if c in picked or c["theme"] in used_today_themes:
                continue
            if avoid_yesterday and c["theme"] in yesterday_themes:
                continue
            used_today_themes.append(c["theme"])
            picked.append(c)
    for c in candidates:
        if len(picked) >= need:
            break
        if c not in picked:
            picked.append(c)
    for slot, c in enumerate(picked[:need], start=len(existing)):
        dq = {"id": oid(), "circle_id": circle_id, "question_id": c["id"], "theme": c["theme"],
              "local_date": local_date, "slot": slot, "generated_at": now().isoformat()}
        try:
            await db.daily_questions.insert_one(dq)
        except DuplicateKeyError:
            break  # a concurrent request already filled this slot
    return await db.daily_questions.find({"circle_id": circle_id, "local_date": local_date}).sort("generated_at", 1).to_list(10)


@api.get("/daily-question")
async def get_daily(user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    dailies = await ensure_daily(member["circle_id"])
    out = []
    for dq in dailies:
        question = await db.questions.find_one({"id": dq["question_id"]})
        state = await db.daily_states.find_one({"daily_question_id": dq["id"], "member_id": member["id"]})
        answered_count = await db.capsules.count_documents({"daily_question_id": dq["id"], "status": "saved"})
        out.append({
            "daily_question_id": dq["id"],
            "question": clean(question) if question else None,
            "theme": dq["theme"],
            "my_state": state["state"] if state else "new",
            "answered_count": answered_count,
        })
    return {"date": paris_today(), "items": out}


@api.patch("/daily-question/state")
async def set_daily_state(body: DailyStateIn, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    dq = await db.daily_questions.find_one({"id": body.daily_question_id, "circle_id": member["circle_id"]})
    if not dq:
        raise HTTPException(404, "Question du jour introuvable")
    previous = await db.daily_states.find_one({"daily_question_id": body.daily_question_id, "member_id": member["id"]})
    if body.state == "viewed" and previous:
        return {"ok": True}  # never downgrade skipped/answered back to viewed
    await db.daily_states.update_one(
        {"daily_question_id": body.daily_question_id, "member_id": member["id"]},
        {"$set": {"state": body.state, "updated_at": now().isoformat(), "circle_id": member["circle_id"]},
         "$setOnInsert": {"id": oid()}},
        upsert=True,
    )
    if body.state == "skipped":
        await log_event("question_skipped", circle_id=member["circle_id"], member_id=member["id"], question_id=dq["question_id"])
    elif body.state == "viewed":
        await log_event("question_viewed", circle_id=member["circle_id"], member_id=member["id"],
                        question_id=dq["question_id"], source="daily")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Capsules (audio memories)
# ---------------------------------------------------------------------------
def _detect_image(data: bytes) -> Optional[tuple[str, str]]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}:
        return "image/heic", "heic"
    return None


def _detect_audio(data: bytes) -> Optional[tuple[str, str]]:
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav", "wav"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm", "webm"
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return "audio/mpeg", "mp3"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "audio/mp4", "m4a"
    return None


async def _read_limited(upload: UploadFile, maximum: int, label: str) -> bytes:
    data = await upload.read(maximum + 1)
    if len(data) > maximum:
        raise HTTPException(413, f"{label} trop volumineux")
    if not data:
        raise HTTPException(400, f"{label} vide")
    return data


async def _validated_photo(upload: UploadFile) -> tuple[bytes, str, str]:
    data = await _read_limited(upload, MAX_PHOTO_BYTES, "Photo")
    detected = _detect_image(data)
    if not detected:
        raise HTTPException(415, "Format photo non pris en charge (JPEG, PNG, WebP ou HEIC uniquement)")
    mime, ext = detected
    return data, mime, ext


async def _store_photo(circle_id: str, capsule_id: str, data: bytes, mime: str, ext: str) -> Optional[dict]:
    pid = oid()
    path = f"{APP_NAME}/photos/{circle_id}/{capsule_id}/{pid}.{ext}"
    try:
        await run_in_threadpool(put_object, path, data, mime)
    except StorageError:
        return None
    return {"id": pid, "path": path, "mime": mime, "created_at": now().isoformat()}


def _capsule_photos(c: dict) -> List[dict]:
    """Normalized photo list (supports legacy single photo_path)."""
    items = list(c.get("photos") or [])
    if not items and c.get("photo_path"):
        items = [{"id": "legacy", "path": c["photo_path"], "mime": c.get("photo_mime") or "image/jpeg"}]
    return items


@api.post("/capsules")
async def create_capsule(
    background_tasks: BackgroundTasks,
    narrator_member_id: str = Form(...),
    duration_sec: int = Form(...),
    question_id: Optional[str] = Form(None),
    daily_question_id: Optional[str] = Form(None),
    theme: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    transcript: Optional[str] = Form(None),
    file: UploadFile = File(...),
    photos: List[UploadFile] = File(default=[]),
    user=Depends(get_current_user),
):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    if duration_sec < 1 or duration_sec > MAX_AUDIO_DURATION_SEC:
        raise HTTPException(422, "La durée doit être comprise entre 1 seconde et 2 heures")
    if len(photos) > MAX_PHOTOS_PER_CAPSULE:
        raise HTTPException(413, "10 photos maximum par souvenir")
    narrator = await db.members.find_one({"id": narrator_member_id, "circle_id": member["circle_id"],
                                          "status": {"$ne": "revoked"}})
    if not narrator:
        raise HTTPException(400, "Narrateur invalide")
    if daily_question_id and not await db.daily_questions.find_one({"id": daily_question_id, "circle_id": member["circle_id"]}):
        raise HTTPException(400, "Question du jour invalide")
    title = (title or "").strip()[:120] or None
    theme = (theme or "").strip()[:80] or None
    data = await _read_limited(file, MAX_AUDIO_BYTES, "Fichier audio")
    audio_type = _detect_audio(data)
    if not audio_type:
        raise HTTPException(415, "Format audio non pris en charge (M4A, MP3, WAV ou WebM uniquement)")
    ctype, ext = audio_type
    validated_photos = []
    total_bytes = len(data)
    for upload in photos:
        photo_data, photo_mime, photo_ext = await _validated_photo(upload)
        total_bytes += len(photo_data)
        if total_bytes > MAX_REQUEST_BYTES:
            raise HTTPException(413, "Requête trop volumineuse (100 Mo maximum)")
        validated_photos.append((photo_data, photo_mime, photo_ext))
    cid = oid()
    path = f"{APP_NAME}/uploads/{member['circle_id']}/{cid}.{ext}"
    try:
        await run_in_threadpool(put_object, path, data, ctype)
    except StorageError as e:
        if e.status_code == 402:
            raise HTTPException(402, "Stockage plein — impossible d’enregistrer pour le moment")
        raise HTTPException(500, "Échec de l’enregistrement audio")

    photos_list = []
    for photo_data, photo_mime, photo_ext in validated_photos:
        stored = await _store_photo(member["circle_id"], cid, photo_data, photo_mime, photo_ext)
        if stored:
            photos_list.append(stored)

    manual_transcript = (transcript or "").strip()
    capsule = {
        "id": cid, "circle_id": member["circle_id"], "narrator_member_id": narrator_member_id,
        "recorded_by_user_id": user["id"], "question_id": question_id, "daily_question_id": daily_question_id,
        "theme": theme, "title": title or ("Souvenir sur le vif" if not question_id else None), "storage_path": path, "mime_type": ctype,
        "photos": photos_list, "photo_path": None, "photo_mime": None,
        "duration_sec": duration_sec, "recorded_at": now().isoformat(), "created_at": now().isoformat(),
        "status": "saved", "transcript": manual_transcript or None,
        "transcript_status": "done" if manual_transcript else ("pending" if STT_API_KEY else "unavailable"),
    }
    await db.capsules.insert_one(capsule)
    if not manual_transcript and STT_API_KEY:
        background_tasks.add_task(transcribe_capsule, cid, path, ext)
    if daily_question_id:
        await db.daily_states.update_one(
            {"daily_question_id": daily_question_id, "member_id": member["id"]},
            {"$set": {"state": "answered", "updated_at": now().isoformat(), "id": oid(), "circle_id": member["circle_id"]}},
            upsert=True,
        )
    await log_event("recording_saved", capsule_id=cid, circle_id=member["circle_id"], member_id=member["id"],
                    narrator_member_id=narrator_member_id, question_id=question_id, duration_sec=duration_sec,
                    source="daily" if daily_question_id else ("guided" if question_id else "spontaneous"))
    return await _enrich_capsule(capsule)


async def _enrich_capsule(
    c: dict,
    members_by_id: Optional[dict] = None,
    questions_by_id: Optional[dict] = None,
) -> dict:
    c = clean(c)
    narrator = members_by_id.get(c["narrator_member_id"]) if members_by_id is not None else await db.members.find_one(
        {"id": c["narrator_member_id"]}, {"_id": 0}
    )
    if narrator:
        c["narrator_name"] = narrator["display_name"]
        c["narrator_color"] = narrator.get("initials_color")
        c["narrator_avatar_url"] = member_avatar_url(narrator)
    q = questions_by_id.get(c.get("question_id")) if questions_by_id is not None else (
        await db.questions.find_one({"id": c.get("question_id")}, {"_id": 0}) if c.get("question_id") else None
    )
    c["question_text"] = q["text"] if q else c.get("title")
    c["audio_url"] = f"/api/capsules/{c['id']}/audio"
    photos = _capsule_photos(c)
    c["photos"] = [{"id": p["id"], "url": f"/api/capsules/{c['id']}/photos/{p['id']}"} for p in photos]
    c["photo_url"] = c["photos"][0]["url"] if c["photos"] else None
    return c


@api.get("/capsules")
async def list_capsules(narrator: Optional[str] = None, theme: Optional[str] = None, q: Optional[str] = None, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    query = {"circle_id": member["circle_id"], "status": "saved"}
    if narrator:
        query["narrator_member_id"] = narrator
    if theme:
        query["theme"] = theme
    docs = await db.capsules.find(query).sort("recorded_at", -1).to_list(1000)
    member_ids = list({doc["narrator_member_id"] for doc in docs if doc.get("narrator_member_id")})
    question_ids = list({doc["question_id"] for doc in docs if doc.get("question_id")})
    members = await db.members.find(
        {"id": {"$in": member_ids}},
        {"_id": 0, "id": 1, "display_name": 1, "initials_color": 1, "avatar_path": 1, "avatar_updated_at": 1},
    ).to_list(len(member_ids)) if member_ids else []
    questions = await db.questions.find(
        {"id": {"$in": question_ids}},
        {"_id": 0, "id": 1, "text": 1},
    ).to_list(len(question_ids)) if question_ids else []
    members_by_id = {item["id"]: item for item in members}
    questions_by_id = {item["id"]: item for item in questions}
    enriched = [await _enrich_capsule(doc, members_by_id, questions_by_id) for doc in docs]
    term = (q or "").strip().lower()
    if term:
        def matches(c: dict) -> bool:
            haystack = " ".join(
                str(c.get(k) or "")
                for k in ("question_text", "title", "theme", "narrator_name", "transcript")
            ).lower()
            return term in haystack
        enriched = [c for c in enriched if matches(c)]
    return enriched


@api.get("/capsules/{capsule_id}")
async def get_capsule(capsule_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    return await _enrich_capsule(c)


@api.patch("/capsules/{capsule_id}")
async def update_capsule(capsule_id: str, body: CapsuleUpdateIn, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    capsule = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not capsule:
        raise HTTPException(404, "Souvenir introuvable")
    if capsule.get("question_id"):
        raise HTTPException(400, "Seuls les souvenirs Sur le vif peuvent être renommés")
    if capsule.get("recorded_by_user_id") != user["id"] and member.get("role") != "owner":
        raise HTTPException(403, "Vous ne pouvez modifier que vos souvenirs")
    narrator = await db.members.find_one({"id": body.narrator_member_id, "circle_id": member["circle_id"], "status": "active"})
    if not narrator:
        raise HTTPException(400, "Profil familial invalide")
    await db.capsules.update_one(
        {"id": capsule_id},
        {"$set": {"title": body.title.strip(), "narrator_member_id": body.narrator_member_id,
                  "updated_at": now().isoformat()}},
    )
    await db.events.insert_one({"id": oid(), "event_type": "capsule_updated", "capsule_id": capsule_id,
                                "circle_id": member["circle_id"], "user_id": user["id"], "occurred_at": now().isoformat()})
    updated = await db.capsules.find_one({"id": capsule_id}, {"_id": 0})
    return await _enrich_capsule(updated)


@api.patch("/capsules/{capsule_id}/transcript")
async def update_capsule_transcript(capsule_id: str, body: CapsuleTranscriptIn, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    capsule = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not capsule:
        raise HTTPException(404, "Souvenir introuvable")
    if capsule.get("recorded_by_user_id") != user["id"] and member.get("role") != "owner":
        raise HTTPException(403, "Vous ne pouvez modifier que vos souvenirs")
    transcript = body.transcript.strip()
    await db.capsules.update_one(
        {"id": capsule_id},
        {"$set": {"transcript": transcript, "transcript_status": "done", "updated_at": now().isoformat()}},
    )
    updated = await db.capsules.find_one({"id": capsule_id}, {"_id": 0})
    return await _enrich_capsule(updated)


async def _media_member(token: str) -> dict:
    user = await user_from_token(token)
    if not user:
        raise HTTPException(401, "Non autorisé")
    member = await db.members.find_one({"user_id": user["id"], "status": "active"})
    if not member:
        raise HTTPException(403, "Accès refusé")
    return member


def _byte_range(range_header: Optional[str], size: int) -> Optional[tuple[int, int]]:
    """Parse a single 'bytes=a-b' range. iOS players require 206 answers to play audio."""
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", (range_header or "").strip())
    if not m or (not m.group(1) and not m.group(2)):
        return None
    if m.group(1):
        start = int(m.group(1))
        end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
    else:
        start = max(size - int(m.group(2)), 0)
        end = size - 1
    if start > end or start >= size:
        raise HTTPException(416, "Plage invalide", headers={"Content-Range": f"bytes */{size}"})
    return start, end


@api.get("/capsules/{capsule_id}/audio")
async def stream_audio(capsule_id: str, request: Request, token: str = Query(...)):
    member = await _media_member(token)
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    rng_header = request.headers.get("range")
    if not rng_header or rng_header.strip() in ("bytes=0-", "bytes=0-1"):
        await db.events.insert_one({"id": oid(), "event_type": "capsule_played", "capsule_id": capsule_id,
                                    "user_id": member["user_id"], "occurred_at": now().isoformat()})
    try:
        content, _ = await run_in_threadpool(get_object, c["storage_path"])
    except Exception:
        raise HTTPException(404, "Audio indisponible")
    safe_audio_type = {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".webm": "audio/webm"}.get(Path(c["storage_path"]).suffix.lower(), "application/octet-stream")
    headers = {
        "Accept-Ranges": "bytes", "Cache-Control": "no-store, no-cache, must-revalidate",
        "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline; filename=\"souvenir-audio\"",
    }
    rng = _byte_range(rng_header, len(content))
    if rng:
        start, end = rng
        headers["Content-Range"] = f"bytes {start}-{end}/{len(content)}"
        return Response(content=content[start:end + 1], status_code=206, media_type=safe_audio_type, headers=headers)
    return Response(content=content, media_type=safe_audio_type, headers=headers)


@api.delete("/capsules/{capsule_id}")
async def delete_capsule(capsule_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"]})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    if c["recorded_by_user_id"] != user["id"] and member.get("role") != "owner":
        raise HTTPException(403, "Vous ne pouvez supprimer que vos souvenirs")
    await db.capsules.update_one({"id": capsule_id}, {"$set": {"status": "deleted", "deleted_at": now().isoformat()}})
    await db.events.insert_one({"id": oid(), "event_type": "capsule_deleted", "capsule_id": capsule_id, "user_id": user["id"], "occurred_at": now().isoformat()})
    return {"ok": True}


@api.post("/capsules/{capsule_id}/transcribe")
async def retranscribe_capsule(capsule_id: str, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    if not STT_API_KEY:
        raise HTTPException(503, "Transcription automatique temporairement indisponible. Ajoutez le texte du souvenir manuellement.")
    ext = Path(c["storage_path"]).suffix.lstrip(".") or "m4a"
    await db.capsules.update_one({"id": capsule_id}, {"$set": {"transcript_status": "pending"}})
    background_tasks.add_task(transcribe_capsule, capsule_id, c["storage_path"], ext)
    return {"ok": True, "transcript_status": "pending"}


# ---------------------------------------------------------------------------
# Capsule photos (multiple per memory)
# ---------------------------------------------------------------------------
@api.post("/capsules/{capsule_id}/photos")
async def add_capsule_photos(capsule_id: str, photos: List[UploadFile] = File(...), user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    if not photos:
        raise HTTPException(400, "Sélectionnez au moins une photo")
    existing_count = len(_capsule_photos(c))
    if len(photos) > MAX_PHOTOS_PER_CAPSULE or existing_count + len(photos) > MAX_PHOTOS_PER_CAPSULE:
        raise HTTPException(413, "10 photos maximum par souvenir")
    validated_photos = []
    total_bytes = 0
    for upload in photos:
        photo_data, photo_mime, photo_ext = await _validated_photo(upload)
        total_bytes += len(photo_data)
        if total_bytes > MAX_REQUEST_BYTES:
            raise HTTPException(413, "Requête trop volumineuse (100 Mo maximum)")
        validated_photos.append((photo_data, photo_mime, photo_ext))
    added = []
    for photo_data, photo_mime, photo_ext in validated_photos:
        stored = await _store_photo(member["circle_id"], capsule_id, photo_data, photo_mime, photo_ext)
        if stored:
            added.append(stored)
    if not added:
        raise HTTPException(400, "Aucune image valide")
    await db.capsules.update_one({"id": capsule_id}, {"$push": {"photos": {"$each": added}}})
    updated = await db.capsules.find_one({"id": capsule_id})
    return await _enrich_capsule(updated)


@api.delete("/capsules/{capsule_id}/photos/{photo_id}")
async def delete_capsule_photo(capsule_id: str, photo_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    if c.get("recorded_by_user_id") != user["id"] and member.get("role") != "owner":
        raise HTTPException(403, "Vous ne pouvez modifier que vos souvenirs")
    if photo_id == "legacy":
        await db.capsules.update_one({"id": capsule_id}, {"$set": {"photo_path": None, "photo_mime": None}})
    else:
        await db.capsules.update_one({"id": capsule_id}, {"$pull": {"photos": {"id": photo_id}}})
    updated = await db.capsules.find_one({"id": capsule_id})
    return await _enrich_capsule(updated)


@api.get("/capsules/{capsule_id}/photos/{photo_id}")
async def stream_photo(capsule_id: str, photo_id: str, token: str = Query(...)):
    member = await _media_member(token)
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    photo = next((p for p in _capsule_photos(c) if p["id"] == photo_id), None)
    if not photo:
        raise HTTPException(404, "Photo introuvable")
    try:
        content, _ = await run_in_threadpool(get_object, photo["path"])
    except Exception:
        raise HTTPException(404, "Photo indisponible")
    safe_photo_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heif"}.get(Path(photo["path"]).suffix.lower(), "application/octet-stream")
    return Response(content=content, media_type=safe_photo_type, headers={
        "Cache-Control": "no-store, no-cache, must-revalidate", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline; filename=\"souvenir-photo\"",
    })


# ---------------------------------------------------------------------------
# Member profile photos (one per family member, shown instead of the initials)
# ---------------------------------------------------------------------------
async def _photo_target(member_id: str, user: dict) -> tuple[dict, dict]:
    """The caller may change their own photo; the circle owner may change anyone's (profiles without accounts)."""
    me = await get_member(user)
    if not me:
        raise HTTPException(404, "Aucun cercle")
    target = await db.members.find_one({"id": member_id, "circle_id": me["circle_id"], "status": {"$ne": "revoked"}})
    if not target:
        raise HTTPException(404, "Membre introuvable")
    if target["id"] != me["id"] and me.get("role") != "owner":
        raise HTTPException(403, "Seul le créateur du cercle peut changer la photo d’un autre membre")
    return me, target


@api.post("/circle/members/{member_id}/photo")
async def set_member_photo(member_id: str, photo: UploadFile = File(...), user=Depends(get_current_user)):
    me, target = await _photo_target(member_id, user)
    data, mime, ext = await _validated_photo(photo)
    path = f"{APP_NAME}/avatars/{me['circle_id']}/{member_id}/{oid()}.{ext}"
    try:
        await run_in_threadpool(put_object, path, data, mime)
    except StorageError:
        raise HTTPException(500, "Échec de l’enregistrement de la photo")
    await db.members.update_one({"id": member_id}, {"$set": {
        "avatar_path": path, "avatar_mime": mime, "avatar_updated_at": now().isoformat()}})
    if target.get("avatar_path"):
        try:
            await run_in_threadpool(delete_object, target["avatar_path"])
        except Exception:  # noqa — the old file is only orphaned, the new photo is already in place
            pass
    await log_event("member_photo_updated", circle_id=me["circle_id"], member_id=member_id, user_id=user["id"])
    return clean(await db.members.find_one({"id": member_id}))


@api.delete("/circle/members/{member_id}/photo")
async def delete_member_photo(member_id: str, user=Depends(get_current_user)):
    me, target = await _photo_target(member_id, user)
    await db.members.update_one({"id": member_id}, {"$unset": {"avatar_path": "", "avatar_mime": "", "avatar_updated_at": ""}})
    if target.get("avatar_path"):
        try:
            await run_in_threadpool(delete_object, target["avatar_path"])
        except Exception:  # noqa
            pass
    await log_event("member_photo_deleted", circle_id=me["circle_id"], member_id=member_id, user_id=user["id"])
    return clean(await db.members.find_one({"id": member_id}))


@api.get("/circle/members/{member_id}/photo")
async def stream_member_photo(member_id: str, token: str = Query(...)):
    viewer = await _media_member(token)
    target = await db.members.find_one({"id": member_id, "circle_id": viewer["circle_id"], "status": {"$ne": "revoked"}})
    if not target or not target.get("avatar_path"):
        raise HTTPException(404, "Photo introuvable")
    try:
        content, _ = await run_in_threadpool(get_object, target["avatar_path"])
    except Exception:
        raise HTTPException(404, "Photo indisponible")
    safe_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".heic": "image/heic"}.get(
        Path(target["avatar_path"]).suffix.lower(), "application/octet-stream")
    # The URL carries a version (?v=…), so phones may cache it: avatars appear on almost every screen.
    return Response(content=content, media_type=safe_type, headers={
        "Cache-Control": "private, max-age=604800", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline; filename=\"photo-profil\"",
    })


# ---------------------------------------------------------------------------
# Livre romancé (AI chapters)
# ---------------------------------------------------------------------------
@api.get("/book/status")
async def book_status(user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    cid = member["circle_id"]
    total = await db.capsules.count_documents({"circle_id": cid, "status": "saved"})
    transcribed = await db.capsules.count_documents({"circle_id": cid, "status": "saved", "transcript_status": "done"})
    pending = await db.capsules.count_documents({"circle_id": cid, "status": "saved", "transcript_status": "pending"})
    unavailable = await db.capsules.count_documents({"circle_id": cid, "status": "saved", "transcript_status": {"$in": ["failed", "unavailable"]}})
    chapters = await db.book_chapters.count_documents({"circle_id": cid, "status": "ready"})
    return {"memory_count": total, "transcribed": transcribed, "pending": pending, "unavailable": unavailable,
            "chapter_count": chapters, "ai_available": book_ai_available(),
            "can_generate": total > 0 and book_ai_available()}


@api.post("/book/chapters")
async def create_chapter(user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    if not await db.capsules.count_documents({"circle_id": member["circle_id"], "status": "saved"}):
        raise HTTPException(400, "Ajoutez au moins un souvenir avant de créer un chapitre")
    if not book_ai_available():
        raise HTTPException(503, "La rédaction des chapitres n’est pas encore activée pour cette version de test.")
    try:
        chapter = await generate_chapter(member["circle_id"])
    except HTTPException:
        raise
    except Exception as e:  # noqa
        logger.error("Chapter generation failed: %s", e)
        raise HTTPException(502, "L’écriture du chapitre a échoué, réessayez dans un instant")
    return clean(chapter)


@api.get("/book/chapters")
async def list_chapters(user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    docs = await db.book_chapters.find({"circle_id": member["circle_id"], "status": "ready"}).sort("created_at", -1).to_list(200)
    return [clean(d) for d in docs]


@api.get("/book/chapters/{chapter_id}")
async def get_chapter(chapter_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    c = await db.book_chapters.find_one({"id": chapter_id, "circle_id": member["circle_id"], "status": "ready"})
    if not c:
        raise HTTPException(404, "Chapitre introuvable")
    return clean(c)


@api.delete("/book/chapters/{chapter_id}")
async def delete_chapter(chapter_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    c = await db.book_chapters.find_one({"id": chapter_id, "circle_id": member["circle_id"]})
    if not c:
        raise HTTPException(404, "Chapitre introuvable")
    await db.book_chapters.update_one({"id": chapter_id}, {"$set": {"status": "deleted", "deleted_at": now().isoformat()}})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Preferences / feedback
# ---------------------------------------------------------------------------
@api.patch("/me/preferences")
async def update_prefs(body: PreferencesIn, user=Depends(get_current_user)):
    member = await get_member(user)
    updates_user = {}
    updates_member = {}
    if body.display_name:
        updates_user["display_name"] = body.display_name.strip()
        updates_member["display_name"] = body.display_name.strip()
    if body.relationship_label is not None:
        updates_user["relationship_label"] = body.relationship_label
        updates_member["relationship_label"] = body.relationship_label
    if body.initials_color:
        updates_member["initials_color"] = body.initials_color
    if body.daily_email is not None:
        updates_member["daily_email"] = body.daily_email
    if updates_user:
        await db.users.update_one({"id": user["id"]}, {"$set": updates_user})
    if member and updates_member:
        await db.members.update_one({"id": member["id"]}, {"$set": updates_member})
    if member and body.daily_email is not None and body.daily_email != member.get("daily_email"):
        await log_event("daily_email_preference_changed", user_id=user["id"], circle_id=member["circle_id"],
                        member_id=member["id"], enabled=body.daily_email)
    updated = await db.users.find_one({"id": user["id"]})
    m = await get_member(user)
    return {"user": clean(updated), "member": clean(m) if m else None}


@api.post("/feedback")
async def submit_feedback(body: FeedbackIn, user=Depends(get_current_user)):
    member = await get_member(user)
    fb = {"id": oid(), "user_id": user["id"], "circle_id": member["circle_id"] if member else None,
          "category": body.category, "rating": body.rating, "comment": body.comment,
          "page_context": body.page_context, "app_version": body.app_version, "platform": body.platform,
          "api_version": APP_API_VERSION, "created_at": now().isoformat()}
    await db.feedback.insert_one(fb)
    await log_event("feedback_submitted", user_id=user["id"], circle_id=fb["circle_id"], category=body.category,
                    rating=body.rating)
    return {"ok": True}


@api.post("/events")
async def client_event(body: ClientEventIn, user=Depends(get_current_user)):
    """Usage events only the app can observe (screen views, recorder start/failure)."""
    if body.event_type not in CLIENT_EVENT_TYPES:
        raise HTTPException(400, "Événement inconnu")
    member = await get_member(user)
    await log_event(body.event_type, user_id=user["id"], circle_id=member["circle_id"] if member else None,
                    member_id=member["id"] if member else None, question_id=body.question_id, theme=body.theme,
                    source=body.source, error_type=body.error_type)
    return {"ok": True}


@api.get("/me/consents")
async def my_consents(user=Depends(get_current_user)):
    docs = await db.consents.find({"user_id": user["id"]}, {"_id": 0}).sort("occurred_at", -1).to_list(50)
    pending = await db.deletion_requests.find_one({"user_id": user["id"], "status": "open"}, {"_id": 0})
    return {"consents": docs, "deletion_request": pending}


@api.post("/me/deletion-request")
async def request_deletion(body: DeletionRequestIn, user=Depends(get_current_user)):
    """E11 / RGPD: the member asks for deletion; Racontelle executes it manually and keeps a trace."""
    member = await get_member(user)
    existing = await db.deletion_requests.find_one({"user_id": user["id"], "status": "open"})
    if existing:
        return {"ok": True, "already_requested": True}
    req = {"id": oid(), "user_id": user["id"], "email": user["email"],
           "circle_id": member["circle_id"] if member else None, "scope": body.scope,
           "comment": (body.comment or "").strip() or None, "status": "open", "created_at": now().isoformat()}
    await db.deletion_requests.insert_one(req)
    await log_event("deletion_requested", user_id=user["id"], circle_id=req["circle_id"], scope=body.scope)
    return {"ok": True, "already_requested": False}


# ---------------------------------------------------------------------------
# Administration (no graphical back-office in the MVP: protected endpoints, header X-Admin-Token)
# ---------------------------------------------------------------------------
ADMIN_TOKEN = (os.environ.get("ADMIN_TOKEN") or "").strip()

EVENT_CSV_FIELDS = ["occurred_at", "event_type", "user_id", "circle_id", "member_id", "narrator_member_id",
                    "capsule_id", "question_id", "daily_question_id", "theme", "source", "duration_sec",
                    "category", "rating", "error_type"]


async def require_admin(x_admin_token: Optional[str] = Header(None)):
    if len(ADMIN_TOKEN) < 24:
        raise HTTPException(503, "Administration désactivée : définissez ADMIN_TOKEN (24 caractères minimum)")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "Jeton d’administration invalide")
    return True


@api.get("/admin/events/export")
async def export_events(since: Optional[str] = None, _=Depends(require_admin)):
    """CSV export of the beta usage journal (MVP-23). Voice content is never included."""
    import csv
    import io
    import json
    query = {"occurred_at": {"$gte": since}} if since else {}
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(EVENT_CSV_FIELDS + ["metadata_json"])
    async for ev in db.events.find(query, {"_id": 0}).sort("occurred_at", 1):
        extra = {k: v for k, v in ev.items() if k not in EVENT_CSV_FIELDS and k != "id"}
        writer.writerow([ev.get(f, "") for f in EVENT_CSV_FIELDS] + [json.dumps(extra, ensure_ascii=False) if extra else ""])
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f"attachment; filename=\"racontelle-evenements-{paris_today()}.csv\"",
        "Cache-Control": "no-store"})


@api.post("/admin/import/questions")
async def import_questions(items: List[QuestionImportItem], _=Depends(require_admin)):
    """Idempotent upsert keyed on source_number (Annex B template). Existing ids are preserved."""
    created = updated = 0
    for item in items:
        fields = item.model_dump()
        res = await db.questions.update_one(
            {"source_number": item.source_number},
            {"$set": fields, "$setOnInsert": {"id": oid()}},
            upsert=True,
        )
        if res.upserted_id is not None:
            created += 1
        else:
            updated += res.modified_count
    await log_event("questions_imported", created=created, updated=updated)
    return {"created": created, "updated": updated, "total": await db.questions.count_documents({})}


@api.patch("/admin/questions/{source_number}")
async def set_question_active(source_number: int, body: QuestionActiveIn, _=Depends(require_admin)):
    """Deactivate/reactivate a question without redeploying (§10.2). Sensitive questions stay inactive."""
    q = await db.questions.find_one({"source_number": source_number})
    if not q:
        raise HTTPException(404, "Question introuvable")
    if body.active and q.get("sensitive"):
        raise HTTPException(400, "Les questions sensibles restent inactives pendant la bêta")
    await db.questions.update_one({"source_number": source_number}, {"$set": {"active": body.active}})
    await log_event("question_toggled", question_id=q["id"], active=body.active)
    return {"source_number": source_number, "active": body.active}


@api.get("/admin/deletion-requests")
async def list_deletion_requests(_=Depends(require_admin)):
    return await db.deletion_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/admin/purge-deleted")
async def purge_deleted_capsules(older_than_days: int = Query(30, ge=0, le=3650), _=Depends(require_admin)):
    """Final purge (RG-14): removes audio/photo files of capsules deleted more than N days ago."""
    cutoff = (now() - timedelta(days=older_than_days)).isoformat()
    purged = failed = 0
    async for c in db.capsules.find({"status": "deleted", "purged_at": {"$exists": False}, "deleted_at": {"$lte": cutoff}}):
        paths = [c["storage_path"]] + [p["path"] for p in _capsule_photos(c)]
        try:
            for path in paths:
                await run_in_threadpool(delete_object, path)
        except Exception as e:  # noqa
            logger.error("Purge failed for capsule %s: %s", c["id"], e)
            failed += 1
            continue
        await db.capsules.update_one({"id": c["id"]}, {
            "$set": {"purged_at": now().isoformat(), "transcript": None, "photos": [], "photo_path": None}})
        await log_event("capsule_purged", capsule_id=c["id"], circle_id=c["circle_id"])
        purged += 1
    return {"purged": purged, "failed": failed}


@api.post("/admin/send-daily-emails")
async def trigger_daily_emails(_=Depends(require_admin)):
    return await send_daily_emails()


# ---------------------------------------------------------------------------
# Daily question e-mail (at most one per member per day, only if the member enabled it)
# ---------------------------------------------------------------------------
DAILY_EMAIL_HOUR = int(os.environ.get("DAILY_EMAIL_HOUR", "9"))  # Europe/Paris


async def send_daily_emails() -> dict:
    local_date = paris_today()
    sent = skipped = failed = 0
    async for circle in db.circles.find({"status": "active"}):
        recipients = await db.members.find({"circle_id": circle["id"], "status": "active", "daily_email": True,
                                             "user_id": {"$ne": None}}).to_list(200)
        if not recipients:
            continue
        dailies = await ensure_daily(circle["id"])
        if not dailies:
            continue
        question = await db.questions.find_one({"id": dailies[0]["question_id"]})
        for m in recipients:
            try:
                # The unique index on (member_id, local_date) guarantees one e-mail per day, even across workers.
                await db.daily_email_log.insert_one({"member_id": m["id"], "local_date": local_date, "at": now().isoformat()})
            except DuplicateKeyError:
                skipped += 1
                continue
            user = await db.users.find_one({"id": m["user_id"], "active": True})
            if not user or not question:
                continue
            ok = await send_email(to=user["email"], subject="Votre question du jour sur Racontelle",
                                  html=_daily_email_html(m["display_name"], question["text"]))
            if ok:
                sent += 1
                await log_event("daily_email_sent", user_id=user["id"], circle_id=circle["id"], member_id=m["id"],
                                daily_question_id=dailies[0]["id"])
            else:
                failed += 1
                await log_event("daily_email_failed", user_id=user["id"], circle_id=circle["id"], member_id=m["id"])
    return {"date": local_date, "sent": sent, "already_sent": skipped, "failed": failed}


async def _daily_email_loop():
    import asyncio
    while True:
        try:
            if now().astimezone(TZ_PARIS).hour >= DAILY_EMAIL_HOUR and (RESEND_API_KEY or EMAIL_KEY):
                result = await send_daily_emails()
                if result["sent"] or result["failed"]:
                    logger.info("Daily e-mails: %s", result)
        except Exception as e:  # noqa
            logger.error("Daily e-mail loop error: %s", e)
        await asyncio.sleep(600)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.questions.create_index("source_number", unique=True)
        await db.invitations.create_index("token_hash")
        await db.reset_tokens.create_index("token_hash")
        await db.events.create_index("occurred_at")
        # At most DAILY_COUNT questions per circle and day, even with concurrent requests (older docs have no slot).
        await db.daily_questions.create_index(
            [("circle_id", 1), ("local_date", 1), ("slot", 1)], unique=True,
            partialFilterExpression={"slot": {"$exists": True}})
        await db.daily_email_log.create_index([("member_id", 1), ("local_date", 1)], unique=True)
    except Exception as e:  # noqa
        logger.warning("index creation: %s", e)
    # One-off data migrations: a failure is logged, never blocks the API from starting.
    try:
        # Plaintext codes from before hashing are no longer needed: token_hash already holds sha(code).
        await db.invitations.update_many({"code": {"$exists": True}}, {"$unset": {"code": ""}})
        await db.reset_tokens.update_many({"code": {"$exists": True}}, {"$set": {"used": True}, "$unset": {"code": ""}})
        for old_name, new_name in LEGACY_THEME_NAMES.items():
            for collection in (db.questions, db.capsules, db.daily_questions):
                await collection.update_many({"theme": old_name}, {"$set": {"theme": new_name}})
    except Exception as e:  # noqa
        logger.warning("startup migration skipped: %s", e)
    # Seed the questions bank, then backfill level/usage/tags from the editorial annex (idempotent).
    count = await db.questions.count_documents({})
    if count < 400:
        for q in parse_questions():
            q["id"] = oid()
            await db.questions.update_one({"source_number": q["source_number"]}, {"$setOnInsert": q}, upsert=True)
        logger.info("Seeded questions bank")
    try:
        if await db.questions.count_documents({"tags": {"$exists": False}}):
            for number, (level, usage, tags) in QUESTION_META.items():
                await db.questions.update_one({"source_number": number, "tags": {"$exists": False}},
                                              {"$set": {"level": level, "usage": usage, "tags": tags}})
            logger.info("Backfilled question level/usage/tags")
    except Exception as e:  # noqa
        logger.warning("question metadata backfill skipped: %s", e)
    import asyncio
    asyncio.get_event_loop().create_task(_daily_email_loop())
    if not STT_API_KEY:
        await db.capsules.update_many(
            {"status": "saved", "transcript_status": "pending"},
            {"$set": {"transcript_status": "unavailable"}},
        )
    try:
        await run_in_threadpool(init_storage)
        logger.info("Object storage ready")
    except Exception as e:  # noqa
        logger.warning("storage init failed: %s", e)


@app.on_event("shutdown")
async def shutdown():
    client.close()


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    # Auth uses a Bearer header, never cookies, so credentials are not needed cross-origin.
    allow_credentials=False,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
