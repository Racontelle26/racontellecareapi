"""Tests for iteration 8 features:
- PATCH /api/residents/{id} (profile rename)
- PATCH /api/capsules/{id} (capsule title rename)
- PATCH /api/capsules/{id}/assign (attach capsule to a resident)
- duration_sec persistence (real chronometer saved server-side)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def residents(session):
    """Create two TEST_ residents, clean them up (soft delete) after the module."""
    created = []
    for _ in range(2):
        name = f"TEST_Rename_{uuid.uuid4().hex[:8]}"
        r = session.post(
            f"{BASE_URL}/api/residents",
            json={"display_name": name, "consent_status": "obtained"},
            timeout=15,
        )
        assert r.status_code == 201
        created.append(r.json())
    yield created
    for resident in created:
        try:
            session.delete(f"{BASE_URL}/api/residents/{resident['id']}", timeout=15)
        except Exception:
            pass


@pytest.fixture(scope="module")
def capsule(session, residents):
    """Unclassified capsule with a real duration, cleaned up after the module."""
    r = session.post(
        f"{BASE_URL}/api/capsules",
        json={
            "resident_id": None,
            "mode": "free",
            "title": "TEST_Souvenir libre",
            "duration_sec": 7,
            "recorded_at": "2026-01-08T12:00:00+00:00",
        },
        timeout=15,
    )
    assert r.status_code == 201
    data = r.json()
    yield data
    try:
        session.delete(f"{BASE_URL}/api/capsules/{data['id']}", timeout=15)
    except Exception:
        pass


class TestResidentRename:
    """PATCH /api/residents/{id} — renommage du profil."""

    def test_rename_resident_and_verify_persistence(self, session, residents):
        resident = residents[0]
        new_name = f"TEST_Renommé_{uuid.uuid4().hex[:6]}"
        r = session.patch(
            f"{BASE_URL}/api/residents/{resident['id']}",
            json={"display_name": new_name},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == new_name
        # GET to verify server-side persistence
        listed = session.get(f"{BASE_URL}/api/residents", timeout=15).json()
        match = [x for x in listed if x["id"] == resident["id"]]
        assert match and match[0]["display_name"] == new_name

    def test_rename_resident_not_found(self, session):
        r = session.patch(
            f"{BASE_URL}/api/residents/{uuid.uuid4()}",
            json={"display_name": "TEST_Nope"},
            timeout=15,
        )
        assert r.status_code == 404

    def test_rename_resident_blank_rejected(self, session, residents):
        # Blank/whitespace-only name must be rejected (min_length=1 after strip)
        r = session.patch(
            f"{BASE_URL}/api/residents/{residents[0]['id']}",
            json={"display_name": ""},
            timeout=15,
        )
        assert r.status_code in (400, 422)


class TestCapsuleRename:
    """PATCH /api/capsules/{id} — renommage d'un souvenir."""

    def test_rename_capsule_and_verify_persistence(self, session, residents, capsule):
        new_title = f"TEST_Titre {uuid.uuid4().hex[:6]}"
        r = session.patch(
            f"{BASE_URL}/api/capsules/{capsule['id']}",
            json={"title": new_title},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == new_title
        # GET to verify persistence from the resident listing after assign
        assign = session.patch(
            f"{BASE_URL}/api/capsules/{capsule['id']}/assign",
            params={"resident_id": residents[0]["id"]},
            timeout=15,
        )
        assert assign.status_code == 200
        fetched = session.get(
            f"{BASE_URL}/api/residents/{residents[0]['id']}/capsules", timeout=15
        ).json()
        match = [c for c in fetched if c["id"] == capsule["id"]]
        assert match and match[0]["title"] == new_title

    def test_rename_capsule_not_found(self, session):
        r = session.patch(
            f"{BASE_URL}/api/capsules/{uuid.uuid4()}",
            json={"title": "TEST_Nope"},
            timeout=15,
        )
        assert r.status_code == 404

    def test_rename_capsule_empty_title_rejected(self, session, capsule):
        r = session.patch(
            f"{BASE_URL}/api/capsules/{capsule['id']}",
            json={"title": ""},
            timeout=15,
        )
        assert r.status_code in (400, 422)


class TestCapsuleAssign:
    """PATCH /api/capsules/{id}/assign — rattachement à un profil."""

    def test_assign_moves_capsule_between_residents(self, session, residents, capsule):
        # Garantir un point de départ connu : rattacher au résident 0 d'abord.
        session.patch(
            f"{BASE_URL}/api/capsules/{capsule['id']}/assign",
            params={"resident_id": residents[0]["id"]},
            timeout=15,
        )
        target = residents[1]
        r = session.patch(
            f"{BASE_URL}/api/capsules/{capsule['id']}/assign",
            params={"resident_id": target["id"]},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["resident_id"] == target["id"]
        assert body["status"] == "assigned"
        # Appears in the new resident's list
        new_list = session.get(
            f"{BASE_URL}/api/residents/{target['id']}/capsules", timeout=15
        ).json()
        assert any(c["id"] == capsule["id"] for c in new_list)
        # Disappears from the old resident's list
        old_list = session.get(
            f"{BASE_URL}/api/residents/{residents[0]['id']}/capsules", timeout=15
        ).json()
        assert not any(c["id"] == capsule["id"] for c in old_list)

    def test_assign_capsule_not_found(self, session, residents):
        r = session.patch(
            f"{BASE_URL}/api/capsules/{uuid.uuid4()}/assign",
            params={"resident_id": residents[0]["id"]},
            timeout=15,
        )
        assert r.status_code == 404

    def test_assign_resident_not_found(self, session, capsule):
        r = session.patch(
            f"{BASE_URL}/api/capsules/{capsule['id']}/assign",
            params={"resident_id": str(uuid.uuid4())},
            timeout=15,
        )
        assert r.status_code == 404


class TestCapsuleDuration:
    """Duration réelle sauvegardée côté serveur (chrono maison)."""

    def test_duration_sec_persisted(self, session, residents, capsule):
        # Rattacher la capsule (idempotent) avant de vérifier la durée persistée.
        session.patch(
            f"{BASE_URL}/api/capsules/{capsule['id']}/assign",
            params={"resident_id": residents[1]["id"]},
            timeout=15,
        )
        fetched = session.get(
            f"{BASE_URL}/api/residents/{residents[1]['id']}/capsules", timeout=15
        ).json()
        match = [c for c in fetched if c["id"] == capsule["id"]]
        assert match, "capsule introuvable dans la liste du résident"
        assert match[0]["duration_sec"] == 7
