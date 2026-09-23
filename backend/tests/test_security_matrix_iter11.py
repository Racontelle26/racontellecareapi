import io
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")


# auth/session helpers
BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL") or "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

ADMIN_A_EMAIL = "admin.security@racontelle.example.com"
ADMIN_A_PASSWORD = "Racontelle-Test-2026!"
ADMIN_B_EMAIL = "admin.other@racontelle.example.com"
ADMIN_B_PASSWORD = "Racontelle-Autre-2026!"
MEMBER_A_EMAIL = "member.security@racontelle.example.com"
MEMBER_A_PASSWORD = "Racontelle-Membre-2026!"


def _assert_env():
    assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL manquant"
    assert MONGO_URL, "MONGO_URL manquant"
    assert DB_NAME, "DB_NAME manquant"


def login(email: str, password: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        headers={"X-Client-Platform": "native"},
        json={"email": email, "password": password},
        timeout=25,
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_test_admin(label: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        headers={"X-Client-Platform": "native"},
        json={
            "email": f"{label}-{uuid.uuid4().hex[:8]}@racontelle.example.com",
            "password": f"Racontelle-{label}-2026!",
            "full_name": f"TEST {label}",
            "establishment_name": f"TEST {label}",
        },
        timeout=25,
    )
    assert response.status_code == 201, response.text
    return response.json()


# protected-route guard checks
def test_anonymous_rejected_on_remaining_protected_routes():
    _assert_env()
    anon_file = {"file": ("clip.m4a", io.BytesIO(b"abcd"), "audio/m4a")}
    for method, path, kwargs in (
        ("POST", "/api/capsules/fake-id/transcribe", {"files": anon_file}),
        ("POST", "/api/capsules/fake-id/audio", {"files": anon_file}),
        ("GET", "/api/residents/fake-id/export", {}),
        ("GET", "/api/residents/fake-id/carnet", {}),
        ("POST", "/api/residents/merge", {"json": {"keep_id": "a", "merge_ids": ["b"]}}),
    ):
        response = requests.request(
            method,
            f"{BASE_URL}{path}",
            headers={"Authorization": ""},
            timeout=20,
            **kwargs,
        )
        assert response.status_code == 401, (path, response.status_code, response.text)


# tenant isolation checks
def test_cross_tenant_resource_access_returns_404_without_leakage():
    _assert_env()
    admin_a = login(ADMIN_A_EMAIL, ADMIN_A_PASSWORD)
    admin_b = login(ADMIN_B_EMAIL, ADMIN_B_PASSWORD)
    resident_name = f"TEST_TENANT_{uuid.uuid4().hex[:8]}"
    created = requests.post(
        f"{BASE_URL}/api/residents",
        headers=auth(admin_a["access_token"]),
        json={"display_name": resident_name, "consent_status": "obtained"},
        timeout=20,
    )
    assert created.status_code == 201, created.text
    resident = created.json()

    cross_get = requests.get(
        f"{BASE_URL}/api/residents/{resident['id']}/capsules",
        headers=auth(admin_b["access_token"]),
        timeout=20,
    )
    assert cross_get.status_code == 404

    cross_patch = requests.patch(
        f"{BASE_URL}/api/residents/{resident['id']}",
        headers=auth(admin_b["access_token"]),
        json={"display_name": "TEST_HACK"},
        timeout=20,
    )
    assert cross_patch.status_code == 404

    cross_export = requests.get(
        f"{BASE_URL}/api/residents/{resident['id']}/export",
        headers=auth(admin_b["access_token"]),
        timeout=20,
    )
    assert cross_export.status_code == 404

    cleanup = requests.delete(
        f"{BASE_URL}/api/residents/{resident['id']}",
        headers=auth(admin_a["access_token"]),
        timeout=20,
    )
    assert cleanup.status_code == 200


# role-authorization matrix checks
def test_member_forbidden_for_admin_only_routes_but_allowed_for_basic_ops():
    _assert_env()
    admin_a = login(ADMIN_A_EMAIL, ADMIN_A_PASSWORD)
    member_a = login(MEMBER_A_EMAIL, MEMBER_A_PASSWORD)

    resident_name = f"TEST_MEMBER_{uuid.uuid4().hex[:8]}"
    resident_create = requests.post(
        f"{BASE_URL}/api/residents",
        headers=auth(member_a["access_token"]),
        json={"display_name": resident_name, "consent_status": "obtained"},
        timeout=20,
    )
    assert resident_create.status_code == 201, resident_create.text
    resident = resident_create.json()

    capsule_create = requests.post(
        f"{BASE_URL}/api/capsules",
        headers=auth(member_a["access_token"]),
        json={
            "resident_id": resident["id"],
            "mode": "free",
            "title": "TEST membre capsule",
            "duration_sec": 2,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
        timeout=20,
    )
    assert capsule_create.status_code == 201, capsule_create.text
    capsule = capsule_create.json()

    capsule_patch = requests.patch(
        f"{BASE_URL}/api/capsules/{capsule['id']}",
        headers=auth(member_a["access_token"]),
        json={"title": "TEST member edited"},
        timeout=20,
    )
    assert capsule_patch.status_code == 200

    for method, path, body in (
        ("DELETE", f"/api/capsules/{capsule['id']}", None),
        ("DELETE", f"/api/residents/{resident['id']}", None),
        ("POST", "/api/residents/merge", {"keep_id": resident["id"], "merge_ids": [resident["id"]]}),
        ("GET", f"/api/residents/{resident['id']}/export", None),
        ("GET", f"/api/residents/{resident['id']}/carnet", None),
        ("POST", "/api/auth/members", {"email": f"forbidden-{uuid.uuid4().hex[:6]}@example.com", "password": "Forbidden-Member-2026!", "full_name": "Nope"}),
    ):
        response = requests.request(
            method,
            f"{BASE_URL}{path}",
            headers=auth(member_a["access_token"]),
            json=body,
            timeout=20,
        )
        assert response.status_code == 403, (path, response.status_code, response.text)

    mongo = MongoClient(MONGO_URL)[DB_NAME]
    mongo.capsules.update_one({"id": capsule["id"]}, {"$set": {"storage_path": f"test/member/{capsule['id']}.m4a"}})
    share = requests.post(
        f"{BASE_URL}/api/capsules/{capsule['id']}/share",
        headers=auth(admin_a["access_token"]),
        timeout=20,
    )
    assert share.status_code == 200, share.text
    share_id = share.json()["share_id"]

    member_revoke = requests.delete(
        f"{BASE_URL}/api/shares/{share_id}",
        headers=auth(member_a["access_token"]),
        timeout=20,
    )
    assert member_revoke.status_code == 403

    requests.delete(
        f"{BASE_URL}/api/capsules/{capsule['id']}",
        headers=auth(admin_a["access_token"]),
        timeout=20,
    )
    requests.delete(
        f"{BASE_URL}/api/residents/{resident['id']}",
        headers=auth(admin_a["access_token"]),
        timeout=20,
    )


# token rotation / logout / validation / throttling checks
def test_refresh_rotation_logout_and_password_validation():
    _assert_env()
    email = f"security-flow-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    password = "Racontelle-Security-2026!"
    register = requests.post(
        f"{BASE_URL}/api/auth/register",
        headers={"X-Client-Platform": "native"},
        json={
            "email": email,
            "password": password,
            "full_name": "TEST Security Flow",
            "establishment_name": "TEST Security Flow Facility",
        },
        timeout=25,
    )
    assert register.status_code == 201, register.text
    session = register.json()

    refresh_1 = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        headers={"X-Client-Platform": "native"},
        json={"refresh_token": session["refresh_token"]},
        timeout=20,
    )
    assert refresh_1.status_code == 200, refresh_1.text
    refresh_1_token = refresh_1.json()["refresh_token"]

    old_replay = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        headers={"X-Client-Platform": "native"},
        json={"refresh_token": session["refresh_token"]},
        timeout=20,
    )
    assert old_replay.status_code == 401

    logout = requests.post(
        f"{BASE_URL}/api/auth/logout",
        headers={**auth(refresh_1.json()["access_token"]), "Content-Type": "application/json"},
        json={"refresh_token": refresh_1_token},
        timeout=20,
    )
    assert logout.status_code == 200

    revoked_refresh = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        headers={"X-Client-Platform": "native"},
        json={"refresh_token": refresh_1_token},
        timeout=20,
    )
    assert revoked_refresh.status_code == 401

    short_password = requests.post(
        f"{BASE_URL}/api/auth/register",
        headers={"X-Client-Platform": "native"},
        json={
            "email": f"short-{uuid.uuid4().hex[:6]}@racontelle.example.com",
            "password": "short123",
            "full_name": "Short Password",
            "establishment_name": "TEST",
        },
        timeout=20,
    )
    assert short_password.status_code == 422


