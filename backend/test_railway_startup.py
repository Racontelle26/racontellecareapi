import importlib.util
import sys


def load_server_module(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    monkeypatch.setenv("CORS_ORIGINS", "")
    monkeypatch.delenv("CORS_PROXY_ORIGIN", raising=False)
    monkeypatch.delenv("CORS_PUBLIC_ORIGIN", raising=False)
    sys.modules.pop("server", None)
    spec = importlib.util.spec_from_file_location("server", "/app/backend/server.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_get_cors_origins_handles_missing_values(monkeypatch):
    server = load_server_module(monkeypatch)
    assert server.get_cors_origins() == []
