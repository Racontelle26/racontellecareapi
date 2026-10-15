from pathlib import Path
import sys

import mongomock
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.reset_user_password import reset_user_password  # noqa: E402
from security import password_hash  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def authenticated_requests():
    """Test Mongo local pur : aucun appel Railway ni compte distant."""
    yield


@pytest.fixture(scope="module", autouse=True)
def fresh_resident_slots():
    """Neutralise le nettoyage distant autouse de la suite d'intégration."""
    yield


def database():
    return mongomock.MongoClient().racontelle


def seed(db, *, email="laracontelle@gmail.com", disabled=False):
    db.tenants.insert_one({"id": "tenant-1", "name": "Racontelle", "active": True})
    db.users.insert_one(
        {
            "id": "user-1",
            "tenant_id": "tenant-1",
            "email_lower": email,
            "password_hash": password_hash.hash("AncienMotDePasse12"),
            "role": "admin",
            "disabled": disabled,
        }
    )
    db.refresh_tokens.insert_one(
        {"id": "refresh-1", "user_id": "user-1", "tenant_id": "tenant-1", "revoked_at": None}
    )
    db.auth_attempts.insert_one({"email_hash": __import__("hashlib").sha256(email.encode()).hexdigest()})
    db.password_resets.insert_one({"id": "reset-1", "user_id": "user-1", "tenant_id": "tenant-1"})


def test_reset_hashes_with_backend_hasher_and_revokes_sessions():
    db = database()
    seed(db)
    result = reset_user_password(db, "LARACONTELLE@GMAIL.COM", "Testproracontelle")
    user = db.users.find_one({"id": "user-1"})
    assert password_hash.verify("Testproracontelle", user["password_hash"])
    assert not password_hash.verify("AncienMotDePasse12", user["password_hash"])
    assert db.refresh_tokens.find_one({"id": "refresh-1"})["revoked_at"] is not None
    assert db.auth_attempts.count_documents({}) == 0
    assert db.password_resets.count_documents({}) == 0
    assert result["refresh_tokens_revoked"] == 1
    audit = db.audit_logs.find_one({"action": "auth.operator_password_reset"})
    assert audit
    assert "Testproracontelle" not in str(audit)
    assert set(audit["details"]) == {"source"}


def test_reset_is_idempotent_and_does_not_duplicate_audit():
    db = database()
    seed(db)
    reset_user_password(db, "laracontelle@gmail.com", "Testproracontelle")
    first_hash = db.users.find_one({"id": "user-1"})["password_hash"]
    reset_user_password(db, "laracontelle@gmail.com", "Testproracontelle")
    assert db.users.find_one({"id": "user-1"})["password_hash"] == first_hash
    assert db.audit_logs.count_documents({"action": "auth.operator_password_reset"}) == 1


def test_reset_refuses_missing_ambiguous_or_disabled_accounts():
    db = database()
    with pytest.raises(RuntimeError, match="0 compte"):
        reset_user_password(db, "laracontelle@gmail.com", "Testproracontelle")
    seed(db, disabled=True)
    with pytest.raises(RuntimeError, match="désactivé"):
        reset_user_password(db, "laracontelle@gmail.com", "Testproracontelle")
    db = database()
    seed(db)
    db.users.insert_one(
        {
            "id": "user-2",
            "tenant_id": "tenant-1",
            "email_lower": "laracontelle@gmail.com",
            "password_hash": password_hash.hash("AutreMotDePasse12"),
            "role": "member",
            "disabled": False,
        }
    )
    with pytest.raises(RuntimeError, match="2 compte"):
        reset_user_password(db, "laracontelle@gmail.com", "Testproracontelle")
