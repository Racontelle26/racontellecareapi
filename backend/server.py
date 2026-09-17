# -*- coding: utf-8 -*-
import os
import re
import logging
import secrets
import hashlib
import ipaddress
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
from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
import requests

from questions_data import parse_questions, THEMES_ORDER

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("racontelle")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ.get("JWT_SECRET", "racontelle-dev-secret-change-me")
JWT_ALG = "HS256"
ACCESS_DAYS = 30
RESET_MIN = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Object storage (audio)
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "racontelle-family"
_storage_key = None

# Email
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Racontelle Family")
APP_PUBLIC_URL = os.environ.get("APP_PUBLIC_URL", "https://racontelle.family")

TZ_PARIS_OFFSET = timedelta(hours=2)  # Europe/Paris (indicative for daily date)


def now() -> datetime:
    return datetime.now(timezone.utc)


def paris_today() -> str:
    return (now() + TZ_PARIS_OFFSET).date().isoformat()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Object storage helpers (sync -> run in threadpool)
# ---------------------------------------------------------------------------
def init_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    global _storage_key
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code == 503:
        _storage_key = None
        key = init_storage()
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


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
    if not EMAIL_KEY:
        logger.warning("EMERGENT_EMAIL_KEY missing; skipping email to %s", to)
        return None
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:  # noqa
        logger.error("Email send error: %s", e)
        return None


def _invite_email_html(circle_name: str, inviter: str, code: str) -> str:
    b = escape(EMAIL_FROM_NAME)
    return (
        f'<table role="presentation" width="100%" style="background:#FDFBF7">'
        f'<tr><td style="padding:32px;font-family:Georgia,serif;color:#3A332C">'
        f'<h1 style="color:#B57477;font-weight:500;font-size:26px;margin:0 0 8px">Racontelle Family</h1>'
        f'<p style="font-size:16px">{escape(inviter)} vous invite à rejoindre le cercle '
        f'<strong>{escape(circle_name)}</strong> pour enregistrer et préserver vos souvenirs de famille.</p>'
        f'<p style="font-size:15px">Ouvrez l’application Racontelle Family, créez votre compte, puis '
        f'choisissez <strong>« Rejoindre une famille »</strong> et saisissez ce code d’invitation :</p>'
        f'<p style="font-size:30px;letter-spacing:6px;color:#B57477;font-weight:600;text-align:center;'
        f'background:#F2DADA;border-radius:16px;padding:18px;margin:20px 0">{escape(code)}</p>'
        f'<p style="font-size:13px;color:#8A8177">Ce code expire dans 7 jours. Si vous n’êtes pas concerné(e), '
        f'ignorez simplement ce message.</p>'
        f'<p style="font-size:12px;color:#8A8177;margin-top:24px">Envoyé par {b}. '
        f'Nous ne vous demanderons jamais votre mot de passe par e-mail.</p>'
        f'</td></tr></table>'
    )


def _daily_email_html(name: str, question: str) -> str:
    b = escape(EMAIL_FROM_NAME)
    return (
        f'<table role="presentation" width="100%" style="background:#FDFBF7">'
        f'<tr><td style="padding:32px;font-family:Georgia,serif;color:#3A332C">'
        f'<h1 style="color:#B57477;font-weight:500;font-size:24px;margin:0 0 12px">Votre question du jour</h1>'
        f'<p style="font-size:16px">Bonjour {escape(name)},</p>'
        f'<p style="font-size:20px;font-style:italic;color:#3A332C;line-height:1.5">« {escape(question)} »</p>'
        f'<p style="font-size:15px;color:#5C5249">Ouvrez Racontelle Family pour répondre avec votre voix. '
        f'Chaque souvenir enregistré fait grandir votre arbre de famille.</p>'
        f'<p style="font-size:12px;color:#8A8177;margin-top:24px">Envoyé par {b}. '
        f'Vous pouvez désactiver ces rappels dans votre profil.</p>'
        f'</td></tr></table>'
    )


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
def oid() -> str:
    return str(ObjectId())


