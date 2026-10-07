"""Iteration 21: Railway backend reconnect, CORS preflight, auth smoke, and env wiring checks."""

import time
import json
import requests
from dotenv import dotenv_values


FRONTEND_ENV_PATH = "/app/frontend/.env"
EAS_JSON_PATH = "/app/frontend/eas.json"
EXPECTED_RAILWAY_ORIGIN = "https://racontelle-famille-production.up.railway.app"
EXPECTED_PREVIEW_ORIGIN = "https://family-stories-34.preview.emergentagent.com"


def _frontend_env() -> dict:
    return dict(dotenv_values(FRONTEND_ENV_PATH))


def _api_base() -> str:
    origin = (_frontend_env().get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/")
    return f"{origin}/api"


def _eas_json() -> dict:
    with open(EAS_JSON_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_frontend_env_points_to_exact_railway_origin_and_preserves_protected_vars():
    env = _frontend_env()
    backend_origin = env.get("EXPO_PUBLIC_BACKEND_URL")
    assert backend_origin == EXPECTED_RAILWAY_ORIGIN
    assert not backend_origin.endswith("/")
    assert "/api" not in backend_origin

    assert env.get("EXPO_PACKAGER_PROXY_URL") == EXPECTED_PREVIEW_ORIGIN
    assert env.get("EXPO_PACKAGER_HOSTNAME") == EXPECTED_PREVIEW_ORIGIN


# EAS preview and production build profiles must both target Railway backend.
def test_eas_profiles_preview_and_production_point_to_railway_origin():
    eas = _eas_json()
    preview_url = eas["build"]["preview"]["env"]["EXPO_PUBLIC_BACKEND_URL"]
    production_url = eas["build"]["production"]["env"]["EXPO_PUBLIC_BACKEND_URL"]

    assert preview_url == EXPECTED_RAILWAY_ORIGIN
    assert production_url == EXPECTED_RAILWAY_ORIGIN


# Railway public API health and branding response.
def test_railway_api_root_health_smoke():
    response = requests.get(f"{_api_base()}/", timeout=20)
    assert response.status_code == 200
    body = response.json()
    assert "Racontelle API" in (body.get("name") or body.get("message") or "")


# CORS preflight from preview origin to Railway auth login.
def test_preflight_cors_from_preview_origin_on_auth_login():
    response = requests.options(
        f"{_api_base()}/auth/login",
        headers={
            "Origin": EXPECTED_PREVIEW_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == EXPECTED_PREVIEW_ORIGIN


# Existing Railway verification account login and has_circle=false profile check.
def test_railway_login_and_auth_me_for_verification_account():
    email = "verification.railway@racontelle.fr"
    password = "Souvenir123"

    login = requests.post(
        f"{_api_base()}/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    assert login.status_code == 200
    login_json = login.json()
    assert "access_token" in login_json
    assert login_json.get("user", {}).get("email") == email

    token = login_json["access_token"]
    me = requests.get(
        f"{_api_base()}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert me.status_code == 200
    me_json = me.json()
    assert me_json.get("user", {}).get("email") == email
    assert me_json.get("has_circle") is False


# Fresh register smoke on Railway, then immediate /auth/me persistence validation.
def test_railway_register_unique_user_and_me_round_trip():
    stamp = str(int(time.time() * 1000))
    email = f"preview.signup.railway.{stamp}@racontelle.fr"
    payload = {
        "email": email,
        "password": "Souvenir123",
        "display_name": "Test Railway Signup",
        "relationship_label": "Parent",
        "accept_terms": True,
    }

    register = requests.post(f"{_api_base()}/auth/register", json=payload, timeout=25)
    assert register.status_code == 200
    register_json = register.json()
    assert register_json.get("user", {}).get("email") == email
    assert "access_token" in register_json

    token = register_json["access_token"]
    me = requests.get(
        f"{_api_base()}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert me.status_code == 200
    assert me.json().get("user", {}).get("email") == email