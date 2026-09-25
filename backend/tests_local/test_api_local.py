"""Parcours complets de l'API sur le banc d'essai local (voir conftest.py)."""
from datetime import datetime, timezone
import importlib.util
import io
from pathlib import Path
import uuid
import zipfile

import requests

# Les critères du cahier des charges (tests/test_beta_cahier_des_charges.py)
# sont rejoués ici, tels quels, contre le serveur local.
_spec = importlib.util.spec_from_file_location(
    "beta_cdc", Path(__file__).resolve().parent.parent / "tests" / "test_beta_cahier_des_charges.py"
)
_beta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_beta)
for _name in dir(_beta):
    if _name.startswith("test_"):
        globals()[_name] = getattr(_beta, _name)

new_tenant = _beta.new_tenant
create_resident = _beta.create_resident
M4A = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 64


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def test_full_password_reset_flow(base_url, sent_codes):
    _, email = new_tenant()
    assert requests.post(f"{base_url}/api/auth/password/forgot", json={"email": email}, timeout=20).status_code == 200
    code = sent_codes[email]
    assert len(code.replace("-", "")) == 8
    new_password = "Nouveau-Mot-De-Passe-2026!"
    reset = requests.post(f"{base_url}/api/auth/password/reset", json={"email": email, "code": code.lower(), "new_password": new_password}, timeout=20)
    assert reset.status_code == 200, reset.text
    old = requests.post(f"{base_url}/api/auth/login", headers={"X-Client-Platform": "native"}, json={"email": email, "password": "Racontelle-Beta-2026!"}, timeout=20)
    assert old.status_code == 401
    fresh = requests.post(f"{base_url}/api/auth/login", headers={"X-Client-Platform": "native"}, json={"email": email, "password": new_password}, timeout=20)
    assert fresh.status_code == 200
    # Un code sert une seule fois.
    again = requests.post(f"{base_url}/api/auth/password/reset", json={"email": email, "code": code, "new_password": "Encore-Un-Autre-2026!"}, timeout=20)
    assert again.status_code == 400


def test_reset_code_is_locked_after_five_wrong_attempts(base_url, sent_codes):
    _, email = new_tenant()
    requests.post(f"{base_url}/api/auth/password/forgot", json={"email": email}, timeout=20)
    good = sent_codes[email]
    for _ in range(5):
        requests.post(f"{base_url}/api/auth/password/reset", json={"email": email, "code": "ZZZZ-ZZZZ", "new_password": "Nouveau-Mot-2026!!"}, timeout=20)
    late = requests.post(f"{base_url}/api/auth/password/reset", json={"email": email, "code": good, "new_password": "Nouveau-Mot-2026!!"}, timeout=20)
    assert late.status_code in (400, 429)


def test_password_reset_revokes_open_sessions(base_url, sent_codes):
    email = f"sessions-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    session = requests.post(f"{base_url}/api/auth/register", headers={"X-Client-Platform": "native"}, json={"email": email, "password": "Racontelle-Beta-2026!", "full_name": "Admin", "establishment_name": "EHPAD"}, timeout=20).json()
    requests.post(f"{base_url}/api/auth/password/forgot", json={"email": email}, timeout=20)
    requests.post(f"{base_url}/api/auth/password/reset", json={"email": email, "code": sent_codes[email], "new_password": "Nouveau-Mot-2026!!"}, timeout=20)
    refresh = requests.post(f"{base_url}/api/auth/refresh", headers={"X-Client-Platform": "native"}, json={"refresh_token": session["refresh_token"]}, timeout=20)
    assert refresh.status_code == 401


def test_admin_can_set_member_password(base_url):
    headers, _ = new_tenant()
    member_email = f"membre-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    member = requests.post(f"{base_url}/api/auth/members", headers=headers, json={"email": member_email, "password": "Membre-Temporaire-2026", "full_name": "Membre"}, timeout=20).json()
    assert requests.post(f"{base_url}/api/auth/members/{member['id']}/password", headers=headers, json={"new_password": "Membre-Nouveau-2026!"}, timeout=20).status_code == 200
    login = requests.post(f"{base_url}/api/auth/login", headers={"X-Client-Platform": "native"}, json={"email": member_email, "password": "Membre-Nouveau-2026!"}, timeout=20)
    assert login.status_code == 200
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    # Un membre ne supprime pas, ne règle rien, ne lit pas le journal.
    assert requests.patch(f"{base_url}/api/settings", headers=member_headers, json={"quiz": False}, timeout=20).status_code == 403
    assert requests.get(f"{base_url}/api/audit", headers=member_headers, timeout=20).status_code == 403


def test_audio_upload_share_page_and_security_headers(base_url):
    headers, _ = new_tenant()
    requests.patch(f"{base_url}/api/settings", headers=headers, json={"family_share": True}, timeout=20)
    resident = create_resident(headers, "Germaine").json()
    capsule = requests.post(f"{base_url}/api/capsules", headers=headers, json={"resident_id": resident["id"], "mode": "free", "duration_sec": 30, "recorded_at": now_iso()}, timeout=20).json()
    assert capsule["upload_status"] == "pending" and capsule["audio_stored"] is False
    upload = requests.post(f"{base_url}/api/capsules/{capsule['id']}/audio", headers=headers, files={"file": ("recording.m4a", io.BytesIO(M4A), "audio/m4a")}, timeout=20)
    assert upload.status_code == 200, upload.text
    listed = requests.get(f"{base_url}/api/capsules", headers=headers, timeout=20).json()
    assert next(item for item in listed if item["id"] == capsule["id"])["upload_status"] == "saved"
    share = requests.post(f"{base_url}/api/capsules/{capsule['id']}/share", headers=headers, timeout=20).json()
    page = requests.get(f"{base_url}{share['path']}", timeout=20)
    assert page.status_code == 200 and "Germaine" in page.text
    assert "default-src 'none'" in page.headers["Content-Security-Policy"]
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    audio = requests.get(f"{base_url}{share['path']}/audio", timeout=20)
    assert audio.status_code == 200 and audio.headers["Content-Type"].startswith("audio/")
    # Couper le partage famille coupe aussi les liens existants.
    requests.patch(f"{base_url}/api/settings", headers=headers, json={"family_share": False}, timeout=20)
    assert requests.get(f"{base_url}{share['path']}", timeout=20).status_code == 404


