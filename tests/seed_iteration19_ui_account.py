import json
import time
from pathlib import Path

import requests
from dotenv import dotenv_values


def env_backend_url() -> str:
    frontend_env = dotenv_values("/app/frontend/.env")
    base = frontend_env.get("EXPO_PUBLIC_BACKEND_URL") or frontend_env.get("EXPO_BACKEND_URL")
    if not base:
        raise RuntimeError("Missing EXPO_PUBLIC_BACKEND_URL/EXPO_BACKEND_URL in frontend/.env")
    return base.rstrip("/") + "/api"


def wav_bytes() -> bytes:
    return (
        b"RIFF" + (36 + 16).to_bytes(4, "little") + b"WAVEfmt "
        + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
        + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (16).to_bytes(4, "little") + b"\x00" * 16
    )


def main() -> None:
    base_url = env_backend_url()
    s = requests.Session()
    stamp = str(int(time.time() * 1000))
    email = f"test_ui_i19_{stamp}@racontelle-test.fr"
    password = "Souvenir123"

    register = s.post(
        f"{base_url}/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "UI I19 Owner",
            "relationship_label": "Parent",
            "accept_terms": True,
        },
        timeout=30,
    )
    register.raise_for_status()
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    circle = s.post(
        f"{base_url}/circles",
        headers=headers,
        json={
            "name": f"Famille UI I19 {stamp}",
            "initial_members": [
                {"display_name": "UI I19 Profil 1", "relationship_label": "Frère"},
                {"display_name": "UI I19 Profil 2", "relationship_label": "Soeur"},
                {"display_name": "UI I19 Profil 3", "relationship_label": "Ami"},
            ],
        },
        timeout=30,
    )
    circle.raise_for_status()
    owner_member_id = circle.json()["member"]["id"]

    files = [("file", ("memo.wav", wav_bytes(), "audio/wav"))]

    unavailable = s.post(
        f"{base_url}/capsules",
        headers=headers,
        data={"narrator_member_id": owner_member_id, "duration_sec": "2", "title": "UI I19 unavailable"},
        files=files,
        timeout=60,
    )
    unavailable.raise_for_status()

    done = s.post(
        f"{base_url}/capsules",
        headers=headers,
        data={
            "narrator_member_id": owner_member_id,
            "duration_sec": "2",
            "title": "UI I19 done",
            "transcript": "TEST_UI_I19_TRANSCRIPT_DONE",
        },
        files=[("file", ("memo2.wav", wav_bytes(), "audio/wav"))],
        timeout=60,
    )
    done.raise_for_status()

    output = {
        "email": email,
        "password": password,
        "capsule_unavailable_id": unavailable.json()["id"],
        "capsule_done_id": done.json()["id"],
    }
    out_path = Path("/app/test_reports/artifacts_iter19/ui_seed.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
