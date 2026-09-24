"""Iteration 19: STT fallback, manual transcript flows, permissions, and book status checks."""

import os
import time
import requests
import pytest
from dotenv import dotenv_values

import server


def _env_backend_url() -> str | None:
    frontend_env = dotenv_values("/app/frontend/.env")
    return (
        os.environ.get("EXPO_BACKEND_URL")
        or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
        or frontend_env.get("EXPO_BACKEND_URL")
        or frontend_env.get("EXPO_PUBLIC_BACKEND_URL")
    )


@pytest.fixture(scope="session")
def base_url() -> str:
    backend_url = _env_backend_url()
    if not backend_url:
        pytest.skip("EXPO_BACKEND_URL/EXPO_PUBLIC_BACKEND_URL is required for public-endpoint testing")
    return backend_url.rstrip("/") + "/api"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


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


def _register(base_url: str, session_obj: requests.Session, prefix: str):
    payload = {
        "email": f"TEST_i19_{prefix}_{_stamp()}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": f"I19 {prefix}",
        "relationship_label": "Parent",
        "accept_terms": True,
    }
    r = session_obj.post(f"{base_url}/auth/register", json=payload)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {
        "user": r.json()["user"],
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "email": payload["email"],
    }


@pytest.fixture(scope="session")
def circle_ctx(base_url, session):
    owner = _register(base_url, session, "owner")
    create_circle = session.post(
        f"{base_url}/circles",
        json={
            "name": f"Famille I19 {_stamp()}",
            "initial_members": [
                {"display_name": "I19 Profil 1", "relationship_label": "Frère"},
                {"display_name": "I19 Profil 2", "relationship_label": "Soeur"},
                {"display_name": "I19 Profil 3", "relationship_label": "Ami"},
            ],
        },
        headers=owner["headers"],
    )
    assert create_circle.status_code == 200, create_circle.text
    owner_member_id = create_circle.json()["member"]["id"]

    member_a = _register(base_url, session, "membera")
    member_b = _register(base_url, session, "memberb")

    def invite_and_accept(ctx_member, display_name: str):
        inv = session.post(
            f"{base_url}/circle/invitations",
            json={
                "display_name": display_name,
                "email": ctx_member["email"],
                "relationship_label": "Cousin",
            },
            headers=owner["headers"],
        )
        assert inv.status_code == 200, inv.text
        code = inv.json()["code"]
        acc = session.post(f"{base_url}/invitations/accept", json={"code": code}, headers=ctx_member["headers"])
        assert acc.status_code == 200, acc.text

    invite_and_accept(member_a, "I19 Member A")
    invite_and_accept(member_b, "I19 Member B")

    members_resp = session.get(f"{base_url}/circle/members", headers=owner["headers"])
    assert members_resp.status_code == 200, members_resp.text
    members = members_resp.json()

    member_a_id = next(item["id"] for item in members if item.get("user_id") == member_a["user"]["id"])
    member_b_id = next(item["id"] for item in members if item.get("user_id") == member_b["user"]["id"])

    outsider = _register(base_url, session, "outsider")
    outsider_circle = session.post(
        f"{base_url}/circles",
        json={"name": f"Famille I19 outsider {_stamp()}"},
        headers=outsider["headers"],
    )
    assert outsider_circle.status_code == 200, outsider_circle.text

    return {
        "owner": owner,
        "owner_member_id": owner_member_id,
        "member_a": member_a,
        "member_a_id": member_a_id,
        "member_b": member_b,
        "member_b_id": member_b_id,
        "outsider": outsider,
    }


def _create_capsule(
    base_url: str,
    session_obj: requests.Session,
    headers: dict,
    narrator_member_id: str,
    *,
    transcript: str | None = None,
    title: str = "TEST_I19 Capsule",
):
    data = {
        "narrator_member_id": narrator_member_id,
        "duration_sec": "2",
        "title": title,
    }
    if transcript is not None:
        data["transcript"] = transcript
    files = [("file", ("memo.wav", _wav_bytes(), "audio/wav"))]
    res = session_obj.post(f"{base_url}/capsules", headers=headers, data=data, files=files)
    assert res.status_code == 200, res.text
    return res.json()


