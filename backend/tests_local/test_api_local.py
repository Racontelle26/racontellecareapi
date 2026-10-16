"""Parcours complets de l'API sur le banc d'essai local (voir conftest.py)."""
from datetime import datetime, timezone
import time
import importlib.util
import io
from pathlib import Path
import uuid
import wave
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


def wait_code(sent_codes, email, timeout=3.0):
    """Le code part dans une tâche d'arrière-plan, après la réponse HTTP."""
    deadline = time.monotonic() + timeout
    while email not in sent_codes and time.monotonic() < deadline:
        time.sleep(0.02)
    return sent_codes[email]
create_resident = _beta.create_resident
M4A = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 64


def pcm_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 3200)
    return output.getvalue()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def test_full_password_reset_flow(base_url, sent_codes):
    _, email = new_tenant()
    assert requests.post(f"{base_url}/api/auth/password/forgot", json={"email": email}, timeout=20).status_code == 200
    code = wait_code(sent_codes, email)
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
    good = wait_code(sent_codes, email)
    for _ in range(5):
        requests.post(f"{base_url}/api/auth/password/reset", json={"email": email, "code": "ZZZZ-ZZZZ", "new_password": "Nouveau-Mot-2026!!"}, timeout=20)
    late = requests.post(f"{base_url}/api/auth/password/reset", json={"email": email, "code": good, "new_password": "Nouveau-Mot-2026!!"}, timeout=20)
    assert late.status_code in (400, 429)


def test_password_reset_revokes_open_sessions(base_url, sent_codes):
    email = f"sessions-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    session = requests.post(f"{base_url}/api/auth/register", headers={"X-Client-Platform": "native"}, json={"email": email, "password": "Racontelle-Beta-2026!", "full_name": "Admin", "establishment_name": "EHPAD"}, timeout=20).json()
    requests.post(f"{base_url}/api/auth/password/forgot", json={"email": email}, timeout=20)
    requests.post(f"{base_url}/api/auth/password/reset", json={"email": email, "code": wait_code(sent_codes, email), "new_password": "Nouveau-Mot-2026!!"}, timeout=20)
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


