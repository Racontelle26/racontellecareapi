"""Iteration 8 security tests: media signature validation, limits, headers, auth isolation."""

import os
import time
import requests
import pytest
from dotenv import dotenv_values


def _env_backend_url() -> str | None:
    frontend_env = dotenv_values("/app/frontend/.env")
    return (
        os.environ.get("EXPO_BACKEND_URL")
        or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
        or frontend_env.get("EXPO_BACKEND_URL")
        or frontend_env.get("EXPO_PUBLIC_BACKEND_URL")
    )


@pytest.fixture(scope="session")
def base_url() -> str:
    backend_url = _env_backend_url()
    if not backend_url:
        pytest.skip("EXPO_BACKEND_URL/EXPO_PUBLIC_BACKEND_URL is required for public-endpoint testing")
    return backend_url.rstrip("/") + "/api"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


def _stamp() -> str:
    return str(int(time.time() * 1000))


def _register_with_circle(base_url: str, session: requests.Session, prefix: str):
    creds = {
        "email": f"TEST_i8_{prefix}_{_stamp()}@racontelle-test.fr",
        "password": "Souvenir123",
        "display_name": f"I8 {prefix}",
        "relationship_label": "Parent",
        "accept_terms": True,
    }
    reg = session.post(f"{base_url}/auth/register", json=creds)
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    circle = session.post(f"{base_url}/circles", json={"name": f"Famille I8 {prefix}"}, headers=headers)
    assert circle.status_code == 200, circle.text
    return {
        "token": token,
        "headers": headers,
        "member_id": circle.json()["member"]["id"],
        "user": reg.json()["user"],
    }


@pytest.fixture(scope="session")
def owner_ctx(base_url, session):
    return _register_with_circle(base_url, session, "owner")


@pytest.fixture(scope="session")
def other_ctx(base_url, session):
    return _register_with_circle(base_url, session, "other")


def _capsule_count(base_url: str, session: requests.Session, headers: dict) -> int:
    r = session.get(f"{base_url}/capsules", headers=headers)
    assert r.status_code == 200, r.text
    return len(r.json())


def _wav_bytes() -> bytes:
    return (
        b"RIFF" + (36 + 16).to_bytes(4, "little") + b"WAVEfmt "
        + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
        + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (16).to_bytes(4, "little") + b"\x00" * 16
    )


def _mp3_bytes() -> bytes:
    return b"ID3\x04\x00\x00\x00\x00\x00\x21" + b"\x00" * 64


def _webm_bytes() -> bytes:
    return b"\x1a\x45\xdf\xa3" + b"\x00" * 128


def _mp4_bytes() -> bytes:
    return b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 64


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _webp_bytes() -> bytes:
    return b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"\x00" * 64


def _heic_bytes() -> bytes:
    return b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64


def _sized_wav(total_size: int) -> bytes:
    header = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 8
    if total_size <= len(header):
        return header
    return header + (b"\x00" * (total_size - len(header)))


def _sized_jpeg(total_size: int) -> bytes:
    header = b"\xff\xd8\xff\xe0"
    if total_size <= len(header):
        return header
    return header + (b"\x00" * (total_size - len(header)))


def _post_capsule(base_url: str, session: requests.Session, headers: dict, member_id: str, file_tuple, duration: str = "5", photos=None):
    data = {
        "narrator_member_id": member_id,
        "duration_sec": duration,
        "title": "TEST_I8 media",
    }
    files = [("file", file_tuple)]
    if photos:
        files.extend(("photos", p) for p in photos)
    return session.post(f"{base_url}/capsules", headers=headers, data=data, files=files, timeout=180)


