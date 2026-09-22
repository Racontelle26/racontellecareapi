import io
import os
import time
import requests
from dotenv import dotenv_values


def wav_bytes() -> bytes:
    return (
        b"RIFF" + (36 + 16).to_bytes(4, "little") + b"WAVEfmt "
        + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
        + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (16).to_bytes(4, "little") + b"\x00" * 16
    )


def main():
    env = dotenv_values("/app/frontend/.env")
    base = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or env.get("EXPO_PUBLIC_BACKEND_URL", "")).rstrip("/") + "/api"
    if not base.startswith("http"):
        raise SystemExit("Missing EXPO_PUBLIC_BACKEND_URL")

    s = requests.Session()
    login = s.post(f"{base}/auth/login", json={"email": "profils@racontelle.fr", "password": "Souvenir123"})
    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    members = s.get(f"{base}/circle/members", headers=headers)
    members.raise_for_status()
    active = [m for m in members.json() if m.get("status") == "active"]

    target = next((m for m in active if str(m.get("display_name", "")).startswith("TEST_I7_Direct_")), None)
    if not target:
        raise SystemExit("No TEST_I7_Direct_* member found")

    marker = f"I7_FMT_{int(time.time())}"
    for duration in (61, 3661):
        data = {
            "narrator_member_id": target["id"],
            "duration_sec": str(duration),
            "title": f"{marker}_{duration}",
        }
        files = {"file": (f"fmt_{duration}.wav", wav_bytes(), "audio/wav")}
        resp = s.post(f"{base}/capsules", headers=headers, data=data, files=files)
        resp.raise_for_status()

    print(f"Seeded durations for member={target['id']} marker={marker}")


if __name__ == "__main__":
    main()
