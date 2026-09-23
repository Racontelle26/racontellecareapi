"""Tests for resident ZIP export (GET /api/residents/{id}/export) and
soft-delete (DELETE /api/residents/{id}) — Racontelle iteration 4."""
import io
import os
import uuid
import wave
import zipfile

import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")


def make_wav() -> bytes:
    """Generate a small valid WAV file (stands in for an .m4a audio)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x01" * 4000)
    return buf.getvalue()


@pytest.fixture(scope="module")
def resident():
    name = f"TEST_Export_{uuid.uuid4().hex[:6]}"
    resp = requests.post(
        f"{BASE_URL}/api/residents",
        json={"display_name": name, "consent_status": "obtained"},
        timeout=15,
    )
    assert resp.status_code == 201, resp.text
    yield resp.json()
    # cleanup: soft-delete the test resident if still active
    requests.delete(f"{BASE_URL}/api/residents/{resp.json()['id']}", timeout=15)


@pytest.fixture(scope="module")
def capsule_with_audio(resident):
    resp = requests.post(
        f"{BASE_URL}/api/capsules",
        json={
            "resident_id": resident["id"],
            "mode": "free",
            "title": "TEST_Souvenir export",
            "duration_sec": 3,
            "recorded_at": "2026-01-20T10:00:00+00:00",
        },
        timeout=15,
    )
    assert resp.status_code == 201, resp.text
    capsule = resp.json()
    up = requests.post(
        f"{BASE_URL}/api/capsules/{capsule['id']}/audio",
        files={"file": ("recording.m4a", make_wav(), "audio/m4a")},
        timeout=60,
    )
    assert up.status_code == 200, up.text
    yield capsule
    requests.delete(f"{BASE_URL}/api/capsules/{capsule['id']}", timeout=15)


class TestResidentExport:
    """GET /api/residents/{id}/export returns a ZIP with audios + transcriptions."""

    def test_export_zip_content(self, resident, capsule_with_audio):
        resp = requests.get(f"{BASE_URL}/api/residents/{resident['id']}/export", timeout=60)
        assert resp.status_code == 200, resp.text
        assert resp.headers["Content-Type"] == "application/zip"
        assert "racontelle-" in resp.headers.get("Content-Disposition", "")

        archive = zipfile.ZipFile(io.BytesIO(resp.content))
        names = archive.namelist()
        assert "souvenirs.txt" in names, f"missing souvenirs.txt in {names}"
        audio_files = [n for n in names if n.startswith("audio/") and n.endswith(".m4a")]
        assert audio_files, f"missing audio/*.m4a in {names}"

        text = archive.read("souvenirs.txt").decode("utf-8")
        assert resident["display_name"] in text
        assert "TEST_Souvenir export" in text
        assert "Fichier : audio/" in text
        assert archive.read(audio_files[0])[:4] == b"RIFF"

    def test_export_empty_resident_still_has_txt(self, resident):
        resp = requests.get(f"{BASE_URL}/api/residents/{resident['id']}/export", timeout=60)
        assert resp.status_code == 200
        archive = zipfile.ZipFile(io.BytesIO(resp.content))
        assert "souvenirs.txt" in archive.namelist()

    def test_export_unknown_resident_404(self):
        resp = requests.get(f"{BASE_URL}/api/residents/does-not-exist/export", timeout=15)
        assert resp.status_code == 404


class TestResidentSoftDelete:
    """DELETE /api/residents/{id} soft-deletes: profile hidden, capsules kept."""

    def test_soft_delete_hides_resident_keeps_capsules(self, resident, capsule_with_audio):
        rid = resident["id"]
        resp = requests.delete(f"{BASE_URL}/api/residents/{rid}", timeout=15)
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True}

        # resident disappears from active list
        listing = requests.get(f"{BASE_URL}/api/residents", timeout=15)
        assert listing.status_code == 200
        assert all(r["id"] != rid for r in listing.json())

        # capsules stay in DB (still retrievable)
        capsules = requests.get(f"{BASE_URL}/api/residents/{rid}/capsules", timeout=15)
        assert capsules.status_code == 200
        assert any(c["id"] == capsule_with_audio["id"] for c in capsules.json())

        # export of a soft-deleted resident still works (data conserved server-side)
        export = requests.get(f"{BASE_URL}/api/residents/{rid}/export", timeout=60)
        assert export.status_code == 200

    def test_delete_unknown_resident_404(self):
        resp = requests.delete(f"{BASE_URL}/api/residents/does-not-exist", timeout=15)
        assert resp.status_code == 404
