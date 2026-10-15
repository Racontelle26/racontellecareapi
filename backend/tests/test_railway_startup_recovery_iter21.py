"""Deployment startup recovery contract checks (Railway + Docker + Azure routes)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, "/app/backend")

from azure_speech import AZURE_REGION, TTS_RATE, TTS_VOICE
from server import app


ROOT = Path("/app")
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
RAILWAY_JSON = ROOT / "railway.json"
SERVER_PY = ROOT / "backend" / "server.py"


@pytest.fixture(scope="session", autouse=True)
def authenticated_requests():
    """Override global auth fixture: this suite only validates local contracts."""
    yield


@pytest.fixture(scope="module", autouse=True)
def fresh_resident_slots():
    """Neutralise le nettoyage Railway hérité de la suite d'intégration."""
    yield


# Module: Railway/Docker build and startup contracts
def test_dockerfile_installs_backend_requirements_and_uvicorn():
    source = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY backend/requirements.txt /tmp/requirements.txt" in source
    assert "python -m pip install --no-cache-dir -r /tmp/requirements.txt" in source
    assert "import uvicorn" in source
    assert "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8001}" in source


def test_dockerfile_keeps_ffmpeg_and_ca_certificates_for_azure():
    source = DOCKERFILE.read_text(encoding="utf-8")
    assert "apt-get install -y --no-install-recommends ca-certificates ffmpeg" in source


def test_railway_json_uses_dockerfile_builder_and_api_healthcheck():
    data = json.loads(RAILWAY_JSON.read_text(encoding="utf-8"))
    assert data["build"]["builder"] == "DOCKERFILE"
    assert data["build"]["dockerfilePath"] == "Dockerfile"
    assert data["deploy"]["healthcheckPath"] == "/api/"


def test_dockerignore_excludes_sensitive_and_irrelevant_paths():
    source = DOCKERIGNORE.read_text(encoding="utf-8")
    assert "backend/.env" in source
    assert "frontend" in source
    assert "backend/tests" in source


def test_no_hardcoded_railway_production_url_in_deploy_files():
    docker_source = DOCKERFILE.read_text(encoding="utf-8")
    railway_source = RAILWAY_JSON.read_text(encoding="utf-8")
    assert "railway.app" not in docker_source
    assert "racontellecareapi-production" not in railway_source


# Module: Azure Speech and route registration non-regression
def test_azure_speech_constants_match_required_contract():
    assert AZURE_REGION == "francecentral"
    assert TTS_VOICE == "fr-FR-AlainNeural"
    assert TTS_RATE == "-5%"


def test_tts_cache_is_preserved_in_server_source():
    source = SERVER_PY.read_text(encoding="utf-8")
    assert "db.tts_cache.find_one" in source
    assert "db.tts_cache.insert_one" in source
    assert '"path": f"/api/tts/{key}.mp3"' in source


def test_azure_stt_and_tts_routes_registered():
    routes = {(route.path, tuple(sorted(route.methods))) for route in app.routes}
    assert ("/api/capsules/{capsule_id}/transcribe", ("POST",)) in routes
    assert ("/api/tts", ("POST",)) in routes
    assert ("/api/tts/{key}.mp3", ("GET",)) in routes


def test_password_forgot_and_reset_routes_registered():
    routes = {(route.path, tuple(sorted(route.methods))) for route in app.routes}
    assert ("/api/auth/password/forgot", ("POST",)) in routes
    assert ("/api/auth/password/reset", ("POST",)) in routes
