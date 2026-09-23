"""Iteration 17 - Branding rename and core API regression checks."""

import os

import pytest
import requests
from dotenv import load_dotenv


# Load public URL from frontend env (no hardcoded fallback)
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL")
TEST_EMAIL = "verification@racontelle.fr"
TEST_PASSWORD = "Souvenir123"


@pytest.fixture(scope="session")
def api_base_url():
    if not BASE_URL:
        pytest.skip("EXPO_PUBLIC_BACKEND_URL is required")
    return BASE_URL.rstrip("/") + "/api"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


# Auth and session module checks
@pytest.fixture(scope="session")
def auth_ctx(api_base_url, session):
    login = session.post(
        f"{api_base_url}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200, login.text
    payload = login.json()
    token = payload.get("access_token")
    assert token
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}}


# API branding checks
def test_root_message_is_racontelle(api_base_url, session):
    resp = session.get(f"{api_base_url}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["message"] == "Racontelle API"


def test_root_message_has_no_legacy_brand(api_base_url, session):
    resp = session.get(f"{api_base_url}/")
    assert resp.status_code == 200
    message = resp.json().get("message", "")
    assert "family stories" not in message.lower()
    assert "racontelle family" not in message.lower()


def test_openapi_title_is_racontelle(api_base_url, session):
    resp = session.get(f"{api_base_url}/openapi.json")
    if resp.status_code == 200:
        title = resp.json().get("info", {}).get("title")
        assert title == "Racontelle API"
        return
    # Public ingress may not expose OpenAPI under /api; verify FastAPI title from source.
    with open("/app/backend/server.py", "r", encoding="utf-8") as fh:
        source = fh.read()
    assert 'FastAPI(title="Racontelle API")' in source


# Login/session regression checks
def test_login_still_works_with_verified_credentials(api_base_url, session):
    resp = session.post(
        f"{api_base_url}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload.get("access_token"), str) and len(payload["access_token"]) > 20
    assert payload.get("user", {}).get("email") == TEST_EMAIL


def test_auth_me_still_returns_session_user(api_base_url, session, auth_ctx):
    resp = session.get(f"{api_base_url}/auth/me", headers=auth_ctx["headers"])
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["user"]["email"] == TEST_EMAIL


# API route regression checks
def test_questions_route_still_accessible(api_base_url, session, auth_ctx):
    resp = session.get(f"{api_base_url}/questions", headers=auth_ctx["headers"])
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
    assert len(payload) > 0


def test_book_chapters_route_still_accessible(api_base_url, session, auth_ctx):
    resp = session.get(f"{api_base_url}/book/chapters", headers=auth_ctx["headers"])
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_capsules_route_still_accessible(api_base_url, session, auth_ctx):
    resp = session.get(f"{api_base_url}/capsules", headers=auth_ctx["headers"])
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
