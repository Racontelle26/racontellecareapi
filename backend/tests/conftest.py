import os

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
TEST_EMAIL = "admin.security@racontelle.example.com"
TEST_PASSWORD = "Racontelle-Test-2026!"


@pytest.fixture(scope="session", autouse=True)
def authenticated_requests():
    login = requests.post(
        f"{BASE_URL}/api/auth/login",
        headers={"X-Client-Platform": "native"},
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=20,
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    original = requests.sessions.Session.request

    def secured(session, method, url, **kwargs):
        if url.startswith(f"{BASE_URL}/api/") and "/api/auth/" not in url:
            headers = dict(kwargs.pop("headers", {}) or {})
            headers.setdefault("Authorization", f"Bearer {token}")
            kwargs["headers"] = headers
        return original(session, method, url, **kwargs)

    requests.sessions.Session.request = secured
    yield
    requests.sessions.Session.request = original
