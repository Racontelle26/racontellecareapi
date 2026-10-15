#!/usr/bin/env python3
"""Réinitialisation opérateur d'un mot de passe Racontelle Care.

À exécuter uniquement dans le terminal privé du service Railway. Le mot de
passe est demandé avec getpass : il n'apparaît ni dans l'historique shell, ni
dans les logs, ni dans le journal d'audit.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import os
from pathlib import Path
import sys
import uuid

from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from security import password_hash  # noqa: E402  — même instance que le login


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def find_reset_target(database, email_lower: str) -> dict:
    matches = database.users.count_documents({"email_lower": email_lower})
    if matches != 1:
        raise RuntimeError(f"Opération refusée : {matches} compte(s) correspondent à cette adresse")
    user = database.users.find_one({"email_lower": email_lower}, {"_id": 0})
    if not user or not user.get("id") or not user.get("tenant_id"):
        raise RuntimeError("Compte incomplet : identifiant utilisateur ou établissement absent")
    if user.get("disabled"):
        raise RuntimeError("Compte désactivé : aucune réactivation automatique n'est autorisée")
    tenant = database.tenants.find_one(
        {"id": user["tenant_id"], "active": {"$ne": False}}, {"_id": 0, "id": 1}
    )
    if not tenant:
        raise RuntimeError("Établissement introuvable ou désactivé")
    return user


def reset_user_password(database, email: str, new_password: str) -> dict[str, int | str]:
    email_lower = email.strip().lower()
    if len(new_password) < 12 or len(new_password) > 128:
        raise ValueError("Le mot de passe doit contenir entre 12 et 128 caractères")

    user = find_reset_target(database, email_lower)

    previous_hash = user.get("password_hash")
    if previous_hash and password_hash.verify(new_password, previous_hash):
        next_hash = previous_hash
    else:
        next_hash = password_hash.hash(new_password)

    stamp = utc_now()
    scope = {"user_id": user["id"], "tenant_id": user["tenant_id"]}
    revoked = database.refresh_tokens.update_many(
        {**scope, "revoked_at": None},
        {"$set": {"revoked_at": stamp, "revocation_reason": "operator_password_reset"}},
    ).modified_count
    attempts = database.auth_attempts.delete_many(
        {"email_hash": hashlib.sha256(email_lower.encode()).hexdigest()}
    ).deleted_count
    resets = database.password_resets.delete_many({"user_id": user["id"]}).deleted_count

    updated = database.users.update_one(
        {"id": user["id"], "tenant_id": user["tenant_id"], "disabled": {"$ne": True}},
        {"$set": {"password_hash": next_hash, "password_changed_at": stamp}},
    )
    if updated.matched_count != 1:
        raise RuntimeError("Le compte a changé pendant l'opération ; relancez la commande")

    operation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"operator-password-reset:{user['id']}"))
    database.audit_logs.update_one(
        {"id": operation_id},
        {
            "$set": {
                "tenant_id": user["tenant_id"],
                "user_id": user["id"],
                "action": "auth.operator_password_reset",
                "object_type": "user",
                "object_id": user["id"],
                "details": {"source": "railway_terminal"},
                "created_at": stamp.isoformat(),
            }
        },
        upsert=True,
    )

    verified = database.users.find_one(
        {"id": user["id"], "tenant_id": user["tenant_id"]}, {"_id": 0, "password_hash": 1}
    )
    if not verified or not password_hash.verify(new_password, verified["password_hash"]):
        raise RuntimeError("Échec de la vérification finale du nouveau mot de passe")
    return {
        "user_id": user["id"],
        "refresh_tokens_revoked": revoked,
        "attempts_deleted": attempts,
        "reset_tokens_deleted": resets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Réinitialiser un mot de passe Racontelle Care")
    parser.add_argument("--email", required=True, help="Adresse email du compte à réinitialiser")
    parser.add_argument("--dry-run", action="store_true", help="Vérifier la cible sans modifier la base")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name = os.environ.get("DB_NAME", "").strip()
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL et DB_NAME sont obligatoires")

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10_000)
    database = client[db_name]
    try:
        email_lower = args.email.strip().lower()
        find_reset_target(database, email_lower)
        if args.dry_run:
            print("OK : un compte unique et modifiable a été trouvé. Aucune donnée n'a été modifiée.")
            return
        new_password = getpass("Nouveau mot de passe : ")
        confirmation = getpass("Confirmez le nouveau mot de passe : ")
        if new_password != confirmation:
            raise SystemExit("Les deux mots de passe ne correspondent pas")
        result = reset_user_password(database, email_lower, new_password)
        print(
            "OK : mot de passe mis à jour, sessions révoquées et blocages de connexion effacés. "
            f"Jetons révoqués : {result['refresh_tokens_revoked']}."
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
