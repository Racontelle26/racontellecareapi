"""Banc d'essai local : l'API tourne réellement (uvicorn, HTTP) avec une base
MongoDB simulée, un stockage audio simulé et des emails capturés
(voir local_env.py). Aucun service externe n'est contacté.

Lancer depuis `backend/` :

    .venv\\Scripts\\python.exe -m pytest tests_local -q -n 0
"""
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_env  # noqa: E402


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# Adresse connue dès l'import : les modules de test la lisent à leur chargement.
PORT = _free_port()
os.environ["EXPO_PUBLIC_BACKEND_URL"] = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="session", autouse=True)
def live_server():
    import uvicorn

    config = uvicorn.Config(local_env.app, host="127.0.0.1", port=PORT, log_level="warning")
    instance = uvicorn.Server(config)
    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()
    for _ in range(100):
        if instance.started:
            break
        time.sleep(0.1)
    assert instance.started, "le serveur local n'a pas démarré"
    yield f"http://127.0.0.1:{PORT}"
    instance.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def base_url(live_server):
    return live_server


@pytest.fixture
def sent_codes():
    return local_env.SENT_CODES


@pytest.fixture
def stored_objects():
    return local_env.OBJECTS
