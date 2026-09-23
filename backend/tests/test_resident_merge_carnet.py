"""Tests for iteration 5 features:
- POST /api/residents/merge (dedupe: capsules re-attached, duplicates soft-deleted)
- GET /api/residents/{id}/carnet (PDF export of transcriptions for the family)
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")


def create_resident(name):
    resp = requests.post(
        f"{BASE_URL}/api/residents",
        json={"display_name": name, "consent_status": "obtained"},
        timeout=15,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_capsule(resident_id, title, transcription=None):
    resp = requests.post(
        f"{BASE_URL}/api/capsules",
        json={
            "resident_id": resident_id,
            "mode": "free",
            "title": title,
            "duration_sec": 5,
            "recorded_at": "2026-01-22T10:00:00+00:00",
        },
        timeout=15,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture(scope="module")
def merge_pair():
    """Two TEST_ residents sharing the same name; one has a capsule."""
    name = f"TEST_Merge_{uuid.uuid4().hex[:6]}"
    keep = create_resident(name)
    dup = create_resident(name)
    capsule = create_capsule(dup["id"], "TEST_Souvenir du doublon")
    yield keep, dup, capsule
    # cleanup: capsules created for tests
    requests.delete(f"{BASE_URL}/api/capsules/{capsule['id']}", timeout=15)
    requests.delete(f"{BASE_URL}/api/residents/{keep['id']}", timeout=15)
    requests.delete(f"{BASE_URL}/api/residents/{dup['id']}", timeout=15)


class TestResidentMerge:
    """POST /api/residents/merge reassigns capsules and soft-deletes duplicates."""

    def test_merge_empty_merge_ids_400(self, merge_pair):
        keep, _, _ = merge_pair
        resp = requests.post(
            f"{BASE_URL}/api/residents/merge",
            json={"keep_id": keep["id"], "merge_ids": []},
            timeout=15,
        )
        assert resp.status_code == 400, resp.text

    def test_merge_only_keep_id_400(self, merge_pair):
        keep, _, _ = merge_pair
        resp = requests.post(
            f"{BASE_URL}/api/residents/merge",
            json={"keep_id": keep["id"], "merge_ids": [keep["id"]]},
            timeout=15,
        )
        assert resp.status_code == 400, resp.text

    def test_merge_unknown_keep_404(self, merge_pair):
        _, dup, _ = merge_pair
        resp = requests.post(
            f"{BASE_URL}/api/residents/merge",
            json={"keep_id": "does-not-exist", "merge_ids": [dup["id"]]},
            timeout=15,
        )
        assert resp.status_code == 404, resp.text

    def test_merge_reassigns_capsules_and_soft_deletes(self, merge_pair):
        keep, dup, capsule = merge_pair
        resp = requests.post(
            f"{BASE_URL}/api/residents/merge",
            json={"keep_id": keep["id"], "merge_ids": [dup["id"]]},
            timeout=15,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"merged": 1}

        # capsule re-attached to the kept resident
        capsules = requests.get(f"{BASE_URL}/api/residents/{keep['id']}/capsules", timeout=15)
        assert capsules.status_code == 200
        ids = [c["id"] for c in capsules.json()]
        assert capsule["id"] in ids, f"capsule not re-attached: {ids}"

        # duplicate soft-deleted: hidden from active list
        listing = requests.get(f"{BASE_URL}/api/residents", timeout=15)
        assert all(r["id"] != dup["id"] for r in listing.json())
        assert any(r["id"] == keep["id"] for r in listing.json())

        # merged duplicate can no longer be used as keep (inactive) -> 404
        resp2 = requests.post(
            f"{BASE_URL}/api/residents/merge",
            json={"keep_id": dup["id"], "merge_ids": [keep["id"]]},
            timeout=15,
        )
        assert resp2.status_code == 404


class TestResidentCarnet:
    """GET /api/residents/{id}/carnet returns an elegant PDF of transcriptions."""

    def test_carnet_pdf_headers_and_content(self, merge_pair):
        keep, _, _ = merge_pair
        resp = requests.get(f"{BASE_URL}/api/residents/{keep['id']}/carnet", timeout=60)
        assert resp.status_code == 200, resp.text
        assert resp.headers["Content-Type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-", resp.content[:20]
        disposition = resp.headers.get("Content-Disposition", "")
        safe = keep["display_name"].lower().replace("_", "-")
        assert "racontelle-carnet-" in disposition
        assert disposition.endswith('.pdf"'), disposition
        assert len(resp.content) > 1000  # a real PDF, not an empty shell

    def test_carnet_unknown_resident_404(self):
        resp = requests.get(f"{BASE_URL}/api/residents/does-not-exist/carnet", timeout=15)
        assert resp.status_code == 404

    def test_carnet_resident_without_capsules(self):
        lonely = create_resident(f"TEST_Carnet_{uuid.uuid4().hex[:6]}")
        try:
            resp = requests.get(f"{BASE_URL}/api/residents/{lonely['id']}/carnet", timeout=60)
            assert resp.status_code == 200
            assert resp.content[:5] == b"%PDF-"
        finally:
            requests.delete(f"{BASE_URL}/api/residents/{lonely['id']}", timeout=15)
