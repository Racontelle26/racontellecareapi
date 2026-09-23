import os
import uuid

import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")

# Auth hardening checks: successful admin logins and brute-force throttling behavior.
BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin.security@racontelle.example.com"
ADMIN_PASSWORD = "Racontelle-Test-2026!"


def test_admin_repeated_valid_logins_do_not_return_429():
    statuses = []
    for _ in range(10):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            headers={"X-Client-Platform": "native"},
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=20,
        )
        statuses.append(response.status_code)
    assert all(code == 200 for code in statuses), statuses


def test_distinct_email_bruteforce_is_rate_limited_after_ten_failures():
    email = f"ratelimit-iter12-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    statuses = []
    for _ in range(11):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            headers={"X-Client-Platform": "native"},
            json={"email": email, "password": "Wrong-Password-2026!"},
            timeout=20,
        )
        statuses.append(response.status_code)

    assert statuses[:10] == [401] * 10, statuses
    assert statuses[10] == 429, statuses
