"""Iteration 18: N+1 regression checks for capsules listing and chapter generation."""

import time
import os
import requests
import pytest
from dotenv import dotenv_values

import server


@pytest.fixture(scope="session")
def base_url() -> str:
    frontend_env = dotenv_values("/app/frontend/.env")
    backend_url = os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL") or frontend_env.get("EXPO_PUBLIC_BACKEND_URL")
    if not backend_url:
        pytest.skip("EXPO_PUBLIC_BACKEND_URL is required for public-endpoint testing")
    return backend_url.rstrip("/") + "/api"


def _stamp() -> str:
    return str(int(time.time() * 1000))


def _wav_bytes() -> bytes:
    return (
        b"RIFF" + (36 + 16).to_bytes(4, "little") + b"WAVEfmt "
        + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
        + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (16).to_bytes(4, "little") + b"\x00" * 16
    )


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _register_and_create_circle(base_url: str, session: requests.Session):
    stamp = _stamp()
    creds = {
        "email": f"TEST_i18_{stamp}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": "TEST I18 Owner",
        "relationship_label": "Parent",
        "accept_terms": True,
    }
    reg = session.post(f"{base_url}/auth/register", json=creds)
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    create = session.post(
        f"{base_url}/circles",
        json={
            "name": f"Famille TEST I18 {stamp}",
            "initial_members": [{"display_name": "TEST I18 Proche", "relationship_label": "Frère"}],
        },
        headers=headers,
    )
    assert create.status_code == 200, create.text
    return {"token": token, "headers": headers, "circle": create.json()["circle"]}


def _create_capsule(base_url: str, session: requests.Session, headers: dict, narrator_id: str, *, title: str, question=None, photo=False):
    data = {"narrator_member_id": narrator_id, "duration_sec": "3", "title": title}
    if question:
        data.update(question)
    files = [("file", ("memo.wav", _wav_bytes(), "audio/wav"))]
    if photo:
        files.append(("photos", ("photo.jpg", _jpeg_bytes(), "image/jpeg")))
    resp = session.post(f"{base_url}/capsules", headers=headers, data=data, files=files)
    assert resp.status_code == 200, resp.text
    return resp.json()


# Capsules API behavior: 0/1/multiple + filters/search + response shape and ObjectId hygiene
def test_capsules_list_zero_one_many_and_filters(base_url):
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    ctx = _register_and_create_circle(base_url, session)

    members = session.get(f"{base_url}/circle/members", headers=ctx["headers"])
    assert members.status_code == 200, members.text
    member_items = members.json()
    owner_member = next(item for item in member_items if item["role"] == "owner")
    profile_member = next(item for item in member_items if item["role"] == "profile")

    empty = session.get(f"{base_url}/capsules", headers=ctx["headers"])
    assert empty.status_code == 200, empty.text
    assert empty.json() == []

    questions = session.get(f"{base_url}/questions", headers=ctx["headers"])
    assert questions.status_code == 200, questions.text
    q0 = questions.json()[0]

    c1 = _create_capsule(
        base_url,
        session,
        ctx["headers"],
        owner_member["id"],
        title="TEST_I18_UNIQUE_ONE",
        question={"question_id": q0["id"], "theme": q0["theme"]},
        photo=True,
    )
    one = session.get(f"{base_url}/capsules", headers=ctx["headers"])
    assert one.status_code == 200, one.text
    one_items = one.json()
    assert len(one_items) == 1
    first = one_items[0]
    assert first["id"] == c1["id"]
    assert first["narrator_name"] == owner_member["display_name"]
    assert first["narrator_color"] == owner_member.get("initials_color")
    assert first["question_text"]
    assert first["audio_url"].startswith(f"/api/capsules/{c1['id']}/audio")
    assert first["photo_url"] is not None
    assert first["photos"][0]["url"].startswith(f"/api/capsules/{c1['id']}/photos/")
    assert "_id" not in first

    _create_capsule(base_url, session, ctx["headers"], profile_member["id"], title="TEST_I18_UNIQUE_TWO")
    _create_capsule(base_url, session, ctx["headers"], owner_member["id"], title="TEST_I18_UNIQUE_THREE")

    many = session.get(f"{base_url}/capsules", headers=ctx["headers"])
    assert many.status_code == 200, many.text
    many_items = many.json()
    assert len(many_items) >= 3
    for item in many_items:
        assert "_id" not in item
        assert item["audio_url"].startswith("/api/capsules/")
        assert "question_text" in item

    by_narrator = session.get(
        f"{base_url}/capsules",
        params={"narrator": profile_member["id"]},
        headers=ctx["headers"],
    )
    assert by_narrator.status_code == 200, by_narrator.text
    narrator_items = by_narrator.json()
    assert len(narrator_items) >= 1
    assert all(item["narrator_member_id"] == profile_member["id"] for item in narrator_items)

    by_theme = session.get(f"{base_url}/capsules", params={"theme": q0["theme"]}, headers=ctx["headers"])
    assert by_theme.status_code == 200, by_theme.text
    theme_items = by_theme.json()
    assert len(theme_items) >= 1
    assert all(item.get("theme") == q0["theme"] for item in theme_items)

    search = session.get(f"{base_url}/capsules", params={"q": "UNIQUE_TWO"}, headers=ctx["headers"])
    assert search.status_code == 200, search.text
    search_items = search.json()
    assert len(search_items) >= 1
    assert any("UNIQUE_TWO" in (item.get("question_text") or "") or "UNIQUE_TWO" in (item.get("title") or "") for item in search_items)