def clean(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    doc.pop("token_hash", None)
    return doc


# ---------------------------------------------------------------------------
# App + auth dependency
# ---------------------------------------------------------------------------
app = FastAPI(title="Racontelle Family API")
api = APIRouter(prefix="/api")


def make_token(user_id: str) -> str:
    t = now()
    return jwt.encode(
        {"sub": user_id, "iat": t, "exp": t + timedelta(days=ACCESS_DAYS)},
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


async def current_user(authorization: Optional[str] = None):
    # Set by dependency wrapper below
    raise NotImplementedError


from fastapi import Header  # noqa: E402


async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Non authentifié")
    uid = decode_token(authorization.split(" ", 1)[1])
    if not uid:
        raise HTTPException(401, "Session expirée")
    user = await db.users.find_one({"id": uid, "active": True})
    if not user:
        raise HTTPException(401, "Utilisateur introuvable")
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
    relationship_label: Optional[str] = None
    accept_terms: bool = True


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ResetReqIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


class CircleIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class InviteIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    relationship_label: Optional[str] = None


class JoinIn(BaseModel):
    code: str


class DailyStateIn(BaseModel):
    daily_question_id: str
    state: str = Field(pattern="^(viewed|skipped|answered)$")


class PreferencesIn(BaseModel):
    display_name: Optional[str] = None
    relationship_label: Optional[str] = None
    initials_color: Optional[str] = None
    daily_email: Optional[bool] = None


class FeedbackIn(BaseModel):
    category: str
    rating: Optional[int] = None
    comment: Optional[str] = None
    page_context: Optional[str] = None


AVATAR_COLORS = ["#C98B8B", "#738A70", "#D1A054", "#8A9691", "#B57477", "#A38160"]


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"message": "Racontelle Family API", "status": "ok"}


@api.post("/auth/register")
async def register(body: RegisterIn):
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
        {"id": oid(), "user_id": uid, "consent_type": "cgu_beta", "accepted": True, "version": "1.0", "occurred_at": now().isoformat()}
    )
    await db.events.insert_one({"id": oid(), "event_type": "account_created", "user_id": uid, "occurred_at": now().isoformat()})
    return {"access_token": make_token(uid), "user": clean(user)}


