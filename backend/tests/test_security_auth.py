from datetime import datetime, timezone
import os
import uuid

from pymongo import MongoClient
import requests


BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def register(label: str):
    email = f"security-{label}-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    password = f"Racontelle-{label}-2026!"
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        headers={"X-Client-Platform": "native"},
        json={
            "email": email,
            "password": password,
            "full_name": f"Test {label}",
            "establishment_name": f"Établissement {label}",
        },
        timeout=30,
    )
    assert response.status_code == 201, response.text
    return response.json(), email, password


def auth(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_sensitive_routes_reject_anonymous_requests():
    for method, path in (
        ("GET", "/api/residents"),
        ("GET", "/api/capsules"),
        ("GET", "/api/questions"),
        ("POST", "/api/tts"),
    ):
        response = requests.request(method, f"{BASE_URL}{path}", json={"text": "test"}, headers={"Authorization": ""}, timeout=20)
        assert response.status_code == 401, (path, response.text)


def test_cross_tenant_and_member_destructive_access_are_blocked():
    tenant_a, _, _ = register("tenant-a")
    tenant_b, _, _ = register("tenant-b")
    resident = requests.post(
        f"{BASE_URL}/api/residents",
        headers=auth(tenant_a["access_token"]),
        json={"display_name": "Résident isolé", "consent_status": "obtained"},
        timeout=20,
    ).json()
    cross = requests.get(
        f"{BASE_URL}/api/residents/{resident['id']}/capsules",
        headers=auth(tenant_b["access_token"]),
        timeout=20,
    )
    assert cross.status_code == 404
    member_email = f"member-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    member_password = "Racontelle-Membre-2026!"
    created = requests.post(
        f"{BASE_URL}/api/auth/members",
        headers=auth(tenant_a["access_token"]),
        json={"email": member_email, "password": member_password, "full_name": "Membre Test"},
        timeout=20,
    )
    assert created.status_code == 201
    member = requests.post(
        f"{BASE_URL}/api/auth/login",
        headers={"X-Client-Platform": "native"},
        json={"email": member_email, "password": member_password},
        timeout=20,
    ).json()
    denied = requests.delete(
        f"{BASE_URL}/api/residents/{resident['id']}",
        headers=auth(member["access_token"]),
        timeout=20,
    )
    assert denied.status_code == 403
    cleanup = requests.delete(
        f"{BASE_URL}/api/residents/{resident['id']}",
        headers=auth(tenant_a["access_token"]),
        timeout=20,
    )
    assert cleanup.status_code == 200


def test_refresh_rotation_rejects_replay():
    session, _, _ = register("refresh")
    first = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        headers={"X-Client-Platform": "native"},
        json={"refresh_token": session["refresh_token"]},
        timeout=20,
    )
    assert first.status_code == 200
    replay = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        headers={"X-Client-Platform": "native"},
        json={"refresh_token": session["refresh_token"]},
        timeout=20,
    )
    assert replay.status_code == 401


def test_share_is_30_days_and_revocable():
    session, _, _ = register("share")
    token = session["access_token"]
    resident = requests.post(
        f"{BASE_URL}/api/residents",
        headers=auth(token),
        json={"display_name": "Partage Test", "consent_status": "obtained"},
        timeout=20,
    ).json()
    capsule = requests.post(
        f"{BASE_URL}/api/capsules",
        headers=auth(token),
        json={"resident_id": resident["id"], "mode": "free", "title": "Lien test", "duration_sec": 1, "recorded_at": datetime.now(timezone.utc).isoformat()},
        timeout=20,
    ).json()
    mongo = MongoClient(MONGO_URL)[DB_NAME]
    mongo.capsules.update_one({"id": capsule["id"]}, {"$set": {"storage_path": "test/dummy.m4a"}})
    share = requests.post(f"{BASE_URL}/api/capsules/{capsule['id']}/share", headers=auth(token), timeout=20)
    assert share.status_code == 200, share.text
    payload = share.json()
    expires = datetime.fromisoformat(payload["expires_at"])
    assert 29 <= (expires - datetime.now(timezone.utc)).days <= 30
    assert requests.get(f"{BASE_URL}{payload['path']}", headers={"Authorization": ""}, timeout=20).status_code == 200
    revoked = requests.delete(f"{BASE_URL}/api/shares/{payload['share_id']}", headers=auth(token), timeout=20)
    assert revoked.status_code == 200
    assert requests.get(f"{BASE_URL}{payload['path']}", headers={"Authorization": ""}, timeout=20).status_code == 404


def test_quota_returns_429_before_costly_operation():
    session, _, _ = register("quota")
    user = session["user"]
    day = datetime.now(timezone.utc).date().isoformat()
    mongo = MongoClient(MONGO_URL)[DB_NAME]
    mongo.usage_quotas.update_one(
        {"tenant_id": user["tenant_id"], "user_id": user["id"], "day": day},
        {"$set": {"tenant_id": user["tenant_id"], "user_id": user["id"], "day": day, "tts": 100, "transcriptions": 0, "audio_uploads": 0}},
        upsert=True,
    )
    response = requests.post(
        f"{BASE_URL}/api/tts",
        headers=auth(session["access_token"]),
        json={"text": "Cette requête doit être bloquée avant génération."},
        timeout=20,
    )
    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "86400"


def test_cors_does_not_allow_unknown_origin():
    response = requests.options(
        f"{BASE_URL}/api/residents",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET", "Authorization": ""},
        timeout=20,
    )
    assert response.headers.get("access-control-allow-origin") is None
