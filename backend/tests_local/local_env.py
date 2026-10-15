"""Environnement local sans aucun service externe : base MongoDB simulée en
mémoire (mongomock-motor), stockage audio simulé, emails capturés.

Utilisé par les tests locaux (conftest.py) et par le serveur de démonstration :

    .venv\\Scripts\\python.exe tests_local\\local_env.py      (API sur le port 8001)
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

for key, value in {
    "MONGO_URL": "mongodb://mock",
    "DB_NAME": "racontelle_local",
    "JWT_SECRET": "x" * 64,
    "JWT_ISSUER": "racontelle-care",
    "JWT_AUDIENCE": "racontelle-care-app",
    "ACCESS_MINUTES": "15",
    "REFRESH_DAYS": "30",
    "CORS_ORIGINS": "http://localhost:8081,http://localhost:8002",
    "INTEGRATION_PROXY_URL": "http://storage.invalid",
    "EMERGENT_LLM_KEY": "cle-de-test",
    "RESEND_API_KEY": "re_email_test_key",
    "RESEND_FROM_EMAIL": "no-reply@racontellecare.com",
    "PASSWORD_RESET_URL": "https://ehpad-recall.preview.emergentagent.com",
}.items():
    os.environ.setdefault(key, value)

import mongomock_motor  # noqa: E402
import motor.motor_asyncio  # noqa: E402

motor.motor_asyncio.AsyncIOMotorClient = mongomock_motor.AsyncMongoMockClient

import storage  # noqa: E402

OBJECTS: dict[str, tuple[bytes, str]] = {}
SENT_CODES: dict[str, str] = {}


def fake_put(path, data, content_type):
    OBJECTS[path] = (data, content_type)
    return {"ok": True}


def fake_get(path):
    if path not in OBJECTS:
        raise FileNotFoundError(path)
    return OBJECTS[path]


def fake_delete(path):
    OBJECTS.pop(path, None)
    return True


import quiz  # noqa: E402
import security  # noqa: E402
import server  # noqa: E402

for module in (storage, server, quiz):
    for name, fake in (("put_object", fake_put), ("get_object", fake_get), ("delete_object", fake_delete)):
        if hasattr(module, name):
            setattr(module, name, fake)
    if hasattr(module, "init_storage"):
        setattr(module, "init_storage", lambda: "cle-stockage-test")


async def _capture_code(to, name, code, minutes):
    SENT_CODES[to] = code


security.send_password_reset_email = _capture_code

app = server.app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8001")), log_level="info")