# Capsule creation fallback behavior: no STT key should save capsule as unavailable, not pending.
def test_create_capsule_without_stt_key_sets_unavailable(base_url, session, circle_ctx):
    created = _create_capsule(
        base_url,
        session,
        circle_ctx["member_a"]["headers"],
        circle_ctx["member_a_id"],
        title="TEST_I19 No STT",
    )
    assert created["status"] == "saved"
    assert created["transcript_status"] == "unavailable"
    assert created.get("transcript") in (None, "")


# Multipart with manual transcript: must be done immediately and exact text preserved.
def test_create_capsule_with_manual_transcript_is_done_and_exact(base_url, session, circle_ctx):
    manual = "Nous étions réunis autour de la table du dimanche."
    created = _create_capsule(
        base_url,
        session,
        circle_ctx["member_a"]["headers"],
        circle_ctx["member_a_id"],
        transcript=manual,
        title="TEST_I19 Manual Transcript",
    )
    assert created["transcript_status"] == "done"
    assert created["transcript"] == manual


# PATCH transcript authorization and shape checks: recorder/owner allowed, non-owner blocked, foreign circle hidden.
def test_patch_transcript_permissions_and_objectid_hygiene(base_url, session, circle_ctx):
    created = _create_capsule(
        base_url,
        session,
        circle_ctx["member_a"]["headers"],
        circle_ctx["member_a_id"],
        title="TEST_I19 Permission Capsule",
    )
    cap_id = created["id"]

    owner_patch = session.patch(
        f"{base_url}/capsules/{cap_id}/transcript",
        headers=circle_ctx["owner"]["headers"],
        json={"transcript": "Texte modifié par le créateur du cercle"},
    )
    assert owner_patch.status_code == 200, owner_patch.text
    owner_payload = owner_patch.json()
    assert owner_payload["transcript"] == "Texte modifié par le créateur du cercle"
    assert "_id" not in owner_payload

    forbidden_patch = session.patch(
        f"{base_url}/capsules/{cap_id}/transcript",
        headers=circle_ctx["member_b"]["headers"],
        json={"transcript": "Je ne devrais pas pouvoir modifier"},
    )
    assert forbidden_patch.status_code == 403, forbidden_patch.text

    foreign_patch = session.patch(
        f"{base_url}/capsules/{cap_id}/transcript",
        headers=circle_ctx["outsider"]["headers"],
        json={"transcript": "Outsider"},
    )
    assert foreign_patch.status_code == 404, foreign_patch.text


# PATCH transcript validation boundaries: empty and >50000 rejected.
def test_patch_transcript_rejects_empty_and_too_large(base_url, session, circle_ctx):
    created = _create_capsule(
        base_url,
        session,
        circle_ctx["member_a"]["headers"],
        circle_ctx["member_a_id"],
        title="TEST_I19 Validation Capsule",
    )
    cap_id = created["id"]

    empty_value = session.patch(
        f"{base_url}/capsules/{cap_id}/transcript",
        headers=circle_ctx["member_a"]["headers"],
        json={"transcript": ""},
    )
    assert empty_value.status_code == 422, empty_value.text

    too_large = session.patch(
        f"{base_url}/capsules/{cap_id}/transcript",
        headers=circle_ctx["member_a"]["headers"],
        json={"transcript": "a" * 50001},
    )
    assert too_large.status_code == 422, too_large.text


# Manual transcribe endpoint fallback: explicit 503 in French and no pending status mutation.
def test_manual_transcribe_without_key_returns_503_and_keeps_unavailable(base_url, session, circle_ctx):
    created = _create_capsule(
        base_url,
        session,
        circle_ctx["member_a"]["headers"],
        circle_ctx["member_a_id"],
        title="TEST_I19 Retry Transcribe",
    )
    cap_id = created["id"]
    assert created["transcript_status"] == "unavailable"

    retry_resp = session.post(f"{base_url}/capsules/{cap_id}/transcribe", headers=circle_ctx["member_a"]["headers"])
    assert retry_resp.status_code == 503, retry_resp.text
    detail = retry_resp.json().get("detail", "")
    assert "Transcription automatique temporairement indisponible" in detail

    detail_after = session.get(f"{base_url}/capsules/{cap_id}", headers=circle_ctx["member_a"]["headers"])
    assert detail_after.status_code == 200, detail_after.text
    assert detail_after.json()["transcript_status"] == "unavailable"


