"""Iteration 5 backend regression: auth, circle, daily, questions, capsules, photos, book, prefs."""

import os
import time
import requests
import pytest


def _rand() -> str:
    return str(int(time.time() * 1000))


def _wav_bytes() -> bytes:
    return (
        b"RIFF" + (36 + 16).to_bytes(4, "little") + b"WAVEfmt "
        + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
        + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (16).to_bytes(4, "little") + b"\x00" * 16
    )


def _png_1x1() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x8c\xdcF9"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture(scope="session")
def api_base_url() -> str:
    backend_url = os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    if not backend_url:
        pytest.skip("EXPO_PUBLIC_BACKEND_URL is required for public-endpoint testing")
    return backend_url.rstrip("/") + "/api"


@pytest.fixture(scope="session")
def api_session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


@pytest.fixture(scope="session")
def owner_ctx(api_base_url, api_session):
    stamp = _rand()
    creds = {
        "email": f"TEST_i5_owner_{stamp}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": "Owner I5",
        "relationship_label": "Parent",
        "accept_terms": True,
    }
    r = api_session.post(f"{api_base_url}/auth/register", json=creds)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    c = api_session.post(f"{api_base_url}/circles", json={"name": "Famille I5"}, headers=headers)
    assert c.status_code == 200, c.text
    circle = c.json()["circle"]
    member = c.json()["member"]
    return {"creds": creds, "token": token, "headers": headers, "circle": circle, "member": member}


@pytest.fixture(scope="session")
def member_ctx(api_base_url, api_session, owner_ctx):
    stamp = _rand()
    creds = {
        "email": f"TEST_i5_member_{stamp}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": "Membre I5",
        "relationship_label": "Enfant",
        "accept_terms": True,
    }
    r = api_session.post(f"{api_base_url}/auth/register", json=creds)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    inv = api_session.post(
        f"{api_base_url}/circle/invitations",
        json={"display_name": "Membre I5", "email": creds["email"], "relationship_label": "Enfant"},
        headers=owner_ctx["headers"],
    )
    assert inv.status_code == 200, inv.text
    code = inv.json()["code"]
    acc = api_session.post(f"{api_base_url}/invitations/accept", json={"code": code}, headers=headers)
    assert acc.status_code == 200, acc.text
    return {"creds": creds, "token": token, "headers": headers}


@pytest.fixture(scope="session")
def outsider_ctx(api_base_url, api_session):
    stamp = _rand()
    creds = {
        "email": f"TEST_i5_out_{stamp}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": "Outsider I5",
        "relationship_label": "Ami",
        "accept_terms": True,
    }
    r = api_session.post(f"{api_base_url}/auth/register", json=creds)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    c = api_session.post(f"{api_base_url}/circles", json={"name": "Autre I5"}, headers=headers)
    assert c.status_code == 200, c.text
    return {"token": token, "headers": headers}


# Auth / basic health
def test_api_root_and_auth_me(api_base_url, api_session, owner_ctx):
    root = api_session.get(f"{api_base_url}/")
    assert root.status_code == 200
    me = api_session.get(f"{api_base_url}/auth/me", headers=owner_ctx["headers"])
    assert me.status_code == 200
    assert me.json().get("has_circle") is True


