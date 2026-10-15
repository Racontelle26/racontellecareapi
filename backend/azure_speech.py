"""Azure AI Speech — traitement vocal France Central uniquement.

La clé reste côté backend. Les réponses détaillées Azure ne sont jamais
persistées : seule la transcription utile est renvoyée au service métier.
"""
from __future__ import annotations

import html
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

import httpx

AZURE_REGION = "francecentral"
STT_URL = (
    "https://francecentral.stt.speech.microsoft.com/"
    "speech/recognition/conversation/cognitiveservices/v1"
    "?language=fr-FR&format=detailed"
)
TTS_URL = "https://francecentral.tts.speech.microsoft.com/cognitiveservices/v1"
TTS_VOICE = "fr-FR-AlainNeural"
TTS_RATE = "-5%"
TTS_OUTPUT_FORMAT = "audio-16khz-128kbitrate-mono-mp3"


class AzureSpeechConfigurationError(RuntimeError):
    """Configuration serveur absente ou incompatible."""


class AzureSpeechUpstreamError(RuntimeError):
    """Réponse Azure non exploitable, sans exposer son contenu sensible."""

    def __init__(self, status_code: int, request_id: str | None = None, retry_after: str | None = None):
        super().__init__(f"Azure Speech HTTP {status_code}")
        self.status_code = status_code
        self.request_id = request_id
        self.retry_after = retry_after


class SpeechNotRecognizedError(ValueError):
    """Le fichier est valide mais aucune parole exploitable n'est reconnue."""


def azure_speech_settings() -> tuple[str, str]:
    key = os.environ.get("AZURE_SPEECH_KEY", "").strip()
    region = os.environ.get("AZURE_SPEECH_REGION", "").strip().lower()
    if not key:
        raise AzureSpeechConfigurationError("AZURE_SPEECH_KEY manquante")
    if region != AZURE_REGION:
        raise AzureSpeechConfigurationError("AZURE_SPEECH_REGION doit être francecentral")
    return key, region


def ensure_azure_speech_ready(require_ffmpeg: bool = True) -> None:
    """Échoue au démarrage Railway plutôt qu'au milieu d'un atelier."""
    azure_speech_settings()
    if require_ffmpeg and not shutil.which("ffmpeg"):
        raise AzureSpeechConfigurationError("ffmpeg est requis pour convertir les enregistrements")


def is_pcm_wav_16khz_mono(data: bytes) -> bool:
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            return (
                audio.getnchannels() == 1
                and audio.getsampwidth() == 2
                and audio.getframerate() == 16000
                and audio.getcomptype() == "NONE"
            )
    except (EOFError, wave.Error):
        return False


def _input_suffix(content_type: str | None, filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".wav", ".m4a", ".mp4", ".aac", ".mp3", ".webm", ".ogg"}:
        return suffix
    base = (content_type or "").split(";", 1)[0].strip().lower()
    return {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/m4a": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/mpeg": ".mp3",
        "audio/webm": ".webm",
        "video/webm": ".webm",
        "audio/ogg": ".ogg",
    }.get(base, ".audio")


def normalize_audio_to_wav(data: bytes, content_type: str | None, filename: str | None) -> bytes:
    """Normalise en PCM signé 16 bits, mono, 16 kHz pour Azure STT."""
    if is_pcm_wav_16khz_mono(data):
        return data
    if not shutil.which("ffmpeg"):
        raise AzureSpeechConfigurationError("ffmpeg indisponible")

    source_path: Path | None = None
    target_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=_input_suffix(content_type, filename), delete=False) as source:
            source.write(data)
            source_path = Path(source.name)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as target:
            target_path = Path(target.name)
        process = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                "-f",
                "wav",
                str(target_path),
            ],
            capture_output=True,
            check=False,
            timeout=45,
        )
        if process.returncode != 0:
            raise ValueError("Fichier audio corrompu ou format non pris en charge")
        wav_data = target_path.read_bytes()
        if not is_pcm_wav_16khz_mono(wav_data):
            raise ValueError("Conversion audio invalide")
        return wav_data
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Conversion audio trop longue") from exc
    finally:
        if source_path:
            source_path.unlink(missing_ok=True)
        if target_path:
            target_path.unlink(missing_ok=True)


def build_ssml(text: str) -> str:
    safe_text = html.escape(text, quote=True)
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='fr-FR'>"
        f"<voice xml:lang='fr-FR' name='{TTS_VOICE}'>"
        f"<prosody rate='{TTS_RATE}'>{safe_text}</prosody>"
        "</voice></speak>"
    )


def tts_cache_key(text: str) -> str:
    """Clé stable du cache existant, variant avec la configuration vocale."""
    payload = f"{text}|azure|{AZURE_REGION}|{TTS_VOICE}|{TTS_RATE}|{TTS_OUTPUT_FORMAT}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    raise AzureSpeechUpstreamError(
        response.status_code,
        request_id=response.headers.get("x-requestid") or response.headers.get("x-request-id"),
        retry_after=response.headers.get("retry-after"),
    )


async def transcribe_wav(wav_data: bytes, client: httpx.AsyncClient | None = None) -> str:
    key, _ = azure_speech_settings()
    timeout = httpx.Timeout(connect=5, read=90, write=30, pool=5)
    owns_client = client is None
    speech_client = client or httpx.AsyncClient(timeout=timeout)
    try:
        try:
            response = await speech_client.post(
                STT_URL,
                headers={
                    "Ocp-Apim-Subscription-Key": key,
                    "Content-Type": "audio/wav",
                    "Accept": "application/json",
                },
                content=wav_data,
            )
        except httpx.TimeoutException as exc:
            raise AzureSpeechUpstreamError(504) from exc
        except httpx.HTTPError as exc:
            raise AzureSpeechUpstreamError(502) from exc
        _raise_for_status(response)
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise AzureSpeechUpstreamError(502, response.headers.get("x-requestid")) from exc
        if payload.get("RecognitionStatus") != "Success":
            raise SpeechNotRecognizedError("Aucune parole n’a été reconnue")
        candidates = payload.get("NBest") or []
        text = ((candidates[0].get("Display") if candidates else None) or payload.get("DisplayText") or "").strip()
        if not text:
            raise SpeechNotRecognizedError("Aucune parole n’a été reconnue")
        return text
    finally:
        if owns_client:
            await speech_client.aclose()


async def synthesize_speech(text: str, client: httpx.AsyncClient | None = None) -> bytes:
    key, _ = azure_speech_settings()
    timeout = httpx.Timeout(connect=5, read=90, write=15, pool=5)
    owns_client = client is None
    speech_client = client or httpx.AsyncClient(timeout=timeout)
    try:
        try:
            response = await speech_client.post(
                TTS_URL,
                headers={
                    "Ocp-Apim-Subscription-Key": key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": TTS_OUTPUT_FORMAT,
                    "User-Agent": "Racontelle-Care/1.0",
                },
                content=build_ssml(text).encode("utf-8"),
            )
        except httpx.TimeoutException as exc:
            raise AzureSpeechUpstreamError(504) from exc
        except httpx.HTTPError as exc:
            raise AzureSpeechUpstreamError(502) from exc
        _raise_for_status(response)
        if not response.content or not response.headers.get("content-type", "").lower().startswith("audio/"):
            raise AzureSpeechUpstreamError(502, response.headers.get("x-requestid"))
        return response.content
    finally:
        if owns_client:
            await speech_client.aclose()
