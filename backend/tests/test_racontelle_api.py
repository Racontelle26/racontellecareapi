import os
import uuid
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")


def test_questions_and_resident_capsule_flow():
    questions = requests.get(f"{BASE_URL}/api/questions?limit=3", timeout=15)
    assert questions.status_code == 200
    data = questions.json()
    assert len(data) == 3 and all({"id", "theme", "text"} <= set(item) for item in data)

    name = f"TEST_{uuid.uuid4().hex[:8]}"
    resident = requests.post(
        f"{BASE_URL}/api/residents",
        json={"display_name": name, "consent_status": "obtained"},
        timeout=15,
    )
    assert resident.status_code == 201
    resident_data = resident.json()
    assert resident_data["display_name"] == name

    capsule = requests.post(
        f"{BASE_URL}/api/capsules",
        json={
            "resident_id": resident_data["id"],
            "question_id": data[0]["id"],
            "mode": "question",
            "theme": data[0]["theme"],
            "title": data[0]["text"],
            "duration_sec": 2,
            "recorded_at": "2026-01-01T12:00:00+00:00",
        },
        timeout=15,
    )
    assert capsule.status_code == 201
    capsule_data = capsule.json()
    assert capsule_data["resident_id"] == resident_data["id"]

    listed = requests.get(
        f"{BASE_URL}/api/residents/{resident_data['id']}/capsules", timeout=15
    )
    assert listed.status_code == 200
    assert any(item["id"] == capsule_data["id"] for item in listed.json())
