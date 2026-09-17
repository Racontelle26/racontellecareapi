# Tests for the NEW photo features (attach on create, POST/DELETE/GET photo, isolation)
# plus regression sanity for audio+transcription and album keyword search.
import io
import struct
import time
import pytest
from tests.conftest import wav_bytes


def _png_1x1() -> bytes:
    """Minimal valid 1x1 red PNG."""
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x8c\xdcF9"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _upload(base_url, session, ctx, *, with_photo=False, title="Souvenir photo test"):
    """Upload a capsule, optionally attaching a photo."""
    dq = session.get(f"{base_url}/daily-question", headers=ctx["headers"]).json()["items"][0]
    files = {"file": ("mem.wav", wav_bytes(), "audio/wav")}
    if with_photo:
        files["photo"] = ("pic.png", _png_1x1(), "image/png")
    data = {
        "narrator_member_id": ctx["member"]["id"],
        "duration_sec": "5",
        "daily_question_id": dq["daily_question_id"],
        "question_id": dq["question"]["id"],
        "theme": dq["theme"],
        "title": title,
    }
    r = session.post(f"{base_url}/capsules", headers=ctx["headers"], data=data, files=files)
    assert r.status_code == 200, r.text
    return r.json()


# --------- Feature: photo attach on create --------
class TestPhotoAttachOnCreate:
    def test_create_capsule_with_photo(self, base_url, session, owner_ctx):
        cap = _upload(base_url, session, owner_ctx, with_photo=True, title="Cap avec photo")
        assert cap.get("photo_path"), "photo_path must be set when photo is uploaded"
        pytest.photo_cap_id = cap["id"]

        # GET /capsules/{id} returns photo_url non-null
        g = session.get(f"{base_url}/capsules/{cap['id']}", headers=owner_ctx["headers"])
        assert g.status_code == 200
        assert g.json().get("photo_url"), "photo_url must be present in enriched capsule"

        # GET /capsules list returns it too
        lst = session.get(f"{base_url}/capsules", headers=owner_ctx["headers"]).json()
        me = next((c for c in lst if c["id"] == cap["id"]), None)
        assert me and me.get("photo_url")

    def test_create_capsule_without_photo(self, base_url, session, owner_ctx):
        cap = _upload(base_url, session, owner_ctx, with_photo=False, title="Cap sans photo")
        assert cap.get("photo_path") in (None, "")
        g = session.get(f"{base_url}/capsules/{cap['id']}", headers=owner_ctx["headers"]).json()
        assert g.get("photo_url") in (None, "")
        pytest.no_photo_cap_id = cap["id"]


# --------- Feature: POST /capsules/{id}/photo + DELETE ----------
class TestPhotoSetReplaceDelete:
    def test_set_photo_on_existing_capsule(self, base_url, session, owner_ctx):
        cap_id = getattr(pytest, "no_photo_cap_id", None)
        assert cap_id
        files = {"photo": ("pic.png", _png_1x1(), "image/png")}
        r = session.post(f"{base_url}/capsules/{cap_id}/photo", headers=owner_ctx["headers"], files=files)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("ok") is True and j.get("photo_url")
        g = session.get(f"{base_url}/capsules/{cap_id}", headers=owner_ctx["headers"]).json()
        assert g.get("photo_url")

    def test_replace_photo(self, base_url, session, owner_ctx):
        cap_id = getattr(pytest, "no_photo_cap_id", None)
        files = {"photo": ("pic2.png", _png_1x1(), "image/png")}
        r = session.post(f"{base_url}/capsules/{cap_id}/photo", headers=owner_ctx["headers"], files=files)
        assert r.status_code == 200, r.text
        assert r.json().get("photo_url")

    def test_delete_photo(self, base_url, session, owner_ctx):
        cap_id = getattr(pytest, "no_photo_cap_id", None)
        d = session.delete(f"{base_url}/capsules/{cap_id}/photo", headers=owner_ctx["headers"])
        assert d.status_code == 200
        assert d.json().get("ok") is True
        g = session.get(f"{base_url}/capsules/{cap_id}", headers=owner_ctx["headers"]).json()
        assert g.get("photo_url") in (None, "")