# Book status should expose unavailable count when memories have unavailable/failed transcript statuses.
def test_book_status_exposes_unavailable_count(base_url, session, circle_ctx):
    _create_capsule(
        base_url,
        session,
        circle_ctx["member_a"]["headers"],
        circle_ctx["member_a_id"],
        title="TEST_I19 Book unavailable",
    )
    status = session.get(f"{base_url}/book/status", headers=circle_ctx["member_a"]["headers"])
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["pending"] == 0
    assert payload["unavailable"] >= 1


class _FakeResultCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, _limit):
        return list(self.docs)


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.update_many_calls = []
        self.inserted = []

    async def find_one(self, query, *_args, **_kwargs):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    def find(self, *_args, **_kwargs):
        return _FakeResultCursor(self.docs)

    async def to_list(self, _limit):
        return list(self.docs)

    async def update_many(self, query, update):
        self.update_many_calls.append((query, update))

    async def count_documents(self, *_args, **_kwargs):
        return 500

    async def create_index(self, *_args, **_kwargs):
        return None

    async def update_one(self, *_args, **_kwargs):
        return None

    async def insert_one(self, doc):
        self.inserted.append(dict(doc))


class _FakeQuestionsCollection(_FakeCollection):
    pass


class _FakePromptChat:
    def __init__(self, recorder):
        self.recorder = recorder

    def with_model(self, *_args, **_kwargs):
        return self

    async def send_message(self, message):
        self.recorder["prompt"] = message.text
        return "# Chapitre test\nCorps de chapitre test"


class _FakeDbForStartup:
    def __init__(self):
        self.users = _FakeCollection([])
        self.questions = _FakeQuestionsCollection([])
        self.invitations = _FakeCollection([])
        self.capsules = _FakeCollection([])


class _FakeDbForChapter:
    def __init__(self):
        self.circles = _FakeCollection([{"id": "c-1", "name": "Famille Prompt"}])
        self.members = _FakeCollection([
            {"id": "m-owner", "circle_id": "c-1", "status": "active", "display_name": "Alice", "relationship_label": "Maman"},
        ])
        self.capsules = _FakeCollection([
            {
                "id": "cap-1",
                "circle_id": "c-1",
                "status": "saved",
                "narrator_member_id": "m-owner",
                "question_id": "q-1",
                "theme": "Famille",
                "recorded_at": "2026-01-01T00:00:00Z",
                "transcript": "TEST_I19_TRANSCRIPT_SOURCE",
                "title": "Titre",
            }
        ])
        self.questions = _FakeQuestionsCollection([
            {"id": "q-1", "text": "Quel est ce souvenir ?"},
        ])
        self.book_chapters = _FakeCollection([])
        self.events = _FakeCollection([])


# Startup migration logic: pending transcripts are moved to unavailable when no STT key exists.
@pytest.mark.anyio
async def test_startup_moves_pending_to_unavailable_when_no_stt_key(monkeypatch):
    fake_db = _FakeDbForStartup()
    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(server, "STT_API_KEY", None)
    monkeypatch.setattr(server, "parse_questions", lambda: [])
    monkeypatch.setattr(server, "init_storage", lambda: {"ok": True})

    await server.startup()

    assert fake_db.capsules.update_many_calls == [
        (
            {"status": "saved", "transcript_status": "pending"},
            {"$set": {"transcript_status": "unavailable"}},
        )
    ]


# Chapter generation prompt should include manual transcript memories.
@pytest.mark.anyio
async def test_generate_chapter_uses_manual_transcript_in_prompt(monkeypatch):
    fake_db = _FakeDbForChapter()
    recorder = {}

    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(server, "LlmChat", lambda *args, **kwargs: _FakePromptChat(recorder))

    chapter = await server.generate_chapter("c-1")

    assert chapter["status"] == "ready"
    assert "TEST_I19_TRANSCRIPT_SOURCE" in recorder.get("prompt", "")