# Capsule detail/edit/photo flows using _enrich_capsule fallback (single-item enrich)
def test_capsule_get_patch_add_photo_regression(base_url):
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    ctx = _register_and_create_circle(base_url, session)

    members = session.get(f"{base_url}/circle/members", headers=ctx["headers"])
    assert members.status_code == 200, members.text
    owner_member = next(item for item in members.json() if item["role"] == "owner")

    created = _create_capsule(
        base_url,
        session,
        ctx["headers"],
        owner_member["id"],
        title="TEST_I18_EDITABLE",
    )
    cap_id = created["id"]

    get_cap = session.get(f"{base_url}/capsules/{cap_id}", headers=ctx["headers"])
    assert get_cap.status_code == 200, get_cap.text
    assert get_cap.json()["id"] == cap_id
    assert "_id" not in get_cap.json()

    patch = session.patch(
        f"{base_url}/capsules/{cap_id}",
        headers=ctx["headers"],
        json={"title": "TEST_I18_EDITED", "narrator_member_id": owner_member["id"]},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["title"] == "TEST_I18_EDITED"

    add_photo = session.post(
        f"{base_url}/capsules/{cap_id}/photos",
        headers=ctx["headers"],
        files=[("photos", ("added.jpg", _jpeg_bytes(), "image/jpeg"))],
    )
    assert add_photo.status_code == 200, add_photo.text
    updated = add_photo.json()
    assert len(updated["photos"]) >= 1
    assert updated["photo_url"].startswith(f"/api/capsules/{cap_id}/photos/")


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, _limit):
        return list(self._docs)


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.find_calls = 0
        self.find_one_calls = 0
        self.inserted = []

    def find(self, *_args, **_kwargs):
        self.find_calls += 1
        return _FakeCursor(self.docs)

    async def find_one(self, query, *_args, **_kwargs):
        self.find_one_calls += 1
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    async def insert_one(self, doc):
        self.inserted.append(dict(doc))


class _FakeQuestionsCollection(_FakeCollection):
    def find(self, query, *_args, **_kwargs):
        self.find_calls += 1
        ids = set(query.get("id", {}).get("$in", []))
        docs = [doc for doc in self.docs if doc.get("id") in ids]
        return _FakeCursor(docs)

    async def find_one(self, *_args, **_kwargs):
        self.find_one_calls += 1
        raise AssertionError("generate_chapter/list_capsules should not call questions.find_one in loops")


