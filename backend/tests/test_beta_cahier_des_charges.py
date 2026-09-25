"""Critères de recette du cahier des charges bêta (BT-01 à BT-22) couverts
côté API, sur un établissement neuf pour ne dépendre d'aucune donnée."""
from datetime import datetime, timezone
import io
import os
import uuid

import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")


def new_tenant():
    email = f"beta-{uuid.uuid4().hex[:8]}@racontelle.example.com"
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        headers={"X-Client-Platform": "native"},
        json={"email": email, "password": "Racontelle-Beta-2026!", "full_name": "Admin Bêta", "establishment_name": "EHPAD Bêta"},
        timeout=30,
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email


def create_resident(headers, name="Jeanne", consent="obtained"):
    return requests.post(f"{BASE_URL}/api/residents", headers=headers, json={"display_name": name, "consent_status": consent}, timeout=20)


def test_bt01_five_profiles_maximum():
    headers, _ = new_tenant()
    for index in range(5):
        assert create_resident(headers, f"Profil {index}").status_code == 201
    sixth = create_resident(headers, "Sixième")
    assert sixth.status_code == 400
    assert "5" in sixth.json()["detail"]


def test_bt02_consent_status_visible_and_logged():
    headers, _ = new_tenant()
    resident = create_resident(headers, "Paul", consent="pending").json()
    assert resident["consent_status"] == "pending"
    blocked = requests.post(f"{BASE_URL}/api/capsules", headers=headers, json={"resident_id": resident["id"], "mode": "free", "duration_sec": 3, "recorded_at": datetime.now(timezone.utc).isoformat()}, timeout=20)
    assert blocked.status_code == 403
    updated = requests.patch(f"{BASE_URL}/api/residents/{resident['id']}", headers=headers, json={"consent_status": "obtained"}, timeout=20)
    assert updated.json()["consent_status"] == "obtained"
    logs = requests.get(f"{BASE_URL}/api/residents/{resident['id']}/consents", headers=headers, timeout=20).json()
    assert [log["status"] for log in logs][:2] == ["obtained", "pending"]
    audit = requests.get(f"{BASE_URL}/api/audit", headers=headers, timeout=20).json()
    assert any(entry["action"] == "resident.consent_change" for entry in audit)


def test_bt06_bt07_question_bank_and_sensitive_themes():
    headers, _ = new_tenant()
    questions = requests.get(f"{BASE_URL}/api/questions", headers=headers, timeout=20).json()
    assert len(questions) == 360  # 400 moins les 2 thèmes sensibles, inactifs par défaut
    assert not any(question["sensitive"] for question in questions)
    assert {"number", "theme", "text", "level", "usage", "tags"} <= set(questions[0])
    themes = requests.get(f"{BASE_URL}/api/questions/themes", headers=headers, timeout=20).json()
    assert len(themes) == 20
    assert sum(1 for theme in themes if theme["sensitive"] and not theme["enabled"]) == 2
    requests.patch(f"{BASE_URL}/api/settings", headers=headers, json={"sensitive_themes": True}, timeout=20)
    assert len(requests.get(f"{BASE_URL}/api/questions", headers=headers, timeout=20).json()) == 400
    toggled = requests.patch(f"{BASE_URL}/api/questions/q001", headers=headers, json={"active": False}, timeout=20)
    assert toggled.status_code == 200
    assert len(requests.get(f"{BASE_URL}/api/questions", headers=headers, timeout=20).json()) == 399


def test_bt10_to_bt13_spontaneous_then_classified_with_audit():
    headers, _ = new_tenant()
    first = create_resident(headers, "Marie").json()
    second = create_resident(headers, "Louise").json()
    recorded_at = "2026-09-20T15:42:00+00:00"
    capsule = requests.post(f"{BASE_URL}/api/capsules", headers=headers, json={"mode": "free", "duration_sec": 400, "recorded_at": recorded_at}, timeout=20).json()
    assert capsule["status"] == "unclassified" and capsule["resident_id"] is None
    assert capsule["title"].startswith("Souvenir spontané")
    assert capsule["duration_sec"] == 400  # aucune coupure à 5 minutes (BT-09)
    unclassified = requests.get(f"{BASE_URL}/api/capsules/unclassified", headers=headers, timeout=20).json()
    assert any(item["id"] == capsule["id"] and item["recorded_at"] == recorded_at for item in unclassified)
    requests.patch(f"{BASE_URL}/api/settings", headers=headers, json={"family_share": True}, timeout=20)
    share = requests.post(f"{BASE_URL}/api/capsules/{capsule['id']}/share", headers=headers, timeout=20)
    assert share.status_code == 400  # un souvenir « À classer » ne se partage pas
    classified = requests.patch(f"{BASE_URL}/api/capsules/{capsule['id']}/assign?resident_id={first['id']}", headers=headers, timeout=20).json()
    assert classified["resident_id"] == first["id"] and classified["recorded_at"] == recorded_at
    requests.patch(f"{BASE_URL}/api/capsules/{capsule['id']}/assign?resident_id={second['id']}", headers=headers, timeout=20)
    actions = [entry["action"] for entry in requests.get(f"{BASE_URL}/api/audit", headers=headers, timeout=20).json()]
    assert "capsule.classify" in actions and "capsule.reassign" in actions


def test_guided_capsule_requires_resident():
    headers, _ = new_tenant()
    response = requests.post(f"{BASE_URL}/api/capsules", headers=headers, json={"mode": "question", "question_id": "q001", "duration_sec": 5, "recorded_at": datetime.now(timezone.utc).isoformat()}, timeout=20)
    assert response.status_code == 400


