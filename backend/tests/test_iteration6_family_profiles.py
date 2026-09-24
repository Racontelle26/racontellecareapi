"""Iteration 6 backend tests: family profiles, invitation gate, and sur-le-vif edit rules."""

import os
import time
import requests
import pytest
from dotenv import dotenv_values


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


@pytest.fixture(scope="session")
def api_base_url() -> str:
    frontend_env = dotenv_values("/app/frontend/.env")
    backend_url = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or frontend_env.get("EXPO_PUBLIC_BACKEND_URL")
    if not backend_url:
        pytest.skip("EXPO_PUBLIC_BACKEND_URL is required for public-endpoint testing")
    return backend_url.rstrip("/") + "/api"


@pytest.fixture(scope="session")
def api_session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


def _register_user(api_base_url: str, api_session: requests.Session, prefix: str):
    stamp = _rand()
    creds = {
        "email": f"TEST_i6_{prefix}_{stamp}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": f"{prefix.capitalize()} I6",
        "relationship_label": "Parent",
        "accept_terms": True,
    }
    r = api_session.post(f"{api_base_url}/auth/register", json=creds)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return {"creds": creds, "token": token, "headers": headers, "user": r.json()["user"]}


def _create_circle(api_base_url: str, api_session: requests.Session, owner_ctx: dict, name: str, initial_members=None):
    payload = {"name": name, "initial_members": initial_members or []}
    r = api_session.post(f"{api_base_url}/circles", json=payload, headers=owner_ctx["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def _assert_no_mongo_id(obj):
    if isinstance(obj, dict):
        assert "_id" not in obj
        for value in obj.values():
            _assert_no_mongo_id(value)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_mongo_id(item)


# circles initial members (0..3 accepted, >3 rejected, invalid rejected)
@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_create_circle_accepts_0_to_3_initial_members(api_base_url, api_session, count):
    owner = _register_user(api_base_url, api_session, f"circle_{count}")
    initial_members = [{"display_name": f"TEST_Proche{idx}", "relationship_label": "Cousin"} for idx in range(count)]
    data = _create_circle(api_base_url, api_session, owner, f"Famille I6 {count}", initial_members=initial_members)
    assert data["member"]["role"] == "owner"
    assert len(data["profiles"]) == count
    _assert_no_mongo_id(data)


def test_create_circle_rejects_more_than_3_initial_members(api_base_url, api_session):
    owner = _register_user(api_base_url, api_session, "circle_gt3")
    payload = {
        "name": "Famille I6 GT3",
        "initial_members": [
            {"display_name": "TEST_A", "relationship_label": "Oncle"},
            {"display_name": "TEST_B", "relationship_label": "Tante"},
            {"display_name": "TEST_C", "relationship_label": "Cousin"},
            {"display_name": "TEST_D", "relationship_label": "Cousine"},
        ],
    }
    r = api_session.post(f"{api_base_url}/circles", json=payload, headers=owner["headers"])
    assert r.status_code == 422


def test_create_circle_rejects_invalid_initial_member_fields(api_base_url, api_session):
    owner = _register_user(api_base_url, api_session, "circle_invalid")
    payload = {
        "name": "Famille I6 Invalid",
        "initial_members": [{"display_name": "", "relationship_label": "Grand-mère"}],
    }
    r = api_session.post(f"{api_base_url}/circles", json=payload, headers=owner["headers"])
    assert r.status_code == 422


# direct members (owner-only, max 4 direct profiles owner+profile, edit/delete rules)
def test_direct_member_owner_only_and_fifth_rejected(api_base_url, api_session):
    owner = _register_user(api_base_url, api_session, "owner_direct")
    _create_circle(api_base_url, api_session, owner, "Famille I6 Direct")
    owner_member_id = api_session.get(f"{api_base_url}/circle/members", headers=owner["headers"]).json()[0]["id"]

    for name in ["TEST_Jeanne", "TEST_Paul", "TEST_Lina"]:
        ok = api_session.post(
            f"{api_base_url}/circle/members",
            json={"display_name": name, "relationship_label": "Proche"},
            headers=owner["headers"],
        )
        assert ok.status_code == 200, ok.text

    # Non-owner in same circle must be forbidden
    member_user = _register_user(api_base_url, api_session, "nonowner_direct")
    inv = api_session.post(
        f"{api_base_url}/circle/invitations",
        json={"display_name": "TEST_NonOwner", "email": member_user["creds"]["email"], "relationship_label": "Ami"},
        headers=owner["headers"],
    )
    assert inv.status_code == 200, inv.text
    accept = api_session.post(
        f"{api_base_url}/invitations/accept",
        json={"code": inv.json()["code"]},
        headers=member_user["headers"],
    )
    assert accept.status_code == 200, accept.text
    deny = api_session.post(
        f"{api_base_url}/circle/members",
        json={"display_name": "TEST_Forbidden", "relationship_label": "Frère"},
        headers=member_user["headers"],
    )
    assert deny.status_code == 403

    fifth = api_session.post(
        f"{api_base_url}/circle/members",
        json={"display_name": "TEST_Extra", "relationship_label": "Proche"},
        headers=owner["headers"],
    )
    assert fifth.status_code == 400

    edit_owner = api_session.patch(
        f"{api_base_url}/circle/members/{owner_member_id}",
        json={"display_name": "TEST_NewOwner", "relationship_label": "Parent"},
        headers=owner["headers"],
    )
    assert edit_owner.status_code == 400


def test_delete_direct_member_without_memories_ok_and_with_memories_blocked(api_base_url, api_session):
    owner = _register_user(api_base_url, api_session, "owner_delete")
    circle = _create_circle(api_base_url, api_session, owner, "Famille I6 Delete")
    owner_member = circle["member"]

    p1 = api_session.post(
        f"{api_base_url}/circle/members",
        json={"display_name": "TEST_SansMemo", "relationship_label": "Tatie"},
        headers=owner["headers"],
    )
    assert p1.status_code == 200, p1.text
    p1_id = p1.json()["id"]

    p2 = api_session.post(
        f"{api_base_url}/circle/members",
        json={"display_name": "TEST_AvecMemo", "relationship_label": "Papy"},
        headers=owner["headers"],
    )
    assert p2.status_code == 200, p2.text
    p2_id = p2.json()["id"]

    del_ok = api_session.delete(f"{api_base_url}/circle/members/{p1_id}", headers=owner["headers"])
    assert del_ok.status_code == 200

    files = {"file": ("memo.wav", _wav_bytes(), "audio/wav")}
    data = {
        "narrator_member_id": p2_id,
        "duration_sec": "2",
        "title": "TEST Souvenir libre",
    }
    cap = api_session.post(f"{api_base_url}/capsules", data=data, files=files, headers=owner["headers"])
    assert cap.status_code == 200, cap.text

    del_blocked = api_session.delete(f"{api_base_url}/circle/members/{p2_id}", headers=owner["headers"])
    assert del_blocked.status_code == 400
    assert "Rattachez" in del_blocked.text

    # non-owner in same circle cannot delete members
    for name in ["TEST_Gate1", "TEST_Gate2"]:
        fill = api_session.post(
            f"{api_base_url}/circle/members",
            json={"display_name": name, "relationship_label": "Proche"},
            headers=owner["headers"],
        )
        assert fill.status_code == 200, fill.text

    invited_user = _register_user(api_base_url, api_session, "nonowner_delete")
    inv = api_session.post(
        f"{api_base_url}/circle/invitations",
        json={"display_name": "TEST_NonOwnerDel", "email": invited_user["creds"]["email"], "relationship_label": "Ami"},
        headers=owner["headers"],
    )
    assert inv.status_code == 200, inv.text
    acc = api_session.post(
        f"{api_base_url}/invitations/accept",
        json={"code": inv.json()["code"]},
        headers=invited_user["headers"],
    )
    assert acc.status_code == 200, acc.text
    forbidden = api_session.delete(f"{api_base_url}/circle/members/{owner_member['id']}", headers=invited_user["headers"])
    assert forbidden.status_code == 403


# invitation gate (<4 direct rejected, >=4 accepted)
def test_invitation_rejected_before_4_direct_then_accepted_and_revocable(api_base_url, api_session):
    owner = _register_user(api_base_url, api_session, "owner_inv")
    _create_circle(api_base_url, api_session, owner, "Famille I6 Invite")

    early = api_session.post(
        f"{api_base_url}/circle/invitations",
        json={"display_name": "TEST_InviteEarly", "email": "delivered@resend.dev", "relationship_label": "Ami"},
        headers=owner["headers"],
    )
    assert early.status_code == 400

    for name in ["TEST_A", "TEST_B", "TEST_C"]:
        create_profile = api_session.post(
            f"{api_base_url}/circle/members",
            json={"display_name": name, "relationship_label": "Proche"},
            headers=owner["headers"],
        )
        assert create_profile.status_code == 200, create_profile.text

    invite = api_session.post(
        f"{api_base_url}/circle/invitations",
        json={"display_name": "TEST_InviteOK", "email": "delivered@resend.dev", "relationship_label": "Ami"},
        headers=owner["headers"],
    )
    assert invite.status_code == 200, invite.text
    inv_id = invite.json()["invitation"]["id"]

    listed = api_session.get(f"{api_base_url}/circle/invitations", headers=owner["headers"])
    assert listed.status_code == 200
    assert any(i["id"] == inv_id for i in listed.json())

    revoke = api_session.delete(f"{api_base_url}/circle/invitations/{inv_id}", headers=owner["headers"])
    assert revoke.status_code == 200


# sur-le-vif update: allowed only no-question memories, with circle/narrator/permission checks
def test_patch_capsule_rules_sur_le_vif_vs_question(api_base_url, api_session):
    owner = _register_user(api_base_url, api_session, "owner_caps")
    circle = _create_circle(api_base_url, api_session, owner, "Famille I6 Capsule", initial_members=[
        {"display_name": "TEST_Alice", "relationship_label": "Soeur"},
        {"display_name": "TEST_Paul", "relationship_label": "Frère"},
    ])
    owner_member_id = circle["member"]["id"]
    member_ids = [p["id"] for p in circle["profiles"]]

    files = {"file": ("free.wav", _wav_bytes(), "audio/wav")}
    free_data = {"narrator_member_id": member_ids[0], "duration_sec": "2", "title": "TEST Libre Original"}
    free_cap = api_session.post(f"{api_base_url}/capsules", data=free_data, files=files, headers=owner["headers"])
    assert free_cap.status_code == 200, free_cap.text
    free_id = free_cap.json()["id"]

    daily = api_session.get(f"{api_base_url}/daily-question", headers=owner["headers"])
    assert daily.status_code == 200
    d0 = daily.json()["items"][0]
    q_data = {
        "narrator_member_id": member_ids[0],
        "duration_sec": "2",
        "question_id": d0["question"]["id"],
        "daily_question_id": d0["daily_question_id"],
        "theme": d0["theme"],
        "title": d0["question"]["text"],
    }
    q_cap = api_session.post(f"{api_base_url}/capsules", data=q_data, files={"file": ("q.wav", _wav_bytes(), "audio/wav")}, headers=owner["headers"])
    assert q_cap.status_code == 200, q_cap.text
    q_id = q_cap.json()["id"]

    ok_patch = api_session.patch(
        f"{api_base_url}/capsules/{free_id}",
        json={"title": "TEST Libre Renommé", "narrator_member_id": member_ids[1]},
        headers=owner["headers"],
    )
    assert ok_patch.status_code == 200, ok_patch.text
    after = api_session.get(f"{api_base_url}/capsules/{free_id}", headers=owner["headers"])
    assert after.status_code == 200
    assert after.json()["title"] == "TEST Libre Renommé"
    assert after.json()["narrator_member_id"] == member_ids[1]

    bad_question_patch = api_session.patch(
        f"{api_base_url}/capsules/{q_id}",
        json={"title": "TEST Should Fail", "narrator_member_id": member_ids[1]},
        headers=owner["headers"],
    )
    assert bad_question_patch.status_code == 400

    bad_narrator_patch = api_session.patch(
        f"{api_base_url}/capsules/{free_id}",
        json={"title": "TEST Wrong Narrator", "narrator_member_id": "invalid-member-id"},
        headers=owner["headers"],
    )
    assert bad_narrator_patch.status_code == 400

    other = _register_user(api_base_url, api_session, "other_caps")
    _create_circle(api_base_url, api_session, other, "Famille I6 OtherCaps")
    forbidden = api_session.patch(
        f"{api_base_url}/capsules/{free_id}",
        json={"title": "TEST Forbidden", "narrator_member_id": owner_member_id},
        headers=other["headers"],
    )
    assert forbidden.status_code == 404