@api.post("/auth/login")
async def login(body: LoginIn):
    email = str(body.email).lower()
    user = await db.users.find_one({"email": email})
    if not user or not pwd_context.verify(body.password, user["password_hash"]):
        raise HTTPException(401, "E-mail ou mot de passe incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now().isoformat()}})
    return {"access_token": make_token(user["id"]), "user": clean(user)}


@api.post("/auth/request-reset")
async def request_reset(body: ResetReqIn):
    user = await db.users.find_one({"email": str(body.email).lower()})
    if user:
        raw = secrets.token_urlsafe(24)
        await db.reset_tokens.insert_one(
            {"id": oid(), "token_hash": sha(raw), "user_id": user["id"], "used": False,
             "expires_at": (now() + timedelta(minutes=RESET_MIN)).isoformat()}
        )
        # In this beta the code is delivered by email as a short reset code.
        code = raw[:8].upper()
        await db.reset_tokens.update_one({"token_hash": sha(raw)}, {"$set": {"code": code}})
        html = (
            f'<table role="presentation" width="100%" style="background:#FDFBF7"><tr>'
            f'<td style="padding:32px;font-family:Georgia,serif;color:#3A332C">'
            f'<h1 style="color:#B57477;font-weight:500">Réinitialisation</h1>'
            f'<p>Votre code de réinitialisation Racontelle Family :</p>'
            f'<p style="font-size:28px;letter-spacing:5px;color:#B57477;font-weight:600">{escape(code)}</p>'
            f'<p style="font-size:12px;color:#8A8177">Ce code expire dans 30 minutes. '
            f'Envoyé par {escape(EMAIL_FROM_NAME)}.</p></td></tr></table>'
        )
        await send_email(to=user["email"], subject="Réinitialisation de votre mot de passe", html=html)
    return {"message": "Si l’e-mail existe, un code de réinitialisation a été envoyé."}


@api.post("/auth/reset-password")
async def reset_password(body: ResetConfirmIn):
    token_doc = await db.reset_tokens.find_one({"code": body.token.strip().upper(), "used": False})
    if not token_doc or token_doc["expires_at"] < now().isoformat():
        raise HTTPException(400, "Code invalide ou expiré")
    await db.users.update_one({"id": token_doc["user_id"]}, {"$set": {"password_hash": pwd_context.hash(body.new_password)}})
    await db.reset_tokens.update_one({"id": token_doc["id"]}, {"$set": {"used": True}})
    return {"message": "Mot de passe réinitialisé"}


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
    await db.events.insert_one({"id": oid(), "event_type": "circle_created", "circle_id": cid, "user_id": user["id"], "occurred_at": now().isoformat()})
    return {"circle": clean(circle), "member": clean(member)}


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
    out = []
    for m in members:
        m = clean(m)
        m["capsule_count"] = await db.capsules.count_documents({"circle_id": member["circle_id"], "narrator_member_id": m["id"], "status": "saved"})
        out.append(m)
    return out


@api.post("/circle/invitations")
async def create_invitation(body: InviteIn, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member or member.get("role") != "owner":
        raise HTTPException(403, "Seul le créateur du cercle peut inviter")
    circle_id = member["circle_id"]
    circle = await db.circles.find_one({"id": circle_id})
    # create pending member profile
    new_member = {"id": oid(), "circle_id": circle_id, "user_id": None,
                  "display_name": body.display_name.strip(), "relationship_label": body.relationship_label,
                  "initials_color": AVATAR_COLORS[(await db.members.count_documents({"circle_id": circle_id})) % len(AVATAR_COLORS)],
                  "status": "pending", "role": "member", "daily_email": True, "created_at": now().isoformat()}
    await db.members.insert_one(new_member)
    raw = secrets.token_urlsafe(8)
    code = raw[:8].upper()
    invite = {"id": oid(), "circle_id": circle_id, "member_id": new_member["id"], "email": str(body.email).lower(),
              "token_hash": sha(code), "code": code, "status": "sent",
              "expires_at": (now() + timedelta(days=7)).isoformat(), "sent_at": now().isoformat(), "accepted_at": None}
    await db.invitations.insert_one(invite)
    await send_email(to=str(body.email).lower(), subject=f"{user['display_name']} vous invite sur Racontelle Family",
                     html=_invite_email_html(circle["name"], user["display_name"], code))
    await db.events.insert_one({"id": oid(), "event_type": "invite_sent", "circle_id": circle_id, "member_id": new_member["id"], "occurred_at": now().isoformat()})
    return {"member": clean(new_member), "invitation": clean(invite), "code": code}


@api.get("/circle/invitations")
async def list_invitations(user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    docs = await db.invitations.find({"circle_id": member["circle_id"], "status": {"$in": ["sent"]}}).sort("sent_at", -1).to_list(100)
    return [clean(d) for d in docs]


@api.post("/circle/invitations/{invite_id}/resend")
async def resend_invitation(invite_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member or member.get("role") != "owner":
        raise HTTPException(403, "Action non autorisée")
    invite = await db.invitations.find_one({"id": invite_id, "circle_id": member["circle_id"]})
    if not invite:
        raise HTTPException(404, "Invitation introuvable")
    circle = await db.circles.find_one({"id": member["circle_id"]})
    await send_email(to=invite["email"], subject=f"Rappel : invitation Racontelle Family",
                     html=_invite_email_html(circle["name"], user["display_name"], invite["code"]))
    return {"ok": True, "code": invite["code"]}


@api.delete("/circle/invitations/{invite_id}")
async def revoke_invitation(invite_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member or member.get("role") != "owner":
        raise HTTPException(403, "Action non autorisée")
    invite = await db.invitations.find_one({"id": invite_id, "circle_id": member["circle_id"]})
    if not invite:
        raise HTTPException(404, "Invitation introuvable")
    await db.invitations.update_one({"id": invite_id}, {"$set": {"status": "revoked"}})
    await db.members.update_one({"id": invite["member_id"], "status": "pending"}, {"$set": {"status": "revoked"}})
    return {"ok": True}


@api.post("/invitations/accept")
async def accept_invitation(body: JoinIn, user=Depends(get_current_user)):
    if await get_member(user):
        raise HTTPException(400, "Vous appartenez déjà à un cercle")
    code = body.code.strip().upper()
    invite = await db.invitations.find_one({"code": code, "status": "sent"})
    if not invite:
        raise HTTPException(404, "Code d’invitation invalide")
    if invite["expires_at"] < now().isoformat():
        await db.invitations.update_one({"id": invite["id"]}, {"$set": {"status": "expired"}})
        raise HTTPException(400, "Ce code d’invitation a expiré")
    await db.members.update_one(
        {"id": invite["member_id"]},
        {"$set": {"user_id": user["id"], "status": "active", "display_name": user["display_name"]}},
    )
    await db.invitations.update_one({"id": invite["id"]}, {"$set": {"status": "accepted", "accepted_at": now().isoformat()}})
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
    used_ids = [d["question_id"] for d in await db.daily_questions.find({"circle_id": circle_id}).to_list(2000)]
    used_today_themes = [d.get("theme") for d in existing]
    need = DAILY_COUNT - len(existing)
    # candidates not used before, avoid today's themes if possible
    pipeline = [{"$match": {"sensitive": False, "active": True, "id": {"$nin": used_ids}}}, {"$sample": {"size": 40}}]
    candidates = await db.questions.aggregate(pipeline).to_list(40)
    if not candidates:
        pipeline = [{"$match": {"sensitive": False, "active": True}}, {"$sample": {"size": 40}}]
        candidates = await db.questions.aggregate(pipeline).to_list(40)
    picked = []
    for c in candidates:
        if len(picked) >= need:
            break
        if c["theme"] in used_today_themes and any(x["theme"] != c["theme"] for x in candidates):
            continue
        used_today_themes.append(c["theme"])
        picked.append(c)
    for c in picked[:need]:
        dq = {"id": oid(), "circle_id": circle_id, "question_id": c["id"], "theme": c["theme"],
              "local_date": local_date, "generated_at": now().isoformat()}
        await db.daily_questions.insert_one(dq)
        existing.append(dq)
    return await db.daily_questions.find({"circle_id": circle_id, "local_date": local_date}).to_list(10)


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
    await db.daily_states.update_one(
        {"daily_question_id": body.daily_question_id, "member_id": member["id"]},
        {"$set": {"state": body.state, "updated_at": now().isoformat(),
                  "id": oid(), "circle_id": member["circle_id"]}},
        upsert=True,
    )
    if body.state == "skipped":
        await db.events.insert_one({"id": oid(), "event_type": "question_skipped", "circle_id": member["circle_id"], "member_id": member["id"], "occurred_at": now().isoformat()})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Capsules (audio memories)
# ---------------------------------------------------------------------------
@api.post("/capsules")
async def create_capsule(
    narrator_member_id: str = Form(...),
    duration_sec: int = Form(...),
    question_id: Optional[str] = Form(None),
    daily_question_id: Optional[str] = Form(None),
    theme: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    narrator = await db.members.find_one({"id": narrator_member_id, "circle_id": member["circle_id"]})
    if not narrator:
        raise HTTPException(400, "Narrateur invalide")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Fichier audio vide")
    ext = "m4a"
    ctype = file.content_type or "audio/m4a"
    if "webm" in ctype:
        ext = "webm"
    elif "mp4" in ctype or "m4a" in ctype:
        ext = "m4a"
    elif "wav" in ctype:
        ext = "wav"
    elif "mpeg" in ctype or "mp3" in ctype:
        ext = "mp3"
    cid = oid()
    path = f"{APP_NAME}/uploads/{member['circle_id']}/{cid}.{ext}"
    try:
        await run_in_threadpool(put_object, path, data, ctype)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 500
        if code == 402:
            raise HTTPException(402, "Stockage plein — impossible d’enregistrer pour le moment")
        raise HTTPException(500, "Échec de l’enregistrement audio")
    capsule = {
        "id": cid, "circle_id": member["circle_id"], "narrator_member_id": narrator_member_id,
        "recorded_by_user_id": user["id"], "question_id": question_id, "daily_question_id": daily_question_id,
        "theme": theme, "title": title, "storage_path": path, "mime_type": ctype,
        "duration_sec": duration_sec, "recorded_at": now().isoformat(), "created_at": now().isoformat(),
        "status": "saved",
    }
    await db.capsules.insert_one(capsule)
    if daily_question_id:
        await db.daily_states.update_one(
            {"daily_question_id": daily_question_id, "member_id": member["id"]},
            {"$set": {"state": "answered", "updated_at": now().isoformat(), "id": oid(), "circle_id": member["circle_id"]}},
            upsert=True,
        )
    await db.events.insert_one({"id": oid(), "event_type": "recording_saved", "capsule_id": cid,
                                "circle_id": member["circle_id"], "narrator_member_id": narrator_member_id,
                                "occurred_at": now().isoformat()})
    return clean(capsule)


async def _enrich_capsule(c: dict) -> dict:
    c = clean(c)
    narrator = await db.members.find_one({"id": c["narrator_member_id"]})
    if narrator:
        c["narrator_name"] = narrator["display_name"]
        c["narrator_color"] = narrator.get("initials_color")
    q = await db.questions.find_one({"id": c.get("question_id")}) if c.get("question_id") else None
    c["question_text"] = q["text"] if q else c.get("title")
    c["audio_url"] = f"/api/capsules/{c['id']}/audio"
    return c


@api.get("/capsules")
async def list_capsules(narrator: Optional[str] = None, theme: Optional[str] = None, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    q = {"circle_id": member["circle_id"], "status": "saved"}
    if narrator:
        q["narrator_member_id"] = narrator
    if theme:
        q["theme"] = theme
    docs = await db.capsules.find(q).sort("recorded_at", -1).to_list(1000)
    return [await _enrich_capsule(d) for d in docs]


@api.get("/capsules/{capsule_id}")
async def get_capsule(capsule_id: str, user=Depends(get_current_user)):
    member = await get_member(user)
    if not member:
        raise HTTPException(404, "Aucun cercle")
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    return await _enrich_capsule(c)


@api.get("/capsules/{capsule_id}/audio")
async def stream_audio(capsule_id: str, token: str = Query(...)):
    uid = decode_token(token)
    if not uid:
        raise HTTPException(401, "Non autorisé")
    user = await db.users.find_one({"id": uid, "active": True})
    if not user:
        raise HTTPException(401, "Non autorisé")
    member = await db.members.find_one({"user_id": uid, "status": "active"})
    if not member:
        raise HTTPException(403, "Accès refusé")
    c = await db.capsules.find_one({"id": capsule_id, "circle_id": member["circle_id"], "status": "saved"})
    if not c:
        raise HTTPException(404, "Souvenir introuvable")
    await db.events.insert_one({"id": oid(), "event_type": "capsule_played", "capsule_id": capsule_id, "user_id": uid, "occurred_at": now().isoformat()})
    try:
        content, ctype = await run_in_threadpool(get_object, c["storage_path"])
    except Exception:
        raise HTTPException(404, "Audio indisponible")
    return Response(content=content, media_type=ctype, headers={"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"})


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
    updated = await db.users.find_one({"id": user["id"]})
    m = await get_member(user)
    return {"user": clean(updated), "member": clean(m) if m else None}


@api.post("/feedback")
async def submit_feedback(body: FeedbackIn, user=Depends(get_current_user)):
    member = await get_member(user)
    fb = {"id": oid(), "user_id": user["id"], "circle_id": member["circle_id"] if member else None,
          "category": body.category, "rating": body.rating, "comment": body.comment,
          "page_context": body.page_context, "created_at": now().isoformat()}
    await db.feedback.insert_one(fb)
    await db.events.insert_one({"id": oid(), "event_type": "feedback_submitted", "user_id": user["id"], "occurred_at": now().isoformat()})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.questions.create_index("source_number", unique=True)
        await db.invitations.create_index("code")
    except Exception as e:  # noqa
        logger.warning("index creation: %s", e)
    # seed questions
    count = await db.questions.count_documents({})
    if count < 400:
        for q in parse_questions():
            q["id"] = oid()
            q["level"] = "tout public"
            q["usage"] = "Question de récit de vie"
            await db.questions.update_one({"source_number": q["source_number"]}, {"$setOnInsert": q}, upsert=True)
        logger.info("Seeded questions bank")
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
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