def test_login_rate_limit_after_repeated_attempts():
    _assert_env()
    target_email = f"ratelimit-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    status_codes = []
    for _ in range(12):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            headers={"X-Client-Platform": "native"},
            json={"email": target_email, "password": "Wrong-Password-2026!"},
            timeout=20,
        )
        status_codes.append(response.status_code)
    assert status_codes[-1] == 429, status_codes


# quota / share / cors checks
def test_tts_stt_upload_quota_returns_429_with_retry_after():
    _assert_env()
    admin_a = register_test_admin("quota-matrix")
    mongo = MongoClient(MONGO_URL)[DB_NAME]

    resident_create = requests.post(
        f"{BASE_URL}/api/residents",
        headers=auth(admin_a["access_token"]),
        json={"display_name": f"TEST_QUOTA_{uuid.uuid4().hex[:8]}", "consent_status": "obtained"},
        timeout=20,
    )
    assert resident_create.status_code == 201, resident_create.text
    resident = resident_create.json()

    capsule_create = requests.post(
        f"{BASE_URL}/api/capsules",
        headers=auth(admin_a["access_token"]),
        json={
            "resident_id": resident["id"],
            "mode": "free",
            "title": "TEST quota",
            "duration_sec": 2,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
        timeout=20,
    )
    assert capsule_create.status_code == 201, capsule_create.text
    capsule = capsule_create.json()

    day = datetime.now(timezone.utc).date().isoformat()
    quota_key = {"tenant_id": admin_a["user"]["tenant_id"], "user_id": admin_a["user"]["id"], "day": day}

    for field, path, payload in (
        ("tts", "/api/tts", {"text": "TEST quota tts"}),
        ("transcriptions", f"/api/capsules/{capsule['id']}/transcribe", None),
        ("audio_uploads", f"/api/capsules/{capsule['id']}/audio", None),
    ):
        base = {"transcriptions": 0, "tts": 0, "audio_uploads": 0, **quota_key}
        limit = 100 if field in {"tts", "audio_uploads"} else 30
        base[field] = limit
        mongo.usage_quotas.update_one(quota_key, {"$set": base}, upsert=True)

        if payload:
            response = requests.post(
                f"{BASE_URL}{path}",
                headers=auth(admin_a["access_token"]),
                json=payload,
                timeout=20,
            )
        else:
            response = requests.post(
                f"{BASE_URL}{path}",
                headers=auth(admin_a["access_token"]),
                files={"file": ("clip.m4a", io.BytesIO(b"abcd"), "audio/m4a")},
                timeout=20,
            )
        assert response.status_code == 429, (field, response.status_code, response.text)
        assert response.headers.get("Retry-After") == "86400"

    requests.delete(f"{BASE_URL}/api/capsules/{capsule['id']}", headers=auth(admin_a["access_token"]), timeout=20)
    requests.delete(f"{BASE_URL}/api/residents/{resident['id']}", headers=auth(admin_a["access_token"]), timeout=20)


def test_share_replacement_public_access_revocation_and_cors_allowlist():
    _assert_env()
    admin_a = login(ADMIN_A_EMAIL, ADMIN_A_PASSWORD)
    mongo = MongoClient(MONGO_URL)[DB_NAME]

    resident_create = requests.post(
        f"{BASE_URL}/api/residents",
        headers=auth(admin_a["access_token"]),
        json={"display_name": f"TEST_SHARE_{uuid.uuid4().hex[:8]}", "consent_status": "obtained"},
        timeout=20,
    )
    assert resident_create.status_code == 201, resident_create.text
    resident = resident_create.json()

    capsule_create = requests.post(
        f"{BASE_URL}/api/capsules",
        headers=auth(admin_a["access_token"]),
        json={
            "resident_id": resident["id"],
            "mode": "free",
            "title": "TEST share replace",
            "duration_sec": 2,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
        timeout=20,
    )
    assert capsule_create.status_code == 201, capsule_create.text
    capsule = capsule_create.json()

    mongo.capsules.update_one({"id": capsule["id"]}, {"$set": {"storage_path": f"test/share/{capsule['id']}.m4a"}})

    share_1 = requests.post(
        f"{BASE_URL}/api/capsules/{capsule['id']}/share",
        headers=auth(admin_a["access_token"]),
        timeout=20,
    )
    assert share_1.status_code == 200, share_1.text

    share_2 = requests.post(
        f"{BASE_URL}/api/capsules/{capsule['id']}/share",
        headers=auth(admin_a["access_token"]),
        timeout=20,
    )
    assert share_2.status_code == 200, share_2.text

    public_old = requests.get(f"{BASE_URL}{share_1.json()['path']}", timeout=20)
    assert public_old.status_code == 404
    public_new = requests.get(f"{BASE_URL}{share_2.json()['path']}", timeout=20)
    assert public_new.status_code == 200

    revoke = requests.delete(
        f"{BASE_URL}/api/shares/{share_2.json()['share_id']}",
        headers=auth(admin_a["access_token"]),
        timeout=20,
    )
    assert revoke.status_code == 200
    public_after_revoke = requests.get(f"{BASE_URL}{share_2.json()['path']}", timeout=20)
    assert public_after_revoke.status_code == 404

    expires = datetime.fromisoformat(share_2.json()["expires_at"])
    assert 29 <= (expires - datetime.now(timezone.utc)).days <= 30

    allowed = requests.options(
        f"{BASE_URL}/api/residents",
        headers={
            "Origin": "https://ehpad-recall.preview.emergentagent.com",
            "Access-Control-Request-Method": "GET",
        },
        timeout=20,
    )
    assert allowed.headers.get("access-control-allow-origin") == "https://ehpad-recall.preview.emergentagent.com"

    requests.delete(f"{BASE_URL}/api/capsules/{capsule['id']}", headers=auth(admin_a["access_token"]), timeout=20)
    requests.delete(f"{BASE_URL}/api/residents/{resident['id']}", headers=auth(admin_a["access_token"]), timeout=20)
