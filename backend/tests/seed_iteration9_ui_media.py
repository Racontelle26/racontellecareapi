import json
from pathlib import Path

import requests
from dotenv import dotenv_values


def _backend_base() -> str:
    env = dotenv_values("/app/frontend/.env")
    base = env.get("EXPO_PUBLIC_BACKEND_URL") or env.get("EXPO_BACKEND_URL")
    if not base:
        raise RuntimeError("Missing EXPO backend URL in frontend/.env")
    return base.rstrip("/") + "/api"


def _wav_bytes() -> bytes:
    return (
        b"RIFF"
        + (36 + 16).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little")
        + (16000).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + (16).to_bytes(4, "little")
        + b"\x00" * 16
    )


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64


def main() -> int:
    base = _backend_base()
    s = requests.Session()

    login = s.post(
        f"{base}/auth/login",
        json={"email": "profils@racontelle.fr", "password": "Souvenir123"},
        timeout=30,
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = s.get(f"{base}/auth/me", headers=headers, timeout=30)
    me.raise_for_status()
    member = me.json().get("member")
    if not member:
        raise RuntimeError("Account has no active circle")
    member_id = member["id"]

    data = {
        "narrator_member_id": member_id,
        "duration_sec": "5",
        "title": "TEST_I9 UI sans photo",
    }
    files = [("file", ("test.wav", _wav_bytes(), "audio/wav"))]
    no_photo = s.post(f"{base}/capsules", headers=headers, data=data, files=files, timeout=60)
    no_photo.raise_for_status()
    no_photo_id = no_photo.json()["id"]

    data2 = {
        "narrator_member_id": member_id,
        "duration_sec": "5",
        "title": "TEST_I9 UI 10 photos",
    }
    files2 = [("file", ("test10.wav", _wav_bytes(), "audio/wav"))]
    files2.extend(("photos", (f"p{i}.jpg", _jpeg_bytes(), "image/jpeg")) for i in range(10))
    ten_photo = s.post(f"{base}/capsules", headers=headers, data=data2, files=files2, timeout=120)
    ten_photo.raise_for_status()
    ten_photo_payload = ten_photo.json()

    data3 = {
        "narrator_member_id": member_id,
        "duration_sec": "5",
        "title": "TEST_I9 UI 2 photos",
    }
    files3 = [("file", ("test2.wav", _wav_bytes(), "audio/wav"))]
    files3.extend(("photos", (f"m{i}.jpg", _jpeg_bytes(), "image/jpeg")) for i in range(2))
    two_photo = s.post(f"{base}/capsules", headers=headers, data=data3, files=files3, timeout=90)
    two_photo.raise_for_status()
    two_photo_payload = two_photo.json()

    out = {
        "no_photo_capsule_id": no_photo_id,
        "two_photo_capsule_id": two_photo_payload["id"],
        "ten_photo_capsule_id": ten_photo_payload["id"],
        "two_photo_count": len(two_photo_payload.get("photos") or []),
        "ten_photo_count": len(ten_photo_payload.get("photos") or []),
    }
    Path("/app/test_reports/artifacts_iter9").mkdir(parents=True, exist_ok=True)
    Path("/app/test_reports/artifacts_iter9/ui_seed_ids.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())