# --------- Feature: GET /capsules/{id}/photo (streaming) ----------
class TestPhotoStreamAuth:
    def test_stream_photo_with_valid_token(self, base_url, session, owner_ctx):
        cap_id = getattr(pytest, "photo_cap_id", None)
        assert cap_id
        r = session.get(f"{base_url}/capsules/{cap_id}/photo", params={"token": owner_ctx["token"]})
        assert r.status_code == 200, r.text
        assert r.headers.get("Content-Type", "").startswith("image/")
        assert len(r.content) > 0

    def test_stream_photo_missing_token(self, base_url, session, owner_ctx):
        cap_id = getattr(pytest, "photo_cap_id", None)
        r = session.get(f"{base_url}/capsules/{cap_id}/photo")
        # FastAPI required Query -> 422 if missing; treat 4xx as pass
        assert r.status_code in (401, 422), r.text

    def test_stream_photo_invalid_token(self, base_url, session, owner_ctx):
        cap_id = getattr(pytest, "photo_cap_id", None)
        r = session.get(f"{base_url}/capsules/{cap_id}/photo", params={"token": "not-a-valid-jwt"})
        assert r.status_code == 401, r.text

    def test_stream_photo_other_circle_forbidden(self, base_url, session, owner_ctx, other_ctx):
        cap_id = getattr(pytest, "photo_cap_id", None)
        r = session.get(f"{base_url}/capsules/{cap_id}/photo", params={"token": other_ctx["token"]})
        assert r.status_code in (403, 404), r.text


# --------- Isolation: other circle cannot POST/DELETE photo ----------
class TestPhotoIsolation:
    def test_other_circle_cannot_post_photo(self, base_url, session, owner_ctx, other_ctx):
        cap_id = getattr(pytest, "photo_cap_id", None)
        files = {"photo": ("pic.png", _png_1x1(), "image/png")}
        r = session.post(f"{base_url}/capsules/{cap_id}/photo", headers=other_ctx["headers"], files=files)
        assert r.status_code == 404, r.text

    def test_other_circle_cannot_delete_photo(self, base_url, session, owner_ctx, other_ctx):
        cap_id = getattr(pytest, "photo_cap_id", None)
        r = session.delete(f"{base_url}/capsules/{cap_id}/photo", headers=other_ctx["headers"])
        assert r.status_code == 404, r.text


# --------- Regression: audio upload + auto-transcription + search + book ----------
class TestRegression:
    def test_audio_transcription_pending_transitions(self, base_url, session, owner_ctx):
        cap = _upload(base_url, session, owner_ctx, with_photo=False, title="Regression audio")
        assert cap.get("transcript_status") == "pending"
        final = None
        for _ in range(20):
            time.sleep(1.5)
            g = session.get(f"{base_url}/capsules/{cap['id']}", headers=owner_ctx["headers"]).json()
            st = g.get("transcript_status")
            if st and st != "pending":
                final = st
                break
        assert final in ("done", "failed"), f"still pending: {final}"

    def test_album_keyword_search(self, base_url, session, owner_ctx):
        marker = "UNIQUEMARQUEURPHOTO"
        cap = _upload(base_url, session, owner_ctx, with_photo=False, title=f"Une {marker} histoire")
        r = session.get(f"{base_url}/capsules", params={"q": marker.lower()}, headers=owner_ctx["headers"])
        assert r.status_code == 200
        assert any(c["id"] == cap["id"] for c in r.json())

    def test_book_generation_still_works(self, base_url, session, owner_ctx):
        # We already have at least 1 capsule
        r = session.post(f"{base_url}/book/chapters", headers=owner_ctx["headers"], timeout=120)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("id") and j.get("content") and len(j["content"]) > 50
