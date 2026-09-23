from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
import uuid
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from pymongo.errors import DuplicateKeyError

load_dotenv()

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ISSUER = os.environ["JWT_ISSUER"]
JWT_AUDIENCE = os.environ["JWT_AUDIENCE"]
ACCESS_MINUTES = int(os.environ["ACCESS_MINUTES"])
REFRESH_DAYS = int(os.environ["REFRESH_DAYS"])
COOKIE_NAME = "racontelle_refresh"

if len(JWT_SECRET) < 64:
    raise RuntimeError("JWT_SECRET doit contenir au moins 64 caractères")

password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash("mot-de-passe-factice-jamais-utilise")
bearer = HTTPBearer(auto_error=False)
db = None


def now() -> datetime:
    return datetime.now(timezone.utc)


def configure_security(database) -> None:
    global db
    db = database


async def ensure_security_indexes() -> None:
    await db.users.create_index("email_lower", unique=True)
    await db.refresh_tokens.create_index("token_hash", unique=True)
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.auth_attempts.create_index("expires_at", expireAfterSeconds=0)
    await db.usage_quotas.create_index(
        [("tenant_id", 1), ("user_id", 1), ("day", 1)], unique=True
    )
    await db.share_tokens.create_index("token_hash", unique=True, sparse=True)
    await db.share_tokens.create_index("expires_at", expireAfterSeconds=0)
    for collection in ("residents", "capsules", "status_checks", "share_tokens"):
        await db[collection].update_many(
            {"tenant_id": {"$exists": False}}, {"$set": {"tenant_id": "legacy-quarantine"}}
        )
        await db[collection].create_index([("tenant_id", 1), ("created_at", -1)])


@dataclass(frozen=True)
class AuthUser:
    id: str
    tenant_id: str
    role: str
    email: str
    full_name: str
    establishment_name: str


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class RegisterRequest(Credentials):
    full_name: str = Field(min_length=2, max_length=100)
    establishment_name: str = Field(min_length=2, max_length=120)


class MemberCreate(Credentials):
    full_name: str = Field(min_length=2, max_length=100)


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


class UserOut(BaseModel):
    id: str
    tenant_id: str
    email: str
    full_name: str
    role: str
    establishment_name: str


class SessionOut(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserOut


def _refresh_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _access_token(user: dict, establishment_name: str) -> str:
    issued = now()
    payload = {
        "sub": user["id"],
        "tid": user["tenant_id"],
        "role": user["role"],
        "typ": "access",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": issued,
        "exp": issued + timedelta(minutes=ACCESS_MINUTES),
        "est": establishment_name,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _user_out(user: dict, establishment_name: str) -> UserOut:
    return UserOut(
        id=user["id"],
        tenant_id=user["tenant_id"],
        email=user["email_lower"],
        full_name=user["full_name"],
        role=user["role"],
        establishment_name=establishment_name,
    )


async def _issue_session(user: dict, response: Response, web: bool) -> SessionOut:
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=401, detail="Établissement introuvable")
    raw = secrets.token_urlsafe(64)
    await db.refresh_tokens.insert_one(
        {
            "id": str(uuid.uuid4()),
            "tenant_id": user["tenant_id"],
            "user_id": user["id"],
            "family_id": str(uuid.uuid4()),
            "token_hash": _refresh_hash(raw),
            "created_at": now(),
            "expires_at": now() + timedelta(days=REFRESH_DAYS),
            "revoked_at": None,
            "replaced_by": None,
        }
    )
    if web:
        response.set_cookie(
            COOKIE_NAME,
            raw,
            max_age=REFRESH_DAYS * 86400,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/api/auth",
        )
    return SessionOut(
        access_token=_access_token(user, tenant["name"]),
        refresh_token=None if web else raw,
        user=_user_out(user, tenant["name"]),
    )


async def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> AuthUser:
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=["HS256"],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
        )
        if payload.get("typ") != "access":
            raise ValueError("type de jeton invalide")
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Session invalide ou expirée",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = await db.users.find_one(
        {
            "id": payload.get("sub"),
            "tenant_id": payload.get("tid"),
            "disabled": {"$ne": True},
        },
        {"_id": 0},
    )
    tenant = await db.tenants.find_one(
        {"id": payload.get("tid"), "active": {"$ne": False}}, {"_id": 0}
    )
    if not user or not tenant:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée")
    return AuthUser(
        id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
        email=user["email_lower"],
        full_name=user["full_name"],
        establishment_name=tenant["name"],
    )