def test_hidden_features_are_refused_by_default(base_url):
    headers, _ = new_tenant()
    resident = create_resident(headers, "Odette").json()
    capsule = requests.post(f"{base_url}/api/capsules", headers=headers, json={"resident_id": resident["id"], "mode": "free", "duration_sec": 5, "recorded_at": now_iso()}, timeout=20).json()
    assert requests.post(f"{base_url}/api/capsules/{capsule['id']}/share", headers=headers, timeout=20).status_code == 403
    assert requests.get(f"{base_url}/api/residents/{resident['id']}/carnet", headers=headers, timeout=20).status_code == 403
    transcribe = requests.post(f"{base_url}/api/capsules/{capsule['id']}/transcribe", headers=headers, files={"file": ("r.m4a", io.BytesIO(M4A), "audio/m4a")}, timeout=20)
    assert transcribe.status_code == 403
    settings = requests.get(f"{base_url}/api/settings", headers=headers, timeout=20).json()
    assert settings["max_residents"] == 5 and settings["features"]["quiz"] is True


def test_export_zip_then_archive_then_rgpd_purge(base_url, stored_objects):
    headers, _ = new_tenant()
    requests.patch(f"{base_url}/api/settings", headers=headers, json={"carnet_pdf": True}, timeout=20)
    resident = create_resident(headers, "Henri").json()
    capsule = requests.post(f"{base_url}/api/capsules", headers=headers, json={"resident_id": resident["id"], "mode": "question", "question_id": "q061", "duration_sec": 95, "recorded_at": now_iso()}, timeout=20).json()
    requests.post(f"{base_url}/api/capsules/{capsule['id']}/audio", headers=headers, files={"file": ("recording.m4a", io.BytesIO(M4A), "audio/m4a")}, timeout=20)
    export = requests.get(f"{base_url}/api/residents/{resident['id']}/export", headers=headers, timeout=20)
    assert export.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(export.content)).namelist()
    assert "souvenirs.txt" in names and any(name.startswith("audio/") for name in names)
    carnet = requests.get(f"{base_url}/api/residents/{resident['id']}/carnet", headers=headers, timeout=20)
    assert carnet.status_code == 200 and carnet.content.startswith(b"%PDF")
    path = next(key for key in stored_objects if capsule["id"] in key)
    purge = requests.delete(f"{base_url}/api/residents/{resident['id']}/purge", headers=headers, timeout=20).json()
    assert purge["capsules_erased"] == 1
    assert path not in stored_objects  # l'audio n'existe plus dans le stockage
    assert not any(item["id"] == capsule["id"] for item in requests.get(f"{base_url}/api/capsules", headers=headers, timeout=20).json())
    actions = [entry["action"] for entry in requests.get(f"{base_url}/api/audit", headers=headers, timeout=20).json()]
    assert {"resident.export", "resident.carnet", "resident.purge"} <= set(actions)


def test_tenants_are_isolated(base_url):
    first, _ = new_tenant()
    second, _ = new_tenant()
    resident = create_resident(first, "Isolée").json()
    assert requests.get(f"{base_url}/api/residents/{resident['id']}/capsules", headers=second, timeout=20).status_code == 404
    assert requests.patch(f"{base_url}/api/residents/{resident['id']}", headers=second, json={"display_name": "Pirate"}, timeout=20).status_code == 404
    assert requests.get(f"{base_url}/api/residents", headers=second, timeout=20).json() == []


def test_quiz_json_import_with_private_music_url(base_url):
    headers, _ = new_tenant()
    content = '[{"id":"M010","type":"music","prompt_text":"Qui chante ça ?","audio_file":"https://example.org/extrait.mp3","correct_answer":"Artiste A","choice_a":"Artiste A","choice_b":"Artiste B","rights_status":"licensed","license_note":"Contrat 2026-01","active":true}]'
    report = requests.post(f"{base_url}/api/quiz/import", headers=headers, json={"format": "json", "content": content}, timeout=20).json()
    assert report["created"] == 1 and not report["inactive"], report
    music = requests.get(f"{base_url}/api/quiz/items?type=music", headers=headers, timeout=20).json()
    assert [item["id"] for item in music] == ["M010"] and music[0]["audio_url"].startswith("https://")
    filters = requests.get(f"{base_url}/api/quiz/filters", headers=headers, timeout=20).json()
    assert "XVIIe siècle" in filters["eras"]


def test_offline_capsule_keeps_original_recording_time(base_url):
    headers, _ = new_tenant()
    resident = create_resident(headers, "Suzanne").json()
    recorded = "2026-09-01T09:15:00+00:00"  # enregistré hors connexion, envoyé plus tard
    capsule = requests.post(f"{base_url}/api/capsules", headers=headers, json={"resident_id": resident["id"], "mode": "free", "duration_sec": 12, "recorded_at": recorded}, timeout=20).json()
    assert capsule["recorded_at"] == recorded and capsule["created_at"] > recorded
    assert capsule["created_by_name"] == "Admin Bêta"
