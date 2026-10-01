"""Checks added with the Family MVP conformity pass (CONFORMITE.md).

Runs against a live API like the other suites: EXPO_PUBLIC_BACKEND_URL, and RATE_LIMIT_DISABLED=1 on the server.
"""
import time

import pytest


def _register(session, base_url, **extra):
    stamp = str(time.time_ns())
    payload = {"email": f"TEST_conf_{stamp}@racontelle-test.fr", "password": "Souvenir123",
               "display_name": "Conformité", "accept_terms": True}
    payload.update(extra)
    return session.post(f"{base_url}/auth/register", json=payload)


@pytest.fixture(scope="module")
def full_circle(base_url, session):
    """Owner + 3 direct profiles, so e-mail invitations are allowed."""
    r = _register(session, base_url)
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    rc = session.post(f"{base_url}/circles", headers=headers, json={
        "name": "Famille Conformité",
        "initial_members": [{"display_name": f"Proche {i}", "relationship_label": "Cousin"} for i in range(3)],
    })
    assert rc.status_code == 200, rc.text
    return {"headers": headers, "circle": rc.json()["circle"]}


def test_register_requires_terms(base_url, session):
    r = _register(session, base_url, accept_terms=False)
    assert r.status_code == 400


def test_invitation_code_is_hashed_and_rotated_on_resend(base_url, session, full_circle):
    inv = session.post(f"{base_url}/circle/invitations", headers=full_circle["headers"],
                       json={"display_name": "Invité", "email": "TEST_conf_invite@racontelle-test.fr"})
    assert inv.status_code == 200, inv.text
    first_code = inv.json()["code"]
    assert "code" not in inv.json()["invitation"]
    invites = session.get(f"{base_url}/circle/invitations", headers=full_circle["headers"]).json()
    assert all("code" not in i for i in invites)

    rs = session.post(f"{base_url}/circle/invitations/{inv.json()['invitation']['id']}/resend", headers=full_circle["headers"])
    assert rs.status_code == 200
    new_code = rs.json()["code"]
    assert new_code != first_code

    joiner = _register(session, base_url)
    jh = {"Authorization": f"Bearer {joiner.json()['access_token']}"}
    assert session.post(f"{base_url}/invitations/accept", headers=jh, json={"code": first_code}).status_code == 404
    assert session.post(f"{base_url}/invitations/accept", headers=jh, json={"code": new_code}).status_code == 200


def test_beta_invitation_open_without_direct_profiles(base_url, session):
    r = _register(session, base_url)
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert session.post(f"{base_url}/circles", headers=headers, json={"name": "Petite famille"}).status_code == 200
    inv = session.post(f"{base_url}/circle/invitations", headers=headers,
                       json={"display_name": "Sœur", "email": "TEST_conf_soeur@racontelle-test.fr"})
    assert inv.status_code == 200, inv.text
    assert inv.json()["code"]


def test_daily_questions_are_unique_and_skip_is_per_member(base_url, session, full_circle):
    daily = session.get(f"{base_url}/daily-question", headers=full_circle["headers"]).json()
    ids = [i["question"]["id"] for i in daily["items"]]
    assert 1 <= len(ids) <= 3 and len(ids) == len(set(ids))
    dq = daily["items"][0]["daily_question_id"]
    ok = session.patch(f"{base_url}/daily-question/state", headers=full_circle["headers"],
                       json={"daily_question_id": dq, "state": "skipped"})
    assert ok.status_code == 200
    again = session.get(f"{base_url}/daily-question", headers=full_circle["headers"]).json()
    assert [i["daily_question_id"] for i in again["items"]] == [i["daily_question_id"] for i in daily["items"]]


def test_daily_state_rejects_other_circle(base_url, session, full_circle):
    other = _register(session, base_url)
    oh = {"Authorization": f"Bearer {other.json()['access_token']}"}
    session.post(f"{base_url}/circles", headers=oh, json={"name": "Autre"})
    dq = session.get(f"{base_url}/daily-question", headers=full_circle["headers"]).json()["items"][0]["daily_question_id"]
    r = session.patch(f"{base_url}/daily-question/state", headers=oh, json={"daily_question_id": dq, "state": "skipped"})
    assert r.status_code == 404


