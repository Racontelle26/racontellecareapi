import os
import io
import time
import pytest
import requests

PUBLIC_BACKEND_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL")

def _rand():
    return str(int(time.time() * 1000))

@pytest.fixture(scope="session")
def base_url():
    if not PUBLIC_BACKEND_URL:
        pytest.skip("EXPO_PUBLIC_BACKEND_URL is required for public-endpoint testing")
    return PUBLIC_BACKEND_URL.rstrip("/") + "/api"

@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s

@pytest.fixture(scope="session")
def owner_creds():
    stamp = _rand()
    return {
        "email": f"TEST_owner_{stamp}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": "Owner Test",
        "relationship_label": "Grand-père",
        "accept_terms": True,
    }

@pytest.fixture(scope="session")
def member_creds():
    stamp = _rand()
    return {
        "email": f"TEST_member_{stamp}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": "Member Test",
        "relationship_label": "Petit-fils",
        "accept_terms": True,
    }

@pytest.fixture(scope="session")
def other_creds():
    stamp = _rand()
    return {
        "email": f"TEST_other_{stamp}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": "Other Test",
        "relationship_label": "Amie",
        "accept_terms": True,
    }

@pytest.fixture(scope="session")
def owner_ctx(base_url, session, owner_creds):
    """Register owner + create a circle. Returns dict with token/user/member/circle."""
    r = session.post(f"{base_url}/auth/register", json=owner_creds)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    rc = session.post(f"{base_url}/circles", json={"name": "Famille Test"}, headers=headers)
    assert rc.status_code == 200, rc.text
    circle_data = rc.json()
    return {
        "token": token,
        "headers": headers,
        "user": r.json()["user"],
        "circle": circle_data["circle"],
        "member": circle_data["member"],
    }

@pytest.fixture(scope="session")
def member_ctx(base_url, session, member_creds, owner_ctx):
    """Register member + accept invite from owner."""
    r = session.post(f"{base_url}/auth/register", json=member_creds)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # owner sends invite
    inv = session.post(
        f"{base_url}/circle/invitations",
        json={"display_name": "Member Test", "email": member_creds["email"], "relationship_label": "Petit-fils"},
        headers=owner_ctx["headers"],
    )
    assert inv.status_code == 200, inv.text
    code = inv.json()["code"]
    # accept
    acc = session.post(f"{base_url}/invitations/accept", json={"code": code}, headers=headers)
    assert acc.status_code == 200, acc.text
    return {
        "token": token,
        "headers": headers,
        "user": r.json()["user"],
        "invite_code": code,
        "circle": acc.json()["circle"],
    }

@pytest.fixture(scope="session")
def other_ctx(base_url, session, other_creds):
    """Third user in a different circle (for isolation tests)."""
    r = session.post(f"{base_url}/auth/register", json=other_creds)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    rc = session.post(f"{base_url}/circles", json={"name": "Autre Famille"}, headers=headers)
    assert rc.status_code == 200, rc.text
    return {"token": token, "headers": headers, "user": r.json()["user"],
            "circle": rc.json()["circle"], "member": rc.json()["member"]}

def wav_bytes():
    # tiny valid-ish WAV (44 byte header + a bit of data)
    header = (
        b"RIFF" + (36 + 16).to_bytes(4, "little") + b"WAVEfmt "
        + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
        + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (16).to_bytes(4, "little") + b"\x00" * 16
    )
    return header
