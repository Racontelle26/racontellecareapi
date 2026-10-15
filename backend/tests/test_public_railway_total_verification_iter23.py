"""Public Railway regression checks for full verification without authenticated account."""

from __future__ import annotations

import os
import uuid

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
PUBLIC_ORIGIN = "https://ehpad-recall.preview.emergentagent.com"
UNKNOWN_ORIGIN = "https://malicious.example.invalid"


@pytest.fixture(scope="session", autouse=True)
def authenticated_requests():
    """Override global auth fixture: this module validates only public/no-auth behavior."""
    yield


# Module: public Railway health/OpenAPI/contracts
def test_api_root_five_times_without_502_and_consistent_payload():
    for _ in range(5):
        response = requests.get(f"{BASE_URL}/api/", timeout=20)
        assert response.status_code == 200
        assert response.status_code != 502
        payload = response.json()
        assert payload.get("message") == "Racontelle Care API"
        assert payload.get("offline_first") is True


def test_openapi_is_public_and_password_routes_present():
    response = requests.get(f"{BASE_URL}/openapi.json", timeout=20)
    assert response.status_code == 200
    paths = response.json().get("paths", {})
    assert "/api/auth/password/forgot" in paths
    assert "/api/auth/password/reset" in paths


def test_residents_endpoint_rejects_anonymous_access():
    response = requests.get(f"{BASE_URL}/api/residents", timeout=20)
    assert response.status_code == 401


def test_invalid_share_token_returns_404():
    token = f"invalid-{uuid.uuid4().hex}"
    response = requests.get(f"{BASE_URL}/api/share/{token}", timeout=20)
    assert response.status_code == 404


def test_forgot_password_returns_200_for_nonexistent_email_without_claiming_delivery():
    email = f"inexistant-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    response = requests.post(
        f"{BASE_URL}/api/auth/password/forgot",
        headers={"X-Client-Platform": "web"},
        json={"email": email},
        timeout=20,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("ok") is True
    assert "Si un compte existe" in payload.get("message", "")


# Module: CORS and security headers from public backend
def test_cors_allows_public_origin_for_login_preflight():
    response = requests.options(
        f"{BASE_URL}/api/auth/login",
        headers={
            "Origin": PUBLIC_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=20,
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == PUBLIC_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_rejects_unknown_origin_for_login_preflight():
    response = requests.options(
        f"{BASE_URL}/api/auth/login",
        headers={
            "Origin": UNKNOWN_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=20,
    )
    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None


def test_security_headers_include_nosniff_and_referrer_policy():
    response = requests.get(f"{BASE_URL}/api/", timeout=20)
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("referrer-policy") == "no-referrer"