def test_client_events_whitelist(base_url, session, full_circle):
    ok = session.post(f"{base_url}/events", headers=full_circle["headers"], json={"event_type": "theme_selected", "theme": "Famille & traditions"})
    assert ok.status_code == 200
    bad = session.post(f"{base_url}/events", headers=full_circle["headers"], json={"event_type": "capsule_deleted"})
    assert bad.status_code == 400


def test_questions_carry_annex_metadata(base_url, session, full_circle):
    qs = session.get(f"{base_url}/questions", headers=full_circle["headers"],
                     params={"theme": "Maison, lieux de vie & quotidien"}).json()
    assert len(qs) == 20
    assert all(q.get("tags") and q.get("level") for q in qs)


def test_deletion_request_is_recorded_once(base_url, session, full_circle):
    first = session.post(f"{base_url}/me/deletion-request", headers=full_circle["headers"], json={"scope": "account"})
    second = session.post(f"{base_url}/me/deletion-request", headers=full_circle["headers"], json={"scope": "account"})
    assert first.json()["already_requested"] is False
    assert second.json()["already_requested"] is True
    consents = session.get(f"{base_url}/me/consents", headers=full_circle["headers"]).json()
    assert consents["deletion_request"] is not None
    assert any(c["consent_type"] == "cgu_beta" for c in consents["consents"])


def test_admin_routes_need_token(base_url, session):
    assert session.get(f"{base_url}/admin/events/export").status_code in (401, 503)
    assert session.get(f"{base_url}/admin/events/export", headers={"X-Admin-Token": "faux"}).status_code in (401, 503)


def test_refresh_returns_a_new_working_token(base_url, session, full_circle):
    r = session.post(f"{base_url}/auth/refresh", headers=full_circle["headers"])
    assert r.status_code == 200
    fresh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert session.get(f"{base_url}/auth/me", headers=fresh).status_code == 200
    assert session.post(f"{base_url}/auth/refresh").status_code == 401


PNG_1PX = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
           b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82")


def test_member_profile_photo_lifecycle(base_url, session, full_circle):
    members = session.get(f"{base_url}/circle/members", headers=full_circle["headers"]).json()
    profile = next(m for m in members if m.get("role") == "profile")
    assert profile.get("avatar_url") is None

    up = session.post(f"{base_url}/circle/members/{profile['id']}/photo", headers=full_circle["headers"],
                      files={"photo": ("p.png", PNG_1PX, "image/png")})
    assert up.status_code == 200, up.text
    url = up.json()["avatar_url"]
    assert url and "avatar_path" not in up.json()

    token = full_circle["headers"]["Authorization"].split(" ", 1)[1]
    img = session.get(f"{base_url.rsplit('/api', 1)[0]}{url}&token={token}")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"

    # A stranger outside the circle cannot read it
    other = _register(session, base_url)
    session.post(f"{base_url}/circles", headers={"Authorization": f"Bearer {other.json()['access_token']}"}, json={"name": "Autre"})
    assert session.get(f"{base_url.rsplit('/api', 1)[0]}{url}&token={other.json()['access_token']}").status_code == 404

    # Disguised files are refused
    bad = session.post(f"{base_url}/circle/members/{profile['id']}/photo", headers=full_circle["headers"],
                       files={"photo": ("x.png", b"<html>pas une image</html>", "image/png")})
    assert bad.status_code == 415

    gone = session.delete(f"{base_url}/circle/members/{profile['id']}/photo", headers=full_circle["headers"])
    assert gone.status_code == 200 and gone.json()["avatar_url"] is None


def test_book_status_reports_ai_availability(base_url, session, full_circle):
    status = session.get(f"{base_url}/book/status", headers=full_circle["headers"]).json()
    assert "ai_available" in status
    if not status["ai_available"]:
        assert status["can_generate"] is False
        # 400 while the circle has no memory yet, 503 once it has one but no AI key is configured
        assert session.post(f"{base_url}/book/chapters", headers=full_circle["headers"]).status_code in (400, 503)
