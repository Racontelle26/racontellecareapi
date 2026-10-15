import asyncio
import httpx
import pytest

import email_service


def test_password_reset_template_contains_safe_link_and_code(monkeypatch):
    monkeypatch.setattr(email_service, "PASSWORD_RESET_URL", "https://ehpad-recall.preview.emergentagent.com")
    subject, html = email_service.build_password_reset_email(
        "Camille <script>", "camille@example.com", "ABCD-EFGH", 30
    )
    assert "Racontelle Care" in subject
    assert "ABCD-EFGH" in html
    assert "reset_email=camille%40example.com" in html
    assert "reset_code=ABCD-EFGH" in html
    assert "<script>" not in html
    assert "<form" not in html.lower() and "<input" not in html.lower()


def test_official_resend_payload_keeps_key_out_of_body(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 202

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "email-123"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, headers, json):
            captured.update(url=url, headers=headers, json=json)
            return FakeResponse()

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_secret_test_key")
    monkeypatch.setattr(email_service, "RESEND_FROM_EMAIL", "no-reply@racontellecare.com")
    monkeypatch.setattr(email_service, "PASSWORD_RESET_URL", "https://ehpad-recall.preview.emergentagent.com")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    email_id = asyncio.run(
        email_service.send_password_reset_email("camille@example.com", "Camille", "ABCD-EFGH", 30)
    )
    assert email_id == "email-123"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_secret_test_key"
    assert captured["json"]["from"] == "Racontelle Care <no-reply@racontellecare.com>"
    assert "re_secret_test_key" not in str(captured["json"])


def test_unsafe_reset_url_is_a_configuration_error(monkeypatch):
    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_secret_test_key")
    monkeypatch.setattr(email_service, "RESEND_FROM_EMAIL", "no-reply@racontellecare.com")
    monkeypatch.setattr(email_service, "PASSWORD_RESET_URL", "http://127.0.0.1/reset")
    with pytest.raises(email_service.EmailConfigurationError):
        asyncio.run(email_service.send_password_reset_email("camille@example.com", "Camille", "ABCD-EFGH", 30))


def test_shortened_reset_url_is_a_configuration_error(monkeypatch):
    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_secret_test_key")
    monkeypatch.setattr(email_service, "RESEND_FROM_EMAIL", "no-reply@racontellecare.com")
    monkeypatch.setattr(email_service, "PASSWORD_RESET_URL", "https://bit.ly/reset")
    with pytest.raises(email_service.EmailConfigurationError):
        asyncio.run(email_service.send_password_reset_email("camille@example.com", "Camille", "ABCD-EFGH", 30))