# Audio signature acceptance even when client MIME/extension is misleading.
@pytest.mark.parametrize(
    "name,data,client_mime,expected_server_mime",
    [
        ("fake_ext.m4a", _wav_bytes(), "text/plain", "audio/wav"),
        ("fake_ext.wav", _mp3_bytes(), "application/octet-stream", "audio/mpeg"),
        ("fake_ext.mp3", _webm_bytes(), "audio/mpeg", "audio/webm"),
        ("fake_ext.webm", _mp4_bytes(), "audio/webm", "audio/mp4"),
    ],
)
def test_create_capsule_accepts_valid_audio_signature_and_derives_safe_mime(base_url, session, owner_ctx, name, data, client_mime, expected_server_mime):
    r = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        (name, data, client_mime),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["mime_type"] == expected_server_mime


# Rejected spoofed media should not create new capsule records.
@pytest.mark.parametrize(
    "filename,client_mime",
    [
        ("evil.jpg", "image/jpeg"),
        ("evil.m4a", "audio/mp4"),
        ("evil.jpg", "text/html"),
        ("evil.m4a", "application/javascript"),
    ],
)
def test_create_capsule_rejects_html_spoofed_media_without_creating_record(base_url, session, owner_ctx, filename, client_mime):
    before = _capsule_count(base_url, session, owner_ctx["headers"])
    r = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        (filename, b"<html><script>alert(1)</script></html>", client_mime),
    )
    assert r.status_code == 415, r.text
    after = _capsule_count(base_url, session, owner_ctx["headers"])
    assert after == before


# Payload and file-size limits.
def test_create_capsule_rejects_audio_above_50mib_with_413(base_url, session, owner_ctx):
    oversized = b"RIFF" + b"\x00" * ((50 * 1024 * 1024) + 1)
    r = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("too-big.wav", oversized, "audio/wav"),
    )
    assert r.status_code == 413, r.text


def test_create_capsule_rejects_more_than_10_photos_with_413(base_url, session, owner_ctx):
    photos = [(f"p{i}.jpg", _jpeg_bytes(), "image/jpeg") for i in range(11)]
    r = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("ok.wav", _wav_bytes(), "audio/wav"),
        photos=photos,
    )
    assert r.status_code == 413, r.text


def test_create_capsule_rejects_single_photo_above_10mib_with_413(base_url, session, owner_ctx):
    huge_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * ((10 * 1024 * 1024) + 1)
    r = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("ok.wav", _wav_bytes(), "audio/wav"),
        photos=[("too-big.jpg", huge_jpeg, "image/jpeg")],
    )
    assert r.status_code == 413, r.text


def test_request_total_above_100mib_rejected_with_413(base_url, session, owner_ctx):
    audio_41_mib = _sized_wav(41 * 1024 * 1024)
    photo_10_mib = _sized_jpeg(10 * 1024 * 1024)
    photos = [(f"p{i}.jpg", photo_10_mib, "image/jpeg") for i in range(6)]  # 41 + 60 = 101 MiB
    r = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("large.wav", audio_41_mib, "audio/wav"),
        photos=photos,
    )
    assert r.status_code == 413, r.text


# duration_sec bounds.
@pytest.mark.parametrize("duration,status", [("0", 422), ("7201", 422), ("1", 200), ("7200", 200)])
def test_duration_bounds_validation(base_url, session, owner_ctx, duration, status):
    r = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("ok.wav", _wav_bytes(), "audio/wav"),
        duration=duration,
    )
    assert r.status_code == status, r.text


# /capsules/{id}/photos signature validation and max-total enforcement.
def test_add_photos_accepts_jpeg_png_webp_heic_signatures(base_url, session, owner_ctx):
    created = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("base.wav", _wav_bytes(), "audio/wav"),
    )
    assert created.status_code == 200, created.text
    capsule_id = created.json()["id"]
    files = [
        ("photos", ("a.jpg", _jpeg_bytes(), "image/jpeg")),
        ("photos", ("b.png", _png_bytes(), "image/png")),
        ("photos", ("c.webp", _webp_bytes(), "image/webp")),
        ("photos", ("d.heic", _heic_bytes(), "image/heic")),
    ]
    add = session.post(f"{base_url}/capsules/{capsule_id}/photos", headers=owner_ctx["headers"], files=files)
    assert add.status_code == 200, add.text
    assert len(add.json()["photos"]) >= 4


