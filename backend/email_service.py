from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from email.utils import parseaddr
import ipaddress
import logging
import os
import re
from urllib.parse import urlencode, urlparse

from dotenv import load_dotenv
import httpx

load_dotenv()
logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "").strip()
PASSWORD_RESET_URL = os.environ.get("PASSWORD_RESET_URL", "").rstrip("/")
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CREDENTIAL_ASKS = ("reply with your password", "reply with the code", "send your password", "seed phrase", "recovery phrase")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


class EmailConfigurationError(RuntimeError):
    pass


class EmailDeliveryError(RuntimeError):
    pass


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: set[str] = set()
        self.urls: list[str] = []
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [value for key, value in attrs if key.lower() in ("href", "src") and value]
        if tag.lower() == "a":
            self._href = dict((key.lower(), value) for key, value in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return not any(host == item or host.endswith(f".{item}") for item in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith(f".{shown}") or shown.endswith(f".{real}")


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("Les formulaires sont interdits dans les emails")
    content = f"{subject}\n{html}".lower()
    if any(phrase in content for phrase in _CREDENTIAL_ASKS):
        raise ValueError("L'email ne doit jamais demander un secret au destinataire")
    for raw_url in scan.urls:
        value = raw_url.strip().lower()
        if value.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        parsed = urlparse(value)
        if parsed.scheme != "https" or not _host_ok(parsed.hostname or "") or parsed.username:
            raise ValueError("Chaque lien email doit être une URL HTTPS sûre")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        for match in _HOSTISH.finditer(text):
            if not _same_site(match.group(1).lower(), real):
                raise ValueError("Le libellé d'un lien ne correspond pas à sa destination")


def email_configured() -> bool:
    _, address = parseaddr(RESEND_FROM_EMAIL)
    reset_target = urlparse(PASSWORD_RESET_URL)
    return bool(
        RESEND_API_KEY.startswith("re_")
        and address.lower() == "no-reply@racontellecare.com"
        and reset_target.scheme == "https"
        and _host_ok(reset_target.hostname or "")
        and reset_target.username is None
    )


def _sender() -> str:
    display_name, address = parseaddr(RESEND_FROM_EMAIL)
    return RESEND_FROM_EMAIL if display_name else f"Racontelle Care <{address}>"


def build_password_reset_email(full_name: str, email: str, code: str, minutes: int) -> tuple[str, str]:
    query = urlencode({"reset_email": email, "reset_code": code})
    reset_link = f"{PASSWORD_RESET_URL}/?{query}"
    subject = "Racontelle Care — réinitialisez votre mot de passe"
    safe_name, safe_code = escape(full_name), escape(code)
    html = f"""
    <table role="presentation" width="100%" style="background:#f7f3ee;padding:24px">
      <tr><td align="center"><table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border-radius:18px;padding:28px;font-family:Arial,sans-serif;color:#2f3e52">
        <tr><td><h1 style="font-size:25px;margin:0 0 18px">Racontelle Care</h1>
        <p>Bonjour {safe_name},</p>
        <p>Une demande de nouveau mot de passe a été faite pour votre compte.</p>
        <p style="text-align:center;margin:28px 0"><a href="{reset_link}" style="background:#2f3e52;color:#ffffff;padding:14px 20px;border-radius:12px;text-decoration:none;font-weight:bold">Choisir un nouveau mot de passe</a></p>
        <p>Vous pouvez aussi saisir ce code dans l’application :</p>
        <p style="font-size:24px;letter-spacing:4px;font-weight:bold;text-align:center">{safe_code}</p>
        <p>Le lien et le code expirent dans {minutes} minutes et ne fonctionnent qu’une seule fois.</p>
        <p>Si vous n’avez pas fait cette demande, ignorez ce message : votre mot de passe actuel reste valable.</p>
        <p style="font-size:12px;color:#7c8698;margin-top:28px">Envoyé par Racontelle Care. Nous ne vous demanderons jamais votre mot de passe par email.</p></td></tr>
      </table></td></tr>
    </table>"""
    _assert_safe_email(subject, html)
    return subject, html


async def send_password_reset_email(to: str, full_name: str, code: str, minutes: int) -> str:
    if not email_configured():
        raise EmailConfigurationError("Service email Racontelle Care non configuré")
    try:
        subject, html = build_password_reset_email(full_name, to, code, minutes)
    except ValueError as exc:
        raise EmailConfigurationError("Modèle email Racontelle Care invalide") from exc
    payload = {"from": _sender(), "to": [to], "subject": subject, "html": html}
    try:
        timeout = httpx.Timeout(10, connect=3)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
        response.raise_for_status()
        email_id = response.json().get("id")
        if not email_id:
            raise EmailDeliveryError("Réponse email sans identifiant")
        return str(email_id)
    except (httpx.HTTPError, ValueError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", "indisponible")
        logger.warning("Envoi email Racontelle Care refusé (statut=%s)", status)
        raise EmailDeliveryError("Envoi de l'email impossible") from exc