async def require_admin(user: AuthUser = Depends(current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return user


QUOTAS = {"stt": ("transcriptions", 30), "tts": ("tts", 100), "upload": ("audio_uploads", 100)}


async def consume_quota(user: AuthUser, kind: str) -> int:
    field, limit = QUOTAS[kind]
    day = now().date().isoformat()
    key = {"tenant_id": user.tenant_id, "user_id": user.id, "day": day}
    await db.usage_quotas.update_one(
        key,
        {
            "$setOnInsert": {
                **key,
                "transcriptions": 0,
                "tts": 0,
                "audio_uploads": 0,
                "created_at": now(),
            }
        },
        upsert=True,
    )
    result = await db.usage_quotas.update_one(
        {**key, field: {"$lt": limit}}, {"$inc": {field: 1}, "$set": {"updated_at": now()}}
    )
    if not result.modified_count:
        raise HTTPException(
            status_code=429,
            detail=f"Quota quotidien {kind} atteint",
            headers={"Retry-After": "86400"},
        )
    document = await db.usage_quotas.find_one(key, {"_id": 0, field: 1})
    return limit - int(document.get(field, 0))


auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


def _is_web(client_platform: Optional[str]) -> bool:
    return (client_platform or "").lower() == "web"


def _login_window(email: str) -> tuple[dict, datetime]:
    window = now().replace(second=0, microsecond=0)
    window = window - timedelta(minutes=window.minute % 15)
    key = {"email_hash": hashlib.sha256(email.encode()).hexdigest(), "window": window}
    return key, window


async def _assert_login_rate(email: str) -> None:
    key, _ = _login_window(email)
    attempt = await db.auth_attempts.find_one(key, {"_id": 0, "count": 1})
    if int((attempt or {}).get("count", 0)) >= 10:
        raise HTTPException(
            status_code=429,
            detail="Trop de tentatives. Réessayez dans quelques minutes.",
            headers={"Retry-After": "900"},
        )


async def _record_failed_login(email: str) -> None:
    key, window = _login_window(email)
    await db.auth_attempts.update_one(
        key,
        {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": window + timedelta(minutes=30)}},
        upsert=True,
    )


@auth_router.post("/register", response_model=SessionOut, status_code=201)
async def register(
    body: RegisterRequest,
    response: Response,
    x_client_platform: Optional[str] = Header(default=None),
):
    email = body.email.lower().strip()
    tenant_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    tenant = {
        "id": tenant_id,
        "name": body.establishment_name.strip(),
        "active": True,
        "created_at": now(),
    }
    user = {
        "id": user_id,
        "tenant_id": tenant_id,
        "email_lower": email,
        "full_name": body.full_name.strip(),
        "password_hash": password_hash.hash(body.password),
        "role": "admin",
        "disabled": False,
        "created_at": now(),
    }
    try:
        await db.tenants.insert_one(tenant)
        await db.users.insert_one(user)
    except DuplicateKeyError as exc:
        await db.tenants.delete_one({"id": tenant_id})
        raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée") from exc
    return await _issue_session(user, response, _is_web(x_client_platform))


@auth_router.post("/login", response_model=SessionOut)
async def login(
    body: Credentials,
    response: Response,
    x_client_platform: Optional[str] = Header(default=None),
):
    email = body.email.lower().strip()
    await _assert_login_rate(email)
    user = await db.users.find_one({"email_lower": email}, {"_id": 0})
    valid = password_hash.verify(body.password, user["password_hash"] if user else dummy_hash)
    if not user or not valid or user.get("disabled"):
        await _record_failed_login(email)
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    await db.auth_attempts.delete_many({"email_hash": hashlib.sha256(email.encode()).hexdigest()})
    return await _issue_session(user, response, _is_web(x_client_platform))


@auth_router.post("/refresh", response_model=SessionOut)
async def refresh_session(
    body: RefreshRequest,
    response: Response,
    request: Request,
    cookie_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    x_client_platform: Optional[str] = Header(default=None),
):
    web = _is_web(x_client_platform)
    raw = cookie_token if web else body.refresh_token
    if not raw:
        raise HTTPException(status_code=401, detail="Session expirée")
    old = await db.refresh_tokens.find_one({"token_hash": _refresh_hash(raw)}, {"_id": 0})
    expires_at = old.get("expires_at") if old else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not old or old.get("revoked_at") or not expires_at or expires_at <= now():
        raise HTTPException(status_code=401, detail="Session expirée")
    if old.get("replaced_by"):
        await db.refresh_tokens.update_many(
            {"family_id": old["family_id"]}, {"$set": {"revoked_at": now()}}
        )
        raise HTTPException(status_code=401, detail="Session expirée")
    user = await db.users.find_one(
        {"id": old["user_id"], "tenant_id": old["tenant_id"], "disabled": {"$ne": True}},
        {"_id": 0},
    )
    if not user:
        raise HTTPException(status_code=401, detail="Session expirée")
    replacement = secrets.token_urlsafe(64)
    replacement_hash = _refresh_hash(replacement)
    updated = await db.refresh_tokens.update_one(
        {"id": old["id"], "revoked_at": None, "replaced_by": None},
        {"$set": {"revoked_at": now(), "replaced_by": replacement_hash}},
    )
    if not updated.modified_count:
        raise HTTPException(status_code=401, detail="Session déjà renouvelée")
    new_doc = {
        **old,
        "id": str(uuid.uuid4()),
        "token_hash": replacement_hash,
        "created_at": now(),
        "expires_at": now() + timedelta(days=REFRESH_DAYS),
        "revoked_at": None,
        "replaced_by": None,
    }
    await db.refresh_tokens.insert_one(new_doc)
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0})
    if web:
        response.set_cookie(
            COOKIE_NAME,
            replacement,
            max_age=REFRESH_DAYS * 86400,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/api/auth",
        )
    return SessionOut(
        access_token=_access_token(user, tenant["name"]),
        refresh_token=None if web else replacement,
        user=_user_out(user, tenant["name"]),
    )


@auth_router.post("/logout")
async def logout(
    body: RefreshRequest,
    response: Response,
    user: AuthUser = Depends(current_user),
    cookie_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
):
    raw = cookie_token or body.refresh_token
    if raw:
        await db.refresh_tokens.update_one(
            {"token_hash": _refresh_hash(raw), "user_id": user.id},
            {"$set": {"revoked_at": now()}},
        )
    response.delete_cookie(COOKIE_NAME, path="/api/auth")
    return {"ok": True}


@auth_router.get("/me", response_model=UserOut)
async def me(user: AuthUser = Depends(current_user)):
    return UserOut(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        establishment_name=user.establishment_name,
    )


@auth_router.get("/members", response_model=list[UserOut])
async def list_members(admin: AuthUser = Depends(require_admin)):
    users = await db.users.find(
        {"tenant_id": admin.tenant_id, "disabled": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return [
        _user_out(user, admin.establishment_name)
        for user in users
    ]


@auth_router.post("/members", response_model=UserOut, status_code=201)
async def create_member(body: MemberCreate, admin: AuthUser = Depends(require_admin)):
    email = body.email.lower().strip()
    user = {
        "id": str(uuid.uuid4()),
        "tenant_id": admin.tenant_id,
        "email_lower": email,
        "full_name": body.full_name.strip(),
        "password_hash": password_hash.hash(body.password),
        "role": "member",
        "disabled": False,
        "created_at": now(),
    }
    try:
        await db.users.insert_one(user)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée") from exc
    return _user_out(user, admin.establishment_name)