def test_azure_transcription_route_persists_only_final_text(base_url, monkeypatch):
    from local_env import server as local_server

    calls = []

    async def fake_azure_stt(wav_data):
        calls.append(wav_data)
        return "Je me souviens des vacances en Bretagne."

    monkeypatch.setattr(local_server, "transcribe_wav", fake_azure_stt)
    headers, _ = new_tenant()
    requests.patch(f"{base_url}/api/settings", headers=headers, json={"transcription": True}, timeout=20)
    resident = create_resident(headers, "Madeleine").json()
    capsule = requests.post(
        f"{base_url}/api/capsules",
        headers=headers,
        json={"resident_id": resident["id"], "mode": "free", "duration_sec": 2, "recorded_at": now_iso()},
        timeout=20,
    ).json()
    response = requests.post(
        f"{base_url}/api/capsules/{capsule['id']}/transcribe",
        headers=headers,
        files={"file": ("recording.wav", io.BytesIO(pcm_wav()), "audio/wav")},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    assert response.json()["transcription"] == "Je me souviens des vacances en Bretagne."
    assert len(calls) == 1 and calls[0].startswith(b"RIFF")
    listed = requests.get(f"{base_url}/api/capsules", headers=headers, timeout=20).json()
    saved = next(item for item in listed if item["id"] == capsule["id"])
    assert saved["transcription"] == response.json()["transcription"]


def test_azure_tts_route_reuses_existing_mongo_cache(base_url, monkeypatch):
    from local_env import server as local_server

    generated = []

    async def fake_azure_tts(text):
        generated.append(text)
        return b"ID3" + b"\x00" * 900

    monkeypatch.setattr(local_server, "synthesize_speech", fake_azure_tts)
    headers, _ = new_tenant()
    requests.patch(f"{base_url}/api/settings", headers=headers, json={"voice_reading": True}, timeout=20)
    payload = {"text": "Racontez-moi votre plus beau souvenir d'enfance."}
    first = requests.post(f"{base_url}/api/tts", headers=headers, json=payload, timeout=20)
    second = requests.post(f"{base_url}/api/tts", headers=headers, json=payload, timeout=20)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["path"] == second.json()["path"]
    assert generated == [payload["text"]]
    audio = requests.get(f"{base_url}{first.json()['path']}", headers=headers, timeout=20)
    assert audio.status_code == 200
    assert audio.headers["Content-Type"].startswith("audio/mpeg")
    assert audio.content.startswith(b"ID3")


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


# ---------------------------------------------------------------------------
# Renouvellement de session sur réseau faible (bug « session expirée » en atelier)
# ---------------------------------------------------------------------------

def _native_session(base_url):
    email = f"reseau-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    return requests.post(f"{base_url}/api/auth/register", headers={"X-Client-Platform": "native"}, json={"email": email, "password": "Racontelle-Reseau-2026!", "full_name": "Animatrice", "establishment_name": "EHPAD Réseau"}, timeout=20).json()


def _refresh(base_url, token):
    return requests.post(f"{base_url}/api/auth/refresh", headers={"X-Client-Platform": "native"}, json={"refresh_token": token}, timeout=20)


def test_lost_refresh_response_does_not_end_session(base_url):
    session = _native_session(base_url)
    first = _refresh(base_url, session["refresh_token"])
    assert first.status_code == 200
    # La réponse s'est perdue : le téléphone renvoie le même jeton.
    retry = _refresh(base_url, session["refresh_token"])
    assert retry.status_code == 200, retry.text
    # Le jeton jamais reçu est annulé, le nouveau fonctionne et continue la session.
    assert _refresh(base_url, first.json()["refresh_token"]).status_code == 401
    following = _refresh(base_url, retry.json()["refresh_token"])
    assert following.status_code == 200
    me = requests.get(f"{base_url}/api/auth/me", headers={"Authorization": f"Bearer {following.json()['access_token']}"}, timeout=20)
    assert me.status_code == 200


def test_late_replay_closes_the_whole_session(base_url):
    session = _native_session(base_url)
    renewed = _refresh(base_url, session["refresh_token"]).json()
    # Le jeton a été renouvelé il y a plus de 2 minutes : son rejeu ressemble à un vol.
    from local_env import server as _server  # base simulée partagée
    import asyncio
    from datetime import timedelta as _td

    async def age_token():
        await _server.db.refresh_tokens.update_many({"replaced_by": {"$ne": None}}, {"$set": {"rotated_at": datetime.now(timezone.utc) - _td(minutes=5)}})

    asyncio.run(age_token())
    assert _refresh(base_url, session["refresh_token"]).status_code == 401
    assert _refresh(base_url, renewed["refresh_token"]).status_code == 401


def test_logged_out_token_is_refused(base_url):
    session = _native_session(base_url)
    headers = {"Authorization": f"Bearer {session['access_token']}", "X-Client-Platform": "native"}
    requests.post(f"{base_url}/api/auth/logout", headers=headers, json={"refresh_token": session["refresh_token"]}, timeout=20)
    assert _refresh(base_url, session["refresh_token"]).status_code == 401


def test_web_refresh_cookie_is_cross_site(base_url):
    """La page web et l'API sont sur deux sites : le cookie doit être SameSite=None + Secure."""
    _, email = new_tenant()
    resp = requests.post(
        f"{base_url}/api/auth/login",
        headers={"X-Client-Platform": "web"},
        json={"email": email, "password": "Racontelle-Beta-2026!"},
        timeout=20,
    )
    assert resp.status_code == 200, resp.text
    cookie = resp.headers.get("set-cookie", "").lower()
    assert "racontelle_refresh=" in cookie
    assert "samesite=none" in cookie and "secure" in cookie and "httponly" in cookie
    assert "partitioned" in cookie
    refreshed = requests.post(
        f"{base_url}/api/auth/refresh",
        headers={"X-Client-Platform": "web"},
        cookies={"racontelle_refresh": resp.cookies.get("racontelle_refresh") or cookie.split("racontelle_refresh=")[1].split(";")[0]},
        json={"refresh_token": None},
        timeout=20,
    )
    assert refreshed.status_code == 200, refreshed.text
    assert "partitioned" in refreshed.headers.get("set-cookie", "").lower()
