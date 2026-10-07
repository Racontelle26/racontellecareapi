"""Railway backend URL + CORS/public integration regression checks."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests


# Module: frontend environment wiring and API route-prefixing checks
FRONTEND_ENV_PATH = Path("/app/frontend/.env")
FRONTEND_API_TS_PATH = Path("/app/frontend/src/api.ts")

EXPECTED_BACKEND_URL = "https://racontellecareapi-production.up.railway.app"
EXPECTED_PUBLIC_ORIGIN = "https://ehpad-recall.preview.emergentagent.com"
EXPECTED_PROXY_ORIGIN = "https://ehpad-recall.cluster-2.preview.emergentcf.cloud"


@pytest.fixture(scope="session", autouse=True)
def authenticated_requests():
    """Override global auth fixture: this suite validates public/no-auth Railway behavior."""
    yield


def _read_env_map() -> dict[str, str]:
    env = {}
    for raw in FRONTEND_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value.strip().strip('"').strip("'")
    return env


def test_frontend_env_points_exactly_to_railway_without_api_suffix():
    env = _read_env_map()
    assert env.get("EXPO_PUBLIC_BACKEND_URL") == EXPECTED_BACKEND_URL
    assert not env["EXPO_PUBLIC_BACKEND_URL"].endswith("/api")


def test_preview_packager_variables_unchanged():
    env = _read_env_map()
    assert env.get("EXPO_PACKAGER_PROXY_URL") == EXPECTED_PUBLIC_ORIGIN
    assert env.get("EXPO_PACKAGER_HOSTNAME") == EXPECTED_PUBLIC_ORIGIN
    assert EXPECTED_PROXY_ORIGIN != env.get("EXPO_PACKAGER_PROXY_URL")


def test_railway_api_root_health_message():
    response = requests.get(f"{EXPECTED_BACKEND_URL}/api/", timeout=20)
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("message") == "Racontelle Care API"


def test_residents_requires_authentication_without_jwt():
    response = requests.get(f"{EXPECTED_BACKEND_URL}/api/residents", timeout=20)
    assert response.status_code == 401
    payload = response.json()
    assert "detail" in payload


def test_preflight_options_login_allows_public_origin_with_credentials():
    response = requests.options(
        f"{EXPECTED_BACKEND_URL}/api/auth/login",
        headers={
            "Origin": EXPECTED_PUBLIC_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=20,
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == EXPECTED_PUBLIC_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


# Module: frontend API path composition must keep /api prefix centralized in src/api.ts
def test_frontend_api_client_adds_api_prefix_in_code_paths():
    source = FRONTEND_API_TS_PATH.read_text(encoding="utf-8")
    assert "fetch(`${baseUrl}/api${path}`" in source
    assert "fetch(`${baseUrl}/api/auth/${path}`" in source
