import os

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
TEST_EMAIL = os.environ.get("RAILWAY_TEST_EMAIL")
TEST_PASSWORD = os.environ.get("RAILWAY_TEST_PASSWORD")
_token: dict = {}


@pytest.fixture(scope="session", autouse=True)
def authenticated_requests():
    if not TEST_EMAIL or not TEST_PASSWORD:
        pytest.skip("RAILWAY_TEST_EMAIL et RAILWAY_TEST_PASSWORD requis pour les suites authentifiées")
    login = requests.post(
        f"{BASE_URL}/api/auth/login",
        headers={"X-Client-Platform": "native"},
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=20,
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    _token["value"] = token
    original = requests.sessions.Session.request

    def secured(session, method, url, **kwargs):
        if url.startswith(f"{BASE_URL}/api/") and "/api/auth/" not in url:
            headers = dict(kwargs.pop("headers", {}) or {})
            headers.setdefault("Authorization", f"Bearer {token}")
            kwargs["headers"] = headers
        return original(session, method, url, **kwargs)

    requests.sessions.Session.request = secured
    # Les fonctions hors bêta sont désactivées par défaut : l'établissement de
    # test les active pour que la non-régression les couvre.
    enabled = requests.patch(
        f"{BASE_URL}/api/settings",
        json={"family_share": True, "transcription": True, "carnet_pdf": True, "voice_reading": True, "quiz": True},
        timeout=20,
    )
    assert enabled.status_code == 200, enabled.text
    yield
    requests.sessions.Session.request = original


@pytest.fixture(scope="module", autouse=True)
def fresh_resident_slots(authenticated_requests):
    """La bêta limite l'établissement à 5 profils actifs : chaque module de
    test repart d'un établissement vide (profils archivés, jamais effacés)."""
    residents = requests.get(f"{BASE_URL}/api/residents", timeout=20)
    if residents.status_code == 200:
        for resident in residents.json():
            requests.delete(f"{BASE_URL}/api/residents/{resident['id']}", timeout=20)
    yield