def test_auth_login_success(api_base_url, api_session, owner_ctx):
    r = api_session.post(
        f"{api_base_url}/auth/login",
        json={"email": owner_ctx["creds"]["email"], "password": owner_ctx["creds"]["password"]},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


# Circle / questions / daily
def test_circle_daily_and_questions(api_base_url, api_session, owner_ctx):
    circle = api_session.get(f"{api_base_url}/circle", headers=owner_ctx["headers"])
    assert circle.status_code == 200
    assert circle.json()["circle"]["name"] == "Famille I5"

    themes = api_session.get(f"{api_base_url}/themes", headers=owner_ctx["headers"])
    assert themes.status_code == 200
    assert len(themes.json()) > 0

    first_theme = themes.json()[0]["theme"]
    qs = api_session.get(f"{api_base_url}/questions", params={"theme": first_theme}, headers=owner_ctx["headers"])
    assert qs.status_code == 200
    assert all(q["theme"] == first_theme for q in qs.json())

    daily = api_session.get(f"{api_base_url}/daily-question", headers=owner_ctx["headers"])
    assert daily.status_code == 200
    assert 1 <= len(daily.json()["items"]) <= 3


def test_daily_skip_state(api_base_url, api_session, owner_ctx):
    daily = api_session.get(f"{api_base_url}/daily-question", headers=owner_ctx["headers"]).json()["items"]
    daily_id = daily[0]["daily_question_id"]
    patch = api_session.patch(
        f"{api_base_url}/daily-question/state",
        json={"daily_question_id": daily_id, "state": "skipped"},
        headers=owner_ctx["headers"],
    )
    assert patch.status_code == 200
    confirm = api_session.get(f"{api_base_url}/daily-question", headers=owner_ctx["headers"]).json()["items"]
    item = next(i for i in confirm if i["daily_question_id"] == daily_id)
    assert item["my_state"] == "skipped"


# Capsules / multipart / protected media
def test_capsule_create_and_persistence(api_base_url, api_session, owner_ctx):
    members = api_session.get(f"{api_base_url}/circle/members", headers=owner_ctx["headers"]).json()
    narrator_id = next(m["id"] for m in members if m["status"] == "active")
    daily = api_session.get(f"{api_base_url}/daily-question", headers=owner_ctx["headers"]).json()["items"][0]
    files = {"file": ("memo.wav", _wav_bytes(), "audio/wav")}
    data = {
        "narrator_member_id": narrator_id,
        "duration_sec": "2",
        "daily_question_id": daily["daily_question_id"],
        "question_id": daily["question"]["id"],
        "theme": daily["theme"],
        "title": "TEST I5 quotidien",
    }
    create = api_session.post(f"{api_base_url}/capsules", data=data, files=files, headers=owner_ctx["headers"])
    assert create.status_code == 200, create.text
    cap = create.json()
    cap_id = cap["id"]

    get_one = api_session.get(f"{api_base_url}/capsules/{cap_id}", headers=owner_ctx["headers"])
    assert get_one.status_code == 200
    assert get_one.json()["id"] == cap_id

    list_all = api_session.get(f"{api_base_url}/capsules", headers=owner_ctx["headers"])
    assert list_all.status_code == 200
    assert any(c["id"] == cap_id for c in list_all.json())

    refreshed_daily = api_session.get(f"{api_base_url}/daily-question", headers=owner_ctx["headers"]).json()["items"]
    d_item = next(i for i in refreshed_daily if i["daily_question_id"] == daily["daily_question_id"])
    assert d_item["my_state"] == "answered"
    pytest.cap_id_main = cap_id


def test_capsule_create_with_multiple_photos(api_base_url, api_session, owner_ctx):
    members = api_session.get(f"{api_base_url}/circle/members", headers=owner_ctx["headers"]).json()
    narrator_id = next(m["id"] for m in members if m["status"] == "active")
    daily = api_session.get(f"{api_base_url}/daily-question", headers=owner_ctx["headers"]).json()["items"][0]
    files = [
        ("file", ("memo2.wav", _wav_bytes(), "audio/wav")),
        ("photos", ("p1.png", _png_1x1(), "image/png")),
        ("photos", ("p2.png", _png_1x1(), "image/png")),
    ]
    data = {
        "narrator_member_id": narrator_id,
        "duration_sec": "3",
        "daily_question_id": daily["daily_question_id"],
        "question_id": daily["question"]["id"],
        "theme": daily["theme"],
        "title": "TEST I5 photos",
    }
    create = api_session.post(f"{api_base_url}/capsules", data=data, files=files, headers=owner_ctx["headers"])
    assert create.status_code == 200, create.text
    cap = create.json()
    assert len(cap.get("photos") or []) >= 1
    pytest.cap_id_photo = cap["id"]


def test_audio_protected_and_isolated(api_base_url, api_session, owner_ctx, outsider_ctx):
    cap_id = getattr(pytest, "cap_id_main", None)
    assert cap_id
    ok = api_session.get(f"{api_base_url}/capsules/{cap_id}/audio", params={"token": owner_ctx["token"]})
    assert ok.status_code == 200
    assert ok.headers.get("content-type", "").startswith("audio")
    bad = api_session.get(f"{api_base_url}/capsules/{cap_id}/audio", params={"token": "bad-token"})
    assert bad.status_code == 401
    other = api_session.get(f"{api_base_url}/capsules/{cap_id}/audio", params={"token": outsider_ctx["token"]})
    assert other.status_code in (403, 404)


def test_capsule_search_and_filter(api_base_url, api_session, owner_ctx):
    hit = api_session.get(f"{api_base_url}/capsules", params={"q": "I5"}, headers=owner_ctx["headers"])
    assert hit.status_code == 200
    assert len(hit.json()) >= 1
    miss = api_session.get(f"{api_base_url}/capsules", params={"q": "zzzi5zz"}, headers=owner_ctx["headers"])
    assert miss.status_code == 200
    assert miss.json() == []


def test_photo_delete_and_verify(api_base_url, api_session, owner_ctx):
    cap_id = getattr(pytest, "cap_id_photo", None)
    assert cap_id
    cap = api_session.get(f"{api_base_url}/capsules/{cap_id}", headers=owner_ctx["headers"]).json()
    photos = cap.get("photos") or []
    assert photos
    photo_id = photos[0]["id"]
    deleted = api_session.delete(f"{api_base_url}/capsules/{cap_id}/photos/{photo_id}", headers=owner_ctx["headers"])
    assert deleted.status_code == 200
    after = api_session.get(f"{api_base_url}/capsules/{cap_id}", headers=owner_ctx["headers"]).json()
    assert all(p["id"] != photo_id for p in (after.get("photos") or []))


# Profile / invitations / feedback / book
def test_preferences_feedback_and_invitations(api_base_url, api_session, owner_ctx):
    pref = api_session.patch(
        f"{api_base_url}/me/preferences",
        json={"display_name": "Owner I5 MAJ", "daily_email": False},
        headers=owner_ctx["headers"],
    )
    assert pref.status_code == 200
    assert pref.json()["user"]["display_name"] == "Owner I5 MAJ"

    fb = api_session.post(
        f"{api_base_url}/feedback",
        json={"category": "idea", "rating": 4, "comment": "TEST I5 feedback", "page_context": "app"},
        headers=owner_ctx["headers"],
    )
    assert fb.status_code == 200
    assert fb.json().get("ok") is True

    inv = api_session.post(
        f"{api_base_url}/circle/invitations",
        json={"display_name": "Invite I5", "email": f"test_i5_inv_{_rand()}@racontelle-test.fr"},
        headers=owner_ctx["headers"],
    )
    assert inv.status_code == 200, inv.text
    inv_id = inv.json()["invitation"]["id"]

    listed = api_session.get(f"{api_base_url}/circle/invitations", headers=owner_ctx["headers"])
    assert listed.status_code == 200
    assert any(i["id"] == inv_id for i in listed.json())

    resend = api_session.post(f"{api_base_url}/circle/invitations/{inv_id}/resend", headers=owner_ctx["headers"])
    assert resend.status_code == 200
    revoke = api_session.delete(f"{api_base_url}/circle/invitations/{inv_id}", headers=owner_ctx["headers"])
    assert revoke.status_code == 200


def test_book_generate_read_delete_and_isolation(api_base_url, api_session, owner_ctx, outsider_ctx):
    status = api_session.get(f"{api_base_url}/book/status", headers=owner_ctx["headers"])
    assert status.status_code == 200
    assert status.json()["can_generate"] is True

    create = api_session.post(f"{api_base_url}/book/chapters", headers=owner_ctx["headers"], timeout=120)
    assert create.status_code == 200, create.text
    chapter = create.json()
    chapter_id = chapter["id"]

    listed = api_session.get(f"{api_base_url}/book/chapters", headers=owner_ctx["headers"])
    assert listed.status_code == 200
    assert any(c["id"] == chapter_id for c in listed.json())

    get_one = api_session.get(f"{api_base_url}/book/chapters/{chapter_id}", headers=owner_ctx["headers"])
    assert get_one.status_code == 200
    assert get_one.json()["id"] == chapter_id

    isolated = api_session.get(f"{api_base_url}/book/chapters/{chapter_id}", headers=outsider_ctx["headers"])
    assert isolated.status_code == 404

    deleted = api_session.delete(f"{api_base_url}/book/chapters/{chapter_id}", headers=owner_ctx["headers"])
    assert deleted.status_code == 200
    after = api_session.get(f"{api_base_url}/book/chapters/{chapter_id}", headers=owner_ctx["headers"])
    assert after.status_code == 404
