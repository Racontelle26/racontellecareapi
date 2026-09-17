# Racontelle Family — end-to-end backend tests
import io
import pytest
from tests.conftest import wav_bytes


# --------- Health ---------
def test_root_health(base_url, session):
    r = session.get(f"{base_url}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# --------- Auth ---------
class TestAuth:
    def test_register_and_me(self, base_url, session, owner_ctx):
        r = session.get(f"{base_url}/auth/me", headers=owner_ctx["headers"])
        assert r.status_code == 200
        j = r.json()
        assert j["has_circle"] is True
        assert j["user"]["email"] == owner_ctx["user"]["email"]

    def test_login_ok_and_bad(self, base_url, session, owner_creds):
        r = session.post(f"{base_url}/auth/login", json={"email": owner_creds["email"], "password": owner_creds["password"]})
        assert r.status_code == 200
        assert "access_token" in r.json()
        bad = session.post(f"{base_url}/auth/login", json={"email": owner_creds["email"], "password": "wrong"})
        assert bad.status_code == 401

    def test_register_duplicate_conflict(self, base_url, session, owner_creds):
        r = session.post(f"{base_url}/auth/register", json=owner_creds)
        assert r.status_code == 409

    def test_request_reset_is_generic(self, base_url, session):
        r = session.post(f"{base_url}/auth/request-reset", json={"email": "unknown_xyz@racontelle-test.fr"})
        assert r.status_code == 200
        assert "message" in r.json()

    def test_me_requires_auth(self, base_url, session):
        r = session.get(f"{base_url}/auth/me")
        assert r.status_code == 401


# --------- Circle ---------
class TestCircle:
    def test_circle_summary_shape(self, base_url, session, owner_ctx):
        r = session.get(f"{base_url}/circle", headers=owner_ctx["headers"])
        assert r.status_code == 200
        j = r.json()
        assert "capsule_count" in j
        assert "tree_level" in j and "level" in j["tree_level"]
        assert j["circle"]["name"] == "Famille Test"

    def test_cannot_create_second_circle(self, base_url, session, owner_ctx):
        r = session.post(f"{base_url}/circles", json={"name": "Deux"}, headers=owner_ctx["headers"])
        assert r.status_code == 400

    def test_members_list(self, base_url, session, owner_ctx, member_ctx):
        r = session.get(f"{base_url}/circle/members", headers=owner_ctx["headers"])
        assert r.status_code == 200
        arr = r.json()
        assert len([m for m in arr if m["status"] == "active"]) >= 2


# --------- Invitations ---------
class TestInvitations:
    def test_invite_flow_and_revoke(self, base_url, session, owner_ctx):
        inv = session.post(
            f"{base_url}/circle/invitations",
            json={"display_name": "Cousin", "email": "TEST_cousin@racontelle-test.fr"},
            headers=owner_ctx["headers"],
        )
        assert inv.status_code == 200, inv.text
        code = inv.json()["code"]
        assert code and len(code) >= 6
        # list
        lst = session.get(f"{base_url}/circle/invitations", headers=owner_ctx["headers"])
        assert lst.status_code == 200
        invs = lst.json()
        target = next((x for x in invs if x["code"] == code), None)
        assert target is not None
        # resend
        rs = session.post(f"{base_url}/circle/invitations/{target['id']}/resend", headers=owner_ctx["headers"])
        assert rs.status_code == 200
        # revoke
        dl = session.delete(f"{base_url}/circle/invitations/{target['id']}", headers=owner_ctx["headers"])
        assert dl.status_code == 200

    def test_non_owner_cannot_invite(self, base_url, session, member_ctx):
        r = session.post(f"{base_url}/circle/invitations",
                         json={"display_name": "X", "email": "TEST_x@racontelle-test.fr"},
                         headers=member_ctx["headers"])
        assert r.status_code == 403

    def test_second_circle_after_join_rejected(self, base_url, session, member_ctx):
        r = session.post(f"{base_url}/circles", json={"name": "Autre"}, headers=member_ctx["headers"])
        assert r.status_code == 400


# --------- Themes / Questions ---------
class TestQuestions:
    def test_themes_hide_sensitive(self, base_url, session, owner_ctx):
        r = session.get(f"{base_url}/themes", headers=owner_ctx["headers"])
        assert r.status_code == 200
        themes = r.json()
        assert isinstance(themes, list)
        assert len(themes) >= 15
        names = [t["theme"] for t in themes]
        assert not any("Intimit" in n for n in names)
        assert not any("Deuils" in n for n in names)

    def test_questions_list_and_filter(self, base_url, session, owner_ctx):
        r = session.get(f"{base_url}/questions", headers=owner_ctx["headers"])
        assert r.status_code == 200
        assert len(r.json()) >= 200  # ~400 seeded, minus sensitive
        # filter by theme
        themes_r = session.get(f"{base_url}/themes", headers=owner_ctx["headers"]).json()
        t = themes_r[0]["theme"]
        rt = session.get(f"{base_url}/questions", params={"theme": t}, headers=owner_ctx["headers"])
        assert rt.status_code == 200
        assert all(q["theme"] == t for q in rt.json())

    def test_surprise(self, base_url, session, owner_ctx):
        r = session.get(f"{base_url}/questions/surprise", headers=owner_ctx["headers"])
        assert r.status_code == 200
        assert r.json().get("text")


# --------- Daily ---------
class TestDaily:
    def test_daily_has_up_to_three(self, base_url, session, owner_ctx):
        r = session.get(f"{base_url}/daily-question", headers=owner_ctx["headers"])
        assert r.status_code == 200
        j = r.json()
        assert 1 <= len(j["items"]) <= 3
        for it in j["items"]:
            assert "daily_question_id" in it
            assert it["question"]
            assert it["my_state"] in ("new", "viewed", "skipped", "answered")

    def test_daily_state_patch(self, base_url, session, owner_ctx):
        r = session.get(f"{base_url}/daily-question", headers=owner_ctx["headers"])
        dq_id = r.json()["items"][0]["daily_question_id"]
        pr = session.patch(f"{base_url}/daily-question/state",
                           json={"daily_question_id": dq_id, "state": "viewed"},
                           headers=owner_ctx["headers"])
        assert pr.status_code == 200
        r2 = session.get(f"{base_url}/daily-question", headers=owner_ctx["headers"])
        it = next(x for x in r2.json()["items"] if x["daily_question_id"] == dq_id)
        assert it["my_state"] == "viewed"


# --------- Capsules ---------
class TestCapsules:
    def _upload(self, base_url, session, ctx, daily_question_id=None):
        r = session.get(f"{base_url}/daily-question", headers=ctx["headers"])
        dq = r.json()["items"][0]
        if daily_question_id is None:
            daily_question_id = dq["daily_question_id"]
        files = {"file": ("mem.wav", wav_bytes(), "audio/wav")}
        data = {
            "narrator_member_id": ctx["member"]["id"] if "member" in ctx else session.get(f"{base_url}/circle", headers=ctx["headers"]).json()["members"][0]["id"],
            "duration_sec": "8",
            "daily_question_id": daily_question_id,
            "question_id": dq["question"]["id"],
            "theme": dq["theme"],
            "title": "Un souvenir test",
        }
        up = session.post(f"{base_url}/capsules", headers=ctx["headers"], data=data, files=files)
        return up, daily_question_id

    def test_capsule_upload_and_side_effects(self, base_url, session, owner_ctx):
        before = session.get(f"{base_url}/circle", headers=owner_ctx["headers"]).json()
        up, dq_id = self._upload(base_url, session, owner_ctx)
        assert up.status_code == 200, up.text
        cap = up.json()
        assert cap["id"] and cap["status"] == "saved"

        # GET list must include it
        lst = session.get(f"{base_url}/capsules", headers=owner_ctx["headers"])
        assert lst.status_code == 200
        ids = [c["id"] for c in lst.json()]
        assert cap["id"] in ids

        # tree grew
        after = session.get(f"{base_url}/circle", headers=owner_ctx["headers"]).json()
        assert after["capsule_count"] == before["capsule_count"] + 1
        assert after["tree_level"]["level"] >= before["tree_level"]["level"]

        # daily state answered
        dq = session.get(f"{base_url}/daily-question", headers=owner_ctx["headers"]).json()
        it = next(x for x in dq["items"] if x["daily_question_id"] == dq_id)
        assert it["my_state"] == "answered"

        # audio stream with token works
        audio = session.get(f"{base_url}/capsules/{cap['id']}/audio", params={"token": owner_ctx["token"]})
        assert audio.status_code == 200
        assert audio.headers.get("content-type", "").startswith("audio")
        assert len(audio.content) > 0

        # store for later tests via pytest cache
        pytest.owner_capsule_id = cap["id"]

    def test_isolation_other_circle_cannot_read(self, base_url, session, owner_ctx, other_ctx):
        cap_id = getattr(pytest, "owner_capsule_id", None)
        assert cap_id, "capsule not created in previous test"
        r = session.get(f"{base_url}/capsules/{cap_id}", headers=other_ctx["headers"])
        assert r.status_code == 404
        aud = session.get(f"{base_url}/capsules/{cap_id}/audio", params={"token": other_ctx["token"]})
        # must be forbidden or not-found for other circle
        assert aud.status_code in (403, 404)

    def test_audio_requires_token(self, base_url, session):
        r = session.get(f"{base_url}/capsules/anything/audio")
        assert r.status_code in (401, 422)

    def test_soft_delete(self, base_url, session, owner_ctx):
        cap_id = getattr(pytest, "owner_capsule_id", None)
        assert cap_id
        r = session.delete(f"{base_url}/capsules/{cap_id}", headers=owner_ctx["headers"])
        assert r.status_code == 200
        g = session.get(f"{base_url}/capsules/{cap_id}", headers=owner_ctx["headers"])
        assert g.status_code == 404


# --------- Preferences & Feedback ---------
class TestPrefsFeedback:
    def test_update_prefs(self, base_url, session, owner_ctx):
        r = session.patch(f"{base_url}/me/preferences",
                          json={"display_name": "Owner Renommé", "initials_color": "#B57477", "daily_email": False},
                          headers=owner_ctx["headers"])
        assert r.status_code == 200
        j = r.json()
        assert j["user"]["display_name"] == "Owner Renommé"
        assert j["member"]["initials_color"] == "#B57477"
        assert j["member"]["daily_email"] is False

    def test_feedback(self, base_url, session, owner_ctx):
        r = session.post(f"{base_url}/feedback",
                         json={"category": "idea", "rating": 5, "comment": "Super app", "page_context": "profile"},
                         headers=owner_ctx["headers"])
        assert r.status_code == 200
        assert r.json().get("ok") is True
