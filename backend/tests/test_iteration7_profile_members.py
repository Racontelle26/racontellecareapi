"""Iteration 7: profile-member stats and invitation member_id regression tests."""

import os
import time
import requests
from dotenv import dotenv_values


_frontend_env = dotenv_values("/app/frontend/.env")
PUBLIC_BACKEND_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or _frontend_env.get("EXPO_PUBLIC_BACKEND_URL")
BASE_URL = PUBLIC_BACKEND_URL.rstrip("/") + "/api" if PUBLIC_BACKEND_URL else None


def _now_stamp() -> str:
    return str(int(time.time() * 1000))


def _login(session: requests.Session, email: str, password: str) -> dict:
    resp = session.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# /circle/members stats coherence and no ObjectId leakage
def test_circle_members_stats_match_capsules_for_profils_account():
    assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL is required"
    session = requests.Session()

    headers = _login(session, "profils@racontelle.fr", "Souvenir123")

    members_resp = session.get(f"{BASE_URL}/circle/members", headers=headers)
    assert members_resp.status_code == 200, members_resp.text
    members = members_resp.json()
    assert isinstance(members, list)
    assert len(members) >= 1

    capsules_resp = session.get(f"{BASE_URL}/capsules", headers=headers)
    assert capsules_resp.status_code == 200, capsules_resp.text
    capsules = capsules_resp.json()

    expected_by_member = {}
    for c in capsules:
        narrator_id = c.get("narrator_member_id")
        if not narrator_id:
            continue
        expected_by_member.setdefault(narrator_id, {"count": 0, "seconds": 0})
        expected_by_member[narrator_id]["count"] += 1
        expected_by_member[narrator_id]["seconds"] += int(c.get("duration_sec") or 0)

    for m in members:
        assert "_id" not in m
        assert "capsule_count" in m
        assert "total_seconds" in m
        assert isinstance(m["capsule_count"], int)
        assert isinstance(m["total_seconds"], int)

        expected = expected_by_member.get(m["id"], {"count": 0, "seconds": 0})
        assert m["capsule_count"] == expected["count"]
        assert m["total_seconds"] == expected["seconds"]


# circle isolation check for member stats visibility
def test_circle_members_are_isolated_between_profils_and_verification_accounts():
    assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL is required"
    session = requests.Session()

    headers_profils = _login(session, "profils@racontelle.fr", "Souvenir123")
    headers_verif = _login(session, "verification@racontelle.fr", "Souvenir123")

    members_profils = session.get(f"{BASE_URL}/circle/members", headers=headers_profils)
    members_verif = session.get(f"{BASE_URL}/circle/members", headers=headers_verif)
    assert members_profils.status_code == 200, members_profils.text
    assert members_verif.status_code == 200, members_verif.text

    profils_ids = {m["id"] for m in members_profils.json()}
    verif_ids = {m["id"] for m in members_verif.json()}

    assert profils_ids
    assert verif_ids
    assert profils_ids.isdisjoint(verif_ids)


# invitation pending linked by member_id + resend/revoke API regression
def test_invitation_member_id_link_and_owner_actions_work_for_profils_account():
    assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL is required"
    session = requests.Session()
    headers = _login(session, "profils@racontelle.fr", "Souvenir123")

    members_resp = session.get(f"{BASE_URL}/circle/members", headers=headers)
    assert members_resp.status_code == 200, members_resp.text
    members = members_resp.json()

    active_direct = [m for m in members if m.get("status") == "active" and m.get("role") in {"owner", "profile"}]
    to_create = max(0, 4 - len(active_direct))

    for idx in range(to_create):
        add_resp = session.post(
            f"{BASE_URL}/circle/members",
            json={
                "display_name": f"TEST_I7_Direct_{_now_stamp()}_{idx}",
                "relationship_label": "Proche",
            },
            headers=headers,
        )
        assert add_resp.status_code == 200, add_resp.text

    invite_email = f"test_i7_invite_{_now_stamp()}@racontelle-test.fr"
    invite_resp = session.post(
        f"{BASE_URL}/circle/invitations",
        json={"display_name": f"TEST_I7_Pending_{_now_stamp()}", "email": invite_email, "relationship_label": "Ami"},
        headers=headers,
    )
    assert invite_resp.status_code == 200, invite_resp.text
    payload = invite_resp.json()

    invite = payload["invitation"]
    pending_member = payload["member"]
    assert invite["member_id"] == pending_member["id"]

    listed = session.get(f"{BASE_URL}/circle/invitations", headers=headers)
    assert listed.status_code == 200, listed.text
    listed_items = listed.json()
    listed_invite = next((item for item in listed_items if item["id"] == invite["id"]), None)
    assert listed_invite is not None
    assert listed_invite["member_id"] == pending_member["id"]

    resend = session.post(f"{BASE_URL}/circle/invitations/{invite['id']}/resend", headers=headers)
    assert resend.status_code == 200, resend.text

    revoke = session.delete(f"{BASE_URL}/circle/invitations/{invite['id']}", headers=headers)
    assert revoke.status_code == 200, revoke.text