def test_bt20_capsule_deletion_is_logged():
    headers, _ = new_tenant()
    resident = create_resident(headers, "Albert").json()
    capsule = requests.post(f"{BASE_URL}/api/capsules", headers=headers, json={"resident_id": resident["id"], "mode": "question", "question_id": "q021", "duration_sec": 12, "recorded_at": datetime.now(timezone.utc).isoformat()}, timeout=20).json()
    assert capsule["title"] == "Quel est votre tout premier souvenir ?"
    assert requests.delete(f"{BASE_URL}/api/capsules/{capsule['id']}", headers=headers, timeout=20).status_code == 200
    listed = requests.get(f"{BASE_URL}/api/capsules", headers=headers, timeout=20).json()
    assert not any(item["id"] == capsule["id"] for item in listed)
    assert requests.get(f"{BASE_URL}/api/capsules/{capsule['id']}/audio", headers=headers, timeout=20).status_code == 404
    audit = requests.get(f"{BASE_URL}/api/audit", headers=headers, timeout=20).json()
    assert any(entry["action"] == "capsule.delete" and entry["object_id"] == capsule["id"] for entry in audit)


def test_bt15_to_bt19_quiz_rules():
    headers, _ = new_tenant()
    items = requests.get(f"{BASE_URL}/api/quiz/items?type=quote", headers=headers, timeout=20).json()
    assert items and all(2 <= len(item["choices"]) <= 4 and item["correct_answer"] in item["choices"] for item in items)
    report = requests.post(
        f"{BASE_URL}/api/quiz/import",
        headers=headers,
        json={"format": "csv", "content": "id;type;prompt_text;audio_file;correct_answer;choice_a;choice_b;choice_c;choice_d;era;theme;difficulty;source_reference;rights_status;license_note;active\nM001;music;Qui chante ça ?;extrait.mp3;Artiste A;Artiste A;Artiste B;;;1960-1970;chanson française;facile;test;blocked;;true\n"},
        timeout=20,
    ).json()
    assert report["created"] == 1 and report["inactive"]
    activate = requests.patch(f"{BASE_URL}/api/quiz/items/M001", headers=headers, json={"active": True}, timeout=20)
    assert activate.status_code == 400  # contenu bloqué : jamais actif (BT-19)
    first = items[0]["id"]
    assert requests.patch(f"{BASE_URL}/api/quiz/items/{first}", headers=headers, json={"active": False}, timeout=20).status_code == 200
    assert not any(item["id"] == first for item in requests.get(f"{BASE_URL}/api/quiz/items", headers=headers, timeout=20).json())
    assert any(item["id"] == first for item in requests.get(f"{BASE_URL}/api/quiz/admin/items", headers=headers, timeout=20).json())  # BT-18
    session = requests.post(f"{BASE_URL}/api/quiz/sessions", headers=headers, json={"quiz_type": "quote", "item_count": 5, "score": 3}, timeout=20).json()
    assert "resident_id" not in session  # BT-17


def test_bt22_feedback_with_app_version_and_indicators():
    headers, _ = new_tenant()
    feedback = requests.post(f"{BASE_URL}/api/feedback", headers=headers, json={"category": "micro", "message": "Le micro coupe", "app_version": "1.0.0-beta"}, timeout=20)
    assert feedback.status_code == 201 and feedback.json()["app_version"] == "1.0.0-beta"
    assert requests.post(f"{BASE_URL}/api/events", headers=headers, json={"type": "question_change"}, timeout=20).status_code == 201
    indicators = requests.get(f"{BASE_URL}/api/indicators", headers=headers, timeout=20).json()
    assert indicators["guided"]["question_changes"] == 1 and indicators["feedback"]["micro"] == 1
    csv_export = requests.get(f"{BASE_URL}/api/indicators?format=csv", headers=headers, timeout=20)
    assert csv_export.status_code == 200 and "indicateur;valeur" in csv_export.text


def test_password_reset_never_reveals_accounts_and_rejects_bad_codes():
    _, email = new_tenant()
    known = requests.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": email}, timeout=20)
    unknown = requests.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": f"inconnu-{uuid.uuid4().hex[:6]}@racontelle.example.com"}, timeout=20)
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    wrong = requests.post(f"{BASE_URL}/api/auth/password/reset", json={"email": email, "code": "ABCD-EFGH", "new_password": "Nouveau-Mot-2026!"}, timeout=20)
    assert wrong.status_code == 400


def test_audio_upload_refuses_html_disguised_as_audio():
    headers, _ = new_tenant()
    resident = create_resident(headers, "Rose").json()
    capsule = requests.post(f"{BASE_URL}/api/capsules", headers=headers, json={"resident_id": resident["id"], "mode": "free", "duration_sec": 2, "recorded_at": datetime.now(timezone.utc).isoformat()}, timeout=20).json()
    upload = requests.post(
        f"{BASE_URL}/api/capsules/{capsule['id']}/audio",
        headers=headers,
        files={"file": ("page.html", io.BytesIO(b"<script>alert(1)</script>"), "text/html")},
        timeout=20,
    )
    assert upload.status_code == 415


def test_member_cannot_archive_resident_through_patch():
    headers, _ = new_tenant()
    resident = create_resident(headers, "Lucien").json()
    patched = requests.patch(f"{BASE_URL}/api/residents/{resident['id']}", headers=headers, json={"active": False}, timeout=20)
    assert patched.status_code == 200 and patched.json()["active"] is True