class _FakeDB:
    def __init__(self):
        self.circles = _FakeCollection([{"id": "circle-1", "name": "Famille Batch"}])
        self.members = _FakeCollection([
            {"id": "m1", "circle_id": "circle-1", "status": "active", "display_name": "Alice", "relationship_label": "Maman", "initials_color": "#AAA"},
            {"id": "m2", "circle_id": "circle-1", "status": "active", "display_name": "Paul", "relationship_label": "Papa", "initials_color": "#BBB"},
        ])
        self.capsules = _FakeCollection([
            {"id": "c1", "circle_id": "circle-1", "status": "saved", "narrator_member_id": "m1", "question_id": "q1", "theme": "Famille", "recorded_at": "2026-01-01T00:00:00Z", "duration_sec": 4, "title": "Souvenir 1", "transcript": "Texte 1", "photos": []},
            {"id": "c2", "circle_id": "circle-1", "status": "saved", "narrator_member_id": "m2", "question_id": "q2", "theme": "Enfance", "recorded_at": "2026-01-02T00:00:00Z", "duration_sec": 6, "title": "Souvenir 2", "transcript": "Texte 2", "photos": []},
        ])
        self.questions = _FakeQuestionsCollection([
            {"id": "q1", "text": "Question une"},
            {"id": "q2", "text": "Question deux"},
        ])
        self.book_chapters = _FakeCollection([])
        self.events = _FakeCollection([])


class _FakeChat:
    def with_model(self, *_args, **_kwargs):
        return self

    async def send_message(self, *_args, **_kwargs):
        return "# Un titre test\nContenu généré test"


# Instrumentation: list_capsules should batch queries (capsules + members + questions) with no per-item find_one
@pytest.mark.anyio
async def test_list_capsules_executes_batched_queries_without_find_one_loop(monkeypatch):
    fake_db = _FakeDB()

    async def _fake_get_member(_user):
        return {"circle_id": "circle-1"}

    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(server, "get_member", _fake_get_member)

    result = await server.list_capsules(user={"id": "u1"})
    assert len(result) == 2
    assert fake_db.capsules.find_calls == 1
    assert fake_db.members.find_calls <= 1
    assert fake_db.questions.find_calls <= 1
    assert fake_db.members.find_one_calls == 0
    assert fake_db.questions.find_one_calls == 0


# Instrumentation: generate_chapter preloads questions once via $in and keeps output structure
@pytest.mark.anyio
async def test_generate_chapter_preloads_questions_once_and_preserves_structure(monkeypatch):
    fake_db = _FakeDB()

    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(server, "LlmChat", lambda *args, **kwargs: _FakeChat())

    chapter = await server.generate_chapter("circle-1")
    assert chapter["title"] == "Un titre test"
    assert chapter["content"] == "Contenu généré test"
    assert chapter["used_capsule_ids"] == ["c1", "c2"]
    assert chapter["memory_count"] == 2
    assert fake_db.questions.find_calls == 1
    assert fake_db.questions.find_one_calls == 0
    assert len(fake_db.book_chapters.inserted) == 1


# Book APIs smoke without triggering expensive generation: status/list/get existing chapters
def test_book_status_list_and_get_existing_chapter_without_generation(base_url):
    session = requests.Session()
    login = session.post(
        f"{base_url}/auth/login",
        json={"email": "verification@racontelle.fr", "password": "Souvenir123"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    status = session.get(f"{base_url}/book/status", headers=headers)
    assert status.status_code == 200, status.text
    status_payload = status.json()
    assert "memory_count" in status_payload
    assert "chapter_count" in status_payload
    assert "can_generate" in status_payload
    assert "_id" not in status_payload

    chapters = session.get(f"{base_url}/book/chapters", headers=headers)
    assert chapters.status_code == 200, chapters.text
    chapter_items = chapters.json()
    assert isinstance(chapter_items, list)
    if chapter_items:
        chapter_id = chapter_items[0]["id"]
        detail = session.get(f"{base_url}/book/chapters/{chapter_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        assert payload["id"] == chapter_id
        assert payload.get("title")
        assert payload.get("content")
        assert isinstance(payload.get("used_capsule_ids"), list)
        assert "_id" not in payload
