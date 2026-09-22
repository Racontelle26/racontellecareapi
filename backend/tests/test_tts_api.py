"""Tests pour la synthèse vocale (TTS) : POST /api/tts + GET /api/tts/{key}.mp3.

Couvre : génération (path), lecture audio/mpeg avec magic bytes MP3,
cache (2e appel identique -> même path), et validation du texte vide.
"""

import os
import re

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("EXPO_PUBLIC_BACKEND_URL manquant", allow_module_level=True)

TTS_TEXT = "TEST_TTS Quel est votre tout premier souvenir ?"


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestTtsGeneration:
    """Génération TTS + lecture du fichier audio."""

    def test_post_tts_returns_path(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/tts", json={"text": TTS_TEXT}, timeout=60)
        assert response.status_code == 200, response.text
        data = response.json()
        assert "path" in data
        assert re.fullmatch(r"/api/tts/[0-9a-f]{64}\.mp3", data["path"]), data["path"]

    def test_get_tts_audio_mpeg_with_mp3_magic_bytes(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/tts", json={"text": TTS_TEXT}, timeout=60)
        path = response.json()["path"]
        audio = api_client.get(f"{BASE_URL}{path}", timeout=60)
        assert audio.status_code == 200
        assert audio.headers["Content-Type"].startswith("audio/mpeg")
        body = audio.content
        assert len(body) > 500, "fichier audio suspicieusement petit"
        # Magic bytes MP3 : en-tête ID3 ou frame sync MPEG (0xFFEx)
        assert body[:3] == b"ID3" or (body[0] == 0xFF and (body[1] & 0xE0) == 0xE0), body[:8]
        # NB : le Cache-Control "public, max-age" posé par l'app est réécrit en
        # "no-store" par l'ingress de preview (artefact d'infrastructure).

    def test_second_identical_post_reuses_cache(self, api_client):
        first = api_client.post(f"{BASE_URL}/api/tts", json={"text": TTS_TEXT}, timeout=60)
        second = api_client.post(f"{BASE_URL}/api/tts", json={"text": TTS_TEXT}, timeout=60)
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["path"] == second.json()["path"], "le cache doit renvoyer le même path"


class TestTtsValidation:
    """Validation des entrées TTS."""

    def test_empty_text_rejected(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/tts", json={"text": ""}, timeout=15)
        assert response.status_code == 400, f"attendu 400, obtenu {response.status_code}: {response.text}"

    def test_whitespace_only_text_rejected(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/tts", json={"text": "   "}, timeout=15)
        assert response.status_code == 400

    def test_url_only_text_rejected(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/tts", json={"text": "https://example.com"}, timeout=15)
        assert response.status_code == 400

    def test_missing_text_field_rejected(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/tts", json={}, timeout=15)
        assert response.status_code in (400, 422)

    def test_unknown_key_returns_404(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/tts/{'0' * 64}.mp3", timeout=15)
        assert response.status_code == 404
