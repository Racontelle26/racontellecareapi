"""Branding regression tests: public share HTML and carnet PDF must expose Racontelle Care."""

import io
import math
import os
import struct
import uuid
import wave

import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")


def _wav_bytes(duration_sec: float = 0.8, freq: float = 440.0) -> bytes:
    rate = 16000
    frames = int(rate * duration_sec)
    buff = io.BytesIO()
    with wave.open(buff, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for i in range(frames):
            amp = int(14000 * abs(math.sin(2 * math.pi * i / (rate / 4))))
            sample = int(amp * math.sin(2 * math.pi * freq * i / rate))
            wav.writeframesraw(struct.pack("<h", sample))
    return buff.getvalue()


def _create_resident(name: str) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/residents",
        json={"display_name": name, "consent_status": "obtained"},
        timeout=20,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_capsule(resident_id: str, title: str) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/capsules",
        json={
            "resident_id": resident_id,
            "mode": "free",
            "title": title,
            "duration_sec": 1,
            "recorded_at": "2026-01-10T10:00:00+00:00",
        },
        timeout=20,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_share_page_and_carnet_branding_racontelle_care():
    """Create TEST resident/capsule -> share page + carnet PDF branding checks -> cleanup."""
    resident = _create_resident(f"TEST_BRAND_{uuid.uuid4().hex[:8]}")
    capsule = _create_capsule(resident["id"], "TEST capsule branding")

    try:
        upload = requests.post(
            f"{BASE_URL}/api/capsules/{capsule['id']}/audio",
            files={"file": ("test.wav", _wav_bytes(), "audio/wav")},
            timeout=60,
        )
        assert upload.status_code == 200, upload.text

        shared = requests.post(f"{BASE_URL}/api/capsules/{capsule['id']}/share", timeout=20)
        assert shared.status_code == 200, shared.text
        share_path = shared.json()["path"]

        page = requests.get(f"{BASE_URL}{share_path}", timeout=20)
        assert page.status_code == 200, page.text
        assert "<title>Un souvenir partagé — Racontelle Care</title>" in page.text
        assert "Racontelle Care" in page.text

        carnet = requests.get(f"{BASE_URL}/api/residents/{resident['id']}/carnet", timeout=60)
        assert carnet.status_code == 200, carnet.text
        assert carnet.headers.get("Content-Type") == "application/pdf"
        assert carnet.content[:5] == b"%PDF-"
        assert "racontelle-carnet-" in carnet.headers.get("Content-Disposition", "")
        assert len(carnet.content) > 1000

    finally:
        requests.delete(f"{BASE_URL}/api/capsules/{capsule['id']}", timeout=20)
        requests.delete(f"{BASE_URL}/api/residents/{resident['id']}", timeout=20)
