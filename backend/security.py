from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
import os
import secrets
import uuid
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from pymongo.errors import DuplicateKeyError

from email_service import EmailConfigurationError, EmailDeliveryError, send_password_reset_email

load_dotenv()
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(64)
JWT_ISSUER = os.environ.get("JWT_ISSUER", "racontelle-care")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "racontelle-care-app")
ACCESS_MINUTES = int(os.environ.get("ACCESS_MINUTES", "15"))
REFRESH_DAYS = int(os.environ.get("REFRESH_DAYS", "30"))
COOKIE_NAME = "racontelle_refresh"
# Délai pendant lequel un jeton tout juste renouvelé peut être présenté à
# nouveau sans fermer la session (réponse perdue sur un réseau faible).
REFRESH_GRACE_SECONDS = 120

if len(JWT_SECRET) < 64:
    logger.warning("JWT_SECRET trop court, génération d'un secret temporaire pour cette instance")
    JWT_SECRET = secrets.token_urlsafe(64)

password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash("mot-de-passe-factice-jamais-utilise")
bearer = HTTPBearer(auto_error=False)
db = None


def now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """MongoDB renvoie des dates sans fuseau : elles sont en UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


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
    await db.password_resets.create_index("expires_at", expireAfterSeconds=0)
    await db.password_resets.create_index("user_id")
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
    if user["role"] == "admin":
        # Cahier des charges bêta §12 : les accès administrateur sont journalisés.
        await _audit_raw(user["tenant_id"], user["id"], "auth.admin_login", "user", user["id"], {"platform": x_client_platform or "inconnu"})
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
    expires_at = _aware(old.get("expires_at")) if old else None
    if not old or old.get("family_revoked") or not expires_at or expires_at <= now():
        raise HTTPException(status_code=401, detail="Session expirée")
    if old.get("replaced_by"):
        rotated_at = _aware(old.get("rotated_at") or old.get("revoked_at"))
        if not rotated_at or now() - rotated_at > timedelta(seconds=REFRESH_GRACE_SECONDS):
            # Rejeu tardif d'un jeton déjà renouvelé : vol possible, toute la
            # famille de sessions est fermée définitivement.
            await db.refresh_tokens.update_many(
                {"family_id": old["family_id"]},
                {"$set": {"revoked_at": now(), "family_revoked": True}},
            )
            raise HTTPException(status_code=401, detail="Session expirée")
        # Réponse perdue en route (réseau d'EHPAD, téléphone qui renvoie la
        # requête) : le jeton qui n'a jamais été reçu est annulé et un nouveau
        # est émis, au lieu de déconnecter quelqu'un en plein atelier.
        await db.refresh_tokens.update_one(
            {"token_hash": old["replaced_by"]}, {"$set": {"revoked_at": now(), "superseded": True}}
        )
    elif old.get("revoked_at"):
        # Déconnexion volontaire ou mot de passe changé.
        raise HTTPException(status_code=401, detail="Session expirée")
    user = await db.users.find_one(
        {"id": old["user_id"], "tenant_id": old["tenant_id"], "disabled": {"$ne": True}},
        {"_id": 0},
    )
    if not user:
        raise HTTPException(status_code=401, detail="Session expirée")
    replacement = secrets.token_urlsafe(64)
    replacement_hash = _refresh_hash(replacement)
    # Deux demandes identiques peuvent arriver en même temps (le téléphone
    # renvoie la requête) : la seconde remplace le jeton émis par la première,
    # dans la même fenêtre de grâce, au lieu de fermer la session.
    expected = old.get("replaced_by")
    rotated_at = old.get("rotated_at")
    for _ in range(3):
        updated = await db.refresh_tokens.update_one(
            {"id": old["id"], "replaced_by": expected, "family_revoked": {"$ne": True}},
            {"$set": {"revoked_at": now(), "rotated_at": rotated_at or now(), "replaced_by": replacement_hash}},
        )
        if updated.modified_count:
            break
        current = await db.refresh_tokens.find_one({"id": old["id"]}, {"_id": 0})
        current_rotated = _aware((current or {}).get("rotated_at"))
        if (
            not current
            or not current.get("replaced_by")
            or current.get("family_revoked")
            or not current_rotated
            or now() - current_rotated > timedelta(seconds=REFRESH_GRACE_SECONDS)
        ):
            raise HTTPException(status_code=401, detail="Session expirée")
        await db.refresh_tokens.update_one(
            {"token_hash": current["replaced_by"]}, {"$set": {"revoked_at": now(), "superseded": True}}
        )
        expected, rotated_at = current["replaced_by"], current.get("rotated_at")
    else:
        raise HTTPException(status_code=401, detail="Session expirée")
    new_doc = {
        **old,
        "id": str(uuid.uuid4()),
        "token_hash": replacement_hash,
        "created_at": now(),
        "expires_at": now() + timedelta(days=REFRESH_DAYS),
        "revoked_at": None,
        "rotated_at": None,
        "replaced_by": None,
        "superseded": False,
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
    await _audit_raw(admin.tenant_id, admin.id, "member.create", "user", user["id"], {"email": email})
    return _user_out(user, admin.establishment_name)


# ---------------------------------------------------------------------------
# Récupération du mot de passe
#
# 1. POST /api/auth/password/forgot : un code à usage unique (8 caractères,
#    valable 30 minutes, 5 essais) est envoyé par email. La réponse est
#    toujours identique pour ne pas révéler quelles adresses ont un compte.
# 2. POST /api/auth/password/reset : code + nouveau mot de passe. Toutes les
#    sessions ouvertes de l'utilisateur sont fermées.
# Sans service email configuré, l'administrateur peut définir un mot de passe
# temporaire pour un membre (voir plus bas).
# ---------------------------------------------------------------------------

RESET_MINUTES = 30
RESET_MAX_ATTEMPTS = 5
RESET_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans 0/O, 1/I/L : lisible et dictable
class ForgotRequest(BaseModel):
    email: EmailStr


class ResetRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=20)
    new_password: str = Field(min_length=12, max_length=128)


class MemberPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


def _normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _code_hash(reset_id: str, code: str) -> str:
    return hashlib.sha256(f"{reset_id}:{_normalize_code(code)}".encode()).hexdigest()


async def _audit_raw(tenant_id: str, user_id: str, action: str, object_type: str, object_id: Optional[str], details: dict) -> None:
    await db.audit_logs.insert_one(
        {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "user_id": user_id,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "details": details,
            "created_at": now().isoformat(),
        }
    )


FORGOT_MESSAGE = {
    "ok": True,
    "message": "Si un compte existe pour cette adresse, un lien et un code viennent d’être envoyés. Pensez à vérifier les courriers indésirables.",
}


async def _deliver_reset_email(to: str, full_name: str, code: str) -> None:
    try:
        await send_password_reset_email(to, full_name, code, RESET_MINUTES)
    except EmailConfigurationError:
        logger.warning("Service Resend non configuré : réinitialisation non envoyée")
    except EmailDeliveryError:
        logger.warning("Service Resend indisponible : réinitialisation non envoyée")


@auth_router.post("/password/forgot")
async def forgot_password(body: ForgotRequest, background_tasks: BackgroundTasks):
    email = body.email.lower().strip()
    # Même garde que la connexion : 10 demandes par quart d'heure et par adresse.
    await _assert_login_rate(email)
    await _record_failed_login(email)
    user = await db.users.find_one({"email_lower": email, "disabled": {"$ne": True}}, {"_id": 0})
    if not user:
        return FORGOT_MESSAGE
    code = "".join(secrets.choice(RESET_ALPHABET) for _ in range(8))
    reset_id = str(uuid.uuid4())
    await db.password_resets.delete_many({"user_id": user["id"]})
    await db.password_resets.insert_one(
        {
            "id": reset_id,
            "user_id": user["id"],
            "tenant_id": user["tenant_id"],
            "code_hash": _code_hash(reset_id, code),
            "attempts": 0,
            "created_at": now(),
            "expires_at": now() + timedelta(minutes=RESET_MINUTES),
        }
    )
    background_tasks.add_task(
        _deliver_reset_email,
        user["email_lower"],
        user["full_name"],
        f"{code[:4]}-{code[4:]}",
    )
    return FORGOT_MESSAGE


@auth_router.post("/password/reset")
async def reset_password(body: ResetRequest):
    email = body.email.lower().strip()
    await _assert_login_rate(email)
    invalid = HTTPException(status_code=400, detail="Code invalide ou expiré. Demandez un nouveau code.")
    user = await db.users.find_one({"email_lower": email, "disabled": {"$ne": True}}, {"_id": 0})
    reset = await db.password_resets.find_one({"user_id": user["id"]}, {"_id": 0}) if user else None
    if not user or not reset:
        await _record_failed_login(email)
        raise invalid
    expires_at = reset["expires_at"] if reset["expires_at"].tzinfo else reset["expires_at"].replace(tzinfo=timezone.utc)
    if expires_at <= now() or reset.get("attempts", 0) >= RESET_MAX_ATTEMPTS:
        await db.password_resets.delete_one({"id": reset["id"]})
        raise invalid
    if not hmac.compare_digest(reset["code_hash"], _code_hash(reset["id"], body.code)):
        await db.password_resets.update_one({"id": reset["id"]}, {"$inc": {"attempts": 1}})
        await _record_failed_login(email)
        raise invalid
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": password_hash.hash(body.new_password), "password_changed_at": now()}},
    )
    await db.password_resets.delete_many({"user_id": user["id"]})
    await db.refresh_tokens.update_many(
        {"user_id": user["id"], "revoked_at": None}, {"$set": {"revoked_at": now()}}
    )
    await db.auth_attempts.delete_many({"email_hash": hashlib.sha256(email.encode()).hexdigest()})
    await _audit_raw(user["tenant_id"], user["id"], "auth.password_reset", "user", user["id"], {})
    return {"ok": True, "message": "Mot de passe modifié. Vous pouvez vous connecter."}


@auth_router.post("/members/{member_id}/password")
async def set_member_password(member_id: str, body: MemberPasswordRequest, admin: AuthUser = Depends(require_admin)):
    """Mot de passe temporaire défini par l'administrateur (sans email)."""
    result = await db.users.update_one(
        {"id": member_id, "tenant_id": admin.tenant_id},
        {"$set": {"password_hash": password_hash.hash(body.new_password), "password_changed_at": now()}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    await db.refresh_tokens.update_many({"user_id": member_id, "revoked_at": None}, {"$set": {"revoked_at": now()}})
    await _audit_raw(admin.tenant_id, admin.id, "member.password_reset", "user", member_id, {})
    return {"ok": True}
