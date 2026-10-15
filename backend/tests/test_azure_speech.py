import asyncio
import io
import math
from pathlib import Path
import struct
import sys
import wave

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from azure_speech import (
    STT_URL,
    TTS_OUTPUT_FORMAT,
    TTS_URL,
    TTS_VOICE,
    AzureSpeechConfigurationError,
    AzureSpeechUpstreamError,
    SpeechNotRecognizedError,
    azure_speech_settings,
    build_ssml,
    is_pcm_wav_16khz_mono,
    normalize_audio_to_wav,
    synthesize_speech,
    tts_cache_key,
    transcribe_wav,
)


@pytest.fixture(scope="session", autouse=True)
def authenticated_requests():
    """Ces tests n'appellent ni l'API publique ni une base Railway."""
    yield


def make_wav(rate: int = 16000, channels: int = 1, duration: float = 0.15) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        for frame in range(int(rate * duration)):
            sample = int(9000 * math.sin(2 * math.pi * 440 * frame / rate))
            packed = struct.pack("<h", sample)
            audio.writeframesraw(packed * channels)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def azure_env(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key-never-sent-outside-mock")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "francecentral")


def test_configuration_requires_francecentral(monkeypatch):
    assert azure_speech_settings()[1] == "francecentral"
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    with pytest.raises(AzureSpeechConfigurationError):
        azure_speech_settings()


def test_ssml_uses_alain_voice_slow_rate_and_escapes_text():
    ssml = build_ssml("Jeanne & Paul <souvenir> 'heureux'")
    assert f"name='{TTS_VOICE}'" in ssml
    assert "rate='-5%'" in ssml
    assert "Jeanne &amp; Paul &lt;souvenir&gt; &#x27;heureux&#x27;" in ssml
    assert "<souvenir>" not in ssml


def test_tts_cache_key_is_stable_and_provider_specific():
    first = tts_cache_key("Bonjour Madame")
    assert first == tts_cache_key("Bonjour Madame")
    assert first != tts_cache_key("Bonjour Monsieur")
    assert len(first) == 64


def test_valid_pcm_wav_is_kept_byte_for_byte():
    wav = make_wav()
    assert is_pcm_wav_16khz_mono(wav)
    assert normalize_audio_to_wav(wav, "audio/wav", "recording.wav") == wav


def test_nonconforming_wav_is_transcoded_to_azure_contract():
    stereo_44k = make_wav(rate=44100, channels=2)
    normalized = normalize_audio_to_wav(stereo_44k, "audio/wav", "recording.wav")
    assert is_pcm_wav_16khz_mono(normalized)


def test_stt_sends_exact_url_headers_and_raw_wav_body():
    wav = make_wav()

    def handler(request: httpx.Request):
        assert str(request.url) == STT_URL
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-key-never-sent-outside-mock"
        assert request.headers["Content-Type"] == "audio/wav"
        assert request.content == wav
        return httpx.Response(
            200,
            json={"RecognitionStatus": "Success", "NBest": [{"Display": "Un souvenir heureux."}]},
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await transcribe_wav(wav, client)

    assert asyncio.run(run()) == "Un souvenir heureux."


def test_stt_rejects_no_match_without_persisting_provider_payload():
    async def run():
        transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json={"RecognitionStatus": "NoMatch", "NBest": []})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            return await transcribe_wav(make_wav(), client)

    with pytest.raises(SpeechNotRecognizedError):
        asyncio.run(run())


def test_tts_sends_exact_azure_contract_and_returns_mp3():
    mp3 = b"ID3" + b"\x00" * 800

    def handler(request: httpx.Request):
        assert str(request.url) == TTS_URL
        assert request.headers["Content-Type"] == "application/ssml+xml"
        assert request.headers["X-Microsoft-OutputFormat"] == TTS_OUTPUT_FORMAT
        body = request.content.decode("utf-8")
        assert "fr-FR-AlainNeural" in body
        assert "rate='-5%'" in body
        return httpx.Response(200, content=mp3, headers={"Content-Type": "audio/mpeg"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await synthesize_speech("Racontez-moi votre enfance.", client)

    assert asyncio.run(run()) == mp3


def test_azure_429_is_sanitized_and_keeps_retry_after():
    async def run():
        transport = httpx.MockTransport(
            lambda _: httpx.Response(429, headers={"Retry-After": "12", "x-requestid": "safe-id"})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            return await synthesize_speech("Bonjour", client)

    with pytest.raises(AzureSpeechUpstreamError) as error:
        asyncio.run(run())
    assert error.value.status_code == 429
    assert error.value.retry_after == "12"
    assert error.value.request_id == "safe-id"