def test_add_photos_rejects_html_payload_even_if_image_jpeg(base_url, session, owner_ctx):
    created = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("base2.wav", _wav_bytes(), "audio/wav"),
    )
    assert created.status_code == 200, created.text
    capsule_id = created.json()["id"]
    add = session.post(
        f"{base_url}/capsules/{capsule_id}/photos",
        headers=owner_ctx["headers"],
        files=[("photos", ("spoof.jpg", b"<html>not image</html>", "image/jpeg"))],
    )
    assert add.status_code == 415, add.text


def test_add_photos_enforces_total_limit_across_calls(base_url, session, owner_ctx):
    created = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("base3.wav", _wav_bytes(), "audio/wav"),
    )
    assert created.status_code == 200, created.text
    capsule_id = created.json()["id"]

    first_batch = [("photos", (f"p{i}.jpg", _jpeg_bytes(), "image/jpeg")) for i in range(10)]
    add_ok = session.post(f"{base_url}/capsules/{capsule_id}/photos", headers=owner_ctx["headers"], files=first_batch)
    assert add_ok.status_code == 200, add_ok.text
    assert len(add_ok.json()["photos"]) == 10

    eleventh = session.post(
        f"{base_url}/capsules/{capsule_id}/photos",
        headers=owner_ctx["headers"],
        files=[("photos", ("p11.jpg", _jpeg_bytes(), "image/jpeg"))],
    )
    assert eleventh.status_code == 413, eleventh.text


# Media serving headers, allowlisted content-type, and access isolation.
def test_get_audio_and_photo_headers_safe_and_circle_isolated(base_url, session, owner_ctx, other_ctx):
    created = _post_capsule(
        base_url,
        session,
        owner_ctx["headers"],
        owner_ctx["member_id"],
        ("lied.mp3", _wav_bytes(), "text/html"),
        photos=[("lied.jpg", _jpeg_bytes(), "application/javascript")],
    )
    assert created.status_code == 200, created.text
    cap = created.json()
    capsule_id = cap["id"]
    photo_id = cap["photos"][0]["id"]

    audio = session.get(f"{base_url}/capsules/{capsule_id}/audio", params={"token": owner_ctx["token"]})
    assert audio.status_code == 200, audio.text
    assert audio.headers.get("x-content-type-options") == "nosniff"
    assert "inline" in (audio.headers.get("content-disposition") or "")
    audio_cache = (audio.headers.get("cache-control") or "").lower()
    assert ("no-store" in audio_cache) or ("private" in audio_cache)
    assert "public" not in audio_cache
    assert audio.headers.get("content-type", "").split(";")[0] in {"audio/wav", "audio/mpeg", "audio/webm", "audio/mp4"}
    assert audio.headers.get("content-type", "").split(";")[0] not in {"text/html", "application/javascript"}

    photo = session.get(f"{base_url}/capsules/{capsule_id}/photos/{photo_id}", params={"token": owner_ctx["token"]})
    assert photo.status_code == 200, photo.text
    assert photo.headers.get("x-content-type-options") == "nosniff"
    assert "inline" in (photo.headers.get("content-disposition") or "")
    photo_cache = (photo.headers.get("cache-control") or "").lower()
    assert ("no-store" in photo_cache) or ("private" in photo_cache)
    assert "public" not in photo_cache
    assert photo.headers.get("content-type", "").split(";")[0] in {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    assert photo.headers.get("content-type", "").split(";")[0] not in {"text/html", "application/javascript"}

    # Different-circle user token must not access owner media.
    denied_audio = session.get(f"{base_url}/capsules/{capsule_id}/audio", params={"token": other_ctx["token"]})
    denied_photo = session.get(f"{base_url}/capsules/{capsule_id}/photos/{photo_id}", params={"token": other_ctx["token"]})
    assert denied_audio.status_code in (403, 404)
    assert denied_photo.status_code in (403, 404)
