# Tests for the 3 new features: Azure Speech transcription, Livre Romancé (Claude), Album search
import time
import pytest
from tests.conftest import wav_bytes


def _upload_capsule(base_url, session, ctx, title="Souvenir test"):
    """Upload a small dummy audio capsule for the owner."""
    dq = session.get(f"{base_url}/daily-question", headers=ctx["headers"]).json()["items"][0]
    files = {"file": ("mem.wav", wav_bytes(), "audio/wav")}
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
    return r.json(), dq


# ------- Feature 1: Auto-transcription (Azure Speech) -------
class TestTranscription:
    def test_capsule_upload_starts_pending_and_leaves_pending(self, base_url, session, owner_ctx):
        cap, _ = _upload_capsule(base_url, session, owner_ctx, title="Cap pour transcription")
        assert cap.get("transcript_status") == "pending"
        pytest.new_cap_id = cap["id"]

        # Poll for transition away from 'pending'
        final_status = None
        for _ in range(20):  # up to ~30s
            time.sleep(1.5)
            g = session.get(f"{base_url}/capsules/{cap['id']}", headers=owner_ctx["headers"])
            assert g.status_code == 200
            st = g.json().get("transcript_status")
            if st and st != "pending":
                final_status = st
                break
        assert final_status in ("done", "failed"), f"transcript_status still pending: {final_status}"
        pytest.new_cap_transcript_status = final_status

    def test_retranscribe_requeues_pending(self, base_url, session, owner_ctx):
        cap_id = getattr(pytest, "new_cap_id", None)
        assert cap_id
        r = session.post(f"{base_url}/capsules/{cap_id}/transcribe", headers=owner_ctx["headers"])
        assert r.status_code == 200, r.text
        assert r.json().get("transcript_status") == "pending"


# ------- Feature 2: Livre romancé (Claude) -------
class TestBook:
    def test_book_status_shape(self, base_url, session, owner_ctx):
        r = session.get(f"{base_url}/book/status", headers=owner_ctx["headers"])
        assert r.status_code == 200
        j = r.json()
        for k in ("memory_count", "transcribed", "pending", "chapter_count", "can_generate"):
            assert k in j
        # We have at least one memory from previous test
        assert j["memory_count"] >= 1
        assert j["can_generate"] is True

    def test_book_status_zero_cannot_generate(self, base_url, session, other_ctx):
        # 'other_ctx' has a fresh circle with 0 memories
        r = session.get(f"{base_url}/book/status", headers=other_ctx["headers"])
        assert r.status_code == 200
        j = r.json()
        assert j["memory_count"] == 0
        assert j["can_generate"] is False

    def test_generate_chapter_zero_memories_400(self, base_url, session, other_ctx):
        r = session.post(f"{base_url}/book/chapters", headers=other_ctx["headers"], timeout=90)
        assert r.status_code == 400, r.text

    def test_generate_chapter_success(self, base_url, session, owner_ctx):
        # This calls Claude live; may take 15-45s
        r = session.post(f"{base_url}/book/chapters", headers=owner_ctx["headers"], timeout=120)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("id")
        assert j.get("title") and isinstance(j["title"], str) and len(j["title"]) > 0
        assert j.get("content") and isinstance(j["content"], str) and len(j["content"]) > 50
        pytest.chapter_id = j["id"]

    def test_list_and_get_chapter(self, base_url, session, owner_ctx):
        cid = getattr(pytest, "chapter_id", None)
        assert cid
        lst = session.get(f"{base_url}/book/chapters", headers=owner_ctx["headers"])
        assert lst.status_code == 200
        arr = lst.json()
        assert any(c["id"] == cid for c in arr)
        one = session.get(f"{base_url}/book/chapters/{cid}", headers=owner_ctx["headers"])
        assert one.status_code == 200
        assert one.json()["id"] == cid

    def test_isolation_other_circle_cannot_read(self, base_url, session, other_ctx):
        cid = getattr(pytest, "chapter_id", None)
        assert cid
        r = session.get(f"{base_url}/book/chapters/{cid}", headers=other_ctx["headers"])
        assert r.status_code == 404
        d = session.delete(f"{base_url}/book/chapters/{cid}", headers=other_ctx["headers"])
        assert d.status_code == 404

    def test_delete_chapter_soft(self, base_url, session, owner_ctx):
        cid = getattr(pytest, "chapter_id", None)
        assert cid
        d = session.delete(f"{base_url}/book/chapters/{cid}", headers=owner_ctx["headers"])
        assert d.status_code == 200
        g = session.get(f"{base_url}/book/chapters/{cid}", headers=owner_ctx["headers"])
        assert g.status_code == 404
        lst = session.get(f"{base_url}/book/chapters", headers=owner_ctx["headers"]).json()
        assert not any(c["id"] == cid for c in lst)


# ------- Feature 3: Album search -------
class TestAlbumSearch:
    def test_search_by_title_and_nonsense(self, base_url, session, owner_ctx):
        # Upload a capsule with a distinctive title
        marker = "ZORGLUBSOUVENIR"
        cap, dq = _upload_capsule(base_url, session, owner_ctx, title=f"Le {marker} de mon enfance")

        # Search returns it
        r = session.get(f"{base_url}/capsules", params={"q": marker.lower()}, headers=owner_ctx["headers"])
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert cap["id"] in ids

        # Nonsense returns nothing
        r2 = session.get(f"{base_url}/capsules", params={"q": "xyzzynotfoundterm"}, headers=owner_ctx["headers"])
        assert r2.status_code == 200
        assert r2.json() == []

    def test_search_by_question_text(self, base_url, session, owner_ctx):
        # Fetch a real question and search a word from it
        lst = session.get(f"{base_url}/capsules", headers=owner_ctx["headers"]).json()
        assert lst, "need at least one capsule"
        c0 = lst[0]
        qtext = (c0.get("question_text") or "").strip()
        assert qtext
        # first meaningful word (>=4 chars)
        word = next((w.strip(".,;:!?").lower() for w in qtext.split() if len(w) >= 5), None)
        assert word
        r = session.get(f"{base_url}/capsules", params={"q": word}, headers=owner_ctx["headers"])
        assert r.status_code == 200
        assert any(c["id"] == c0["id"] for c in r.json())

    def test_search_combined_with_narrator(self, base_url, session, owner_ctx):
        r = session.get(
            f"{base_url}/capsules",
            params={"q": "souvenir", "narrator": owner_ctx["member"]["id"]},
            headers=owner_ctx["headers"],
        )
        assert r.status_code == 200
        for c in r.json():
            assert c["narrator_member_id"] == owner_ctx["member"]["id"]
