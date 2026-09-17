"""Regression tests for Racontelle backend: audio upload, Whisper transcription,
family share links, plus base resident/capsule flow."""
import io
import math
import os
import struct
import uuid
import wave

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL env var required"


def make_wav(duration_sec: float = 2.0, freq: float = 440.0) -> bytes:
    """Generate a valid WAV file (sine tone with amplitude envelope)."""
    rate = 16000
    frames = int(rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for i in range(frames):
            # Varying amplitude so the signal is not pure silence
            amp = int(16000 * abs(math.sin(2 * math.pi * i / (rate / 4))))
            sample = int(amp * math.sin(2 * math.pi * freq * i / rate))
            wav.writeframesraw(struct.pack("<h", sample))
    return buf.getvalue()


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    yield s
    s.close()


@pytest.fixture(scope="module")
def resident(session):
    name = f"TEST_{uuid.uuid4().hex[:8]}"
    r = session.post(
        f"{BASE_URL}/api/residents",
        json={"display_name": name, "consent_status": "obtained"},
        timeout=20,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["display_name"] == name
    yield data
    # deactivate to not pollute the 10-profile list
    session.patch(f"{BASE_URL}/api/residents/{data['id']}", json={"active": False}, timeout=20)


@pytest.fixture(scope="module")
def capsule(session, resident):
    r = session.post(
        f"{BASE_URL}/api/capsules",
        json={
            "resident_id": resident["id"],
            "question_id": None,
            "mode": "free",
            "theme": None,
            "title": "TEST souvenir audio",
            "duration_sec": 2,
            "recorded_at": "2026-01-05T10:00:00+00:00",
        },
        timeout=20,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["resident_id"] == resident["id"]
    return data


class TestAudioUpload:
    """POST /api/capsules/{id}/audio -> object storage"""

    def test_upload_audio_returns_uploaded_true(self, session, capsule):
        wav = make_wav()
        r = session.post(
            f"{BASE_URL}/api/capsules/{capsule['id']}/audio",
            files={"file": ("recording.wav", wav, "audio/wav")},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["uploaded"] is True
        assert "path" in body

    def test_upload_audio_unknown_capsule_404(self, session):
        wav = make_wav(0.5)
        r = session.post(
            f"{BASE_URL}/api/capsules/{uuid.uuid4()}/audio",
            files={"file": ("recording.wav", wav, "audio/wav")},
            timeout=60,
        )
        assert r.status_code == 404

    def test_upload_empty_file_400(self, session, capsule):
        r = session.post(
            f"{BASE_URL}/api/capsules/{capsule['id']}/audio",
            files={"file": ("recording.wav", b"", "audio/wav")},
            timeout=60,
        )
        assert r.status_code == 400


class TestTranscription:
    """POST /api/capsules/{id}/transcribe -> Whisper via Emergent key"""

    def test_transcribe_returns_text_and_persists(self, session, resident, capsule):
        wav = make_wav()
        r = session.post(
            f"{BASE_URL}/api/capsules/{capsule['id']}/transcribe",
            files={"file": ("recording.wav", wav, "audio/wav")},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "transcription" in body
        assert isinstance(body["transcription"], str)
        # persisted: visible via GET /api/residents/{rid}/capsules
        listed = session.get(
            f"{BASE_URL}/api/residents/{resident['id']}/capsules", timeout=20
        )
        assert listed.status_code == 200
        match = [c for c in listed.json() if c["id"] == capsule["id"]]
        assert match, "capsule missing from resident capsules"
        assert match[0].get("transcription") is not None
        assert match[0]["transcription"] == body["transcription"]

    def test_transcribe_unknown_capsule_404(self, session):
        wav = make_wav(0.5)
        r = session.post(
            f"{BASE_URL}/api/capsules/{uuid.uuid4()}/transcribe",
            files={"file": ("recording.wav", wav, "audio/wav")},
            timeout=60,
        )
        assert r.status_code == 404


class TestShareFlow:
    """POST /api/capsules/{id}/share + GET /api/share/{token}[/audio]"""

    def test_share_requires_uploaded_audio(self, session, resident):
        r = session.post(
            f"{BASE_URL}/api/capsules",
            json={
                "resident_id": resident["id"],
                "mode": "free",
                "title": "TEST capsule sans audio",
                "duration_sec": 1,
                "recorded_at": "2026-01-05T11:00:00+00:00",
            },
            timeout=20,
        )
        assert r.status_code == 201
        no_audio = r.json()
        s = session.post(f"{BASE_URL}/api/capsules/{no_audio['id']}/share", timeout=20)
        assert s.status_code == 400

    def test_share_token_page_audio_and_404(self, session, capsule):
        # self-contained: upload audio first (xdist may run classes on different workers)
        wav = make_wav()
        up = session.post(
            f"{BASE_URL}/api/capsules/{capsule['id']}/audio",
            files={"file": ("recording.wav", wav, "audio/wav")},
            timeout=60,
        )
        assert up.status_code == 200 and up.json()["uploaded"] is True
        r = session.post(f"{BASE_URL}/api/capsules/{capsule['id']}/share", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token"] and body["path"].startswith("/api/share/")

        page = session.get(f"{BASE_URL}{body['path']}", timeout=20)
        assert page.status_code == 200
        assert "text/html" in page.headers.get("content-type", "")
        assert "<audio" in page.text

        audio = session.get(f"{BASE_URL}{body['path']}/audio", timeout=60)
        assert audio.status_code == 200
        assert len(audio.content) > 100
        assert audio.content[:4] == b"RIFF"  # wav round-trip

        bad = session.get(f"{BASE_URL}/api/share/{uuid.uuid4().hex}", timeout=20)
        assert bad.status_code == 404
        bad_audio = session.get(f"{BASE_URL}/api/share/{uuid.uuid4().hex}/audio", timeout=20)
        assert bad_audio.status_code == 404

    def test_share_unknown_capsule_404(self, session):
        r = session.post(f"{BASE_URL}/api/capsules/{uuid.uuid4()}/share", timeout=20)
        assert r.status_code == 404
