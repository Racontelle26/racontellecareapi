import asyncio
import inspect
import shutil
import wave
from pathlib import Path

import pytest
import httpx

import server


def test_azure_endpoint_headers_and_detailed_parser(monkeypatch):
    monkeypatch.setattr(server, "AZURE_SPEECH_KEY", "test-key")
    assert server.AZURE_STT_URL == (
        "https://francecentral.stt.speech.microsoft.com/"
        "speech/recognition/conversation/cognitiveservices/v1?language=fr-FR&format=detailed"
    )
    assert server.azure_stt_headers() == {
        "Ocp-Apim-Subscription-Key": "test-key",
        "Content-Type": "audio/wav",
        "Accept": "application/json",
    }
    assert server.parse_azure_stt_response({
        "RecognitionStatus": "Success",
        "NBest": [{"Display": "Bonjour la famille."}],
    }) == "Bonjour la famille."
    assert server.parse_azure_stt_response({"RecognitionStatus": "NoMatch"}) == ""


@pytest.mark.parametrize(("error", "expected"), [
    (RuntimeError("Authentification Azure Speech refusée"), "azure_auth"),
    (RuntimeError("Azure Speech temporairement limité"), "azure_rate_limit"),
    (RuntimeError("Azure Speech indisponible"), "azure_service"),
    (RuntimeError("Azure Speech a rejeté l’audio"), "audio_rejected"),
    (RuntimeError("Réponse Azure Speech invalide"), "azure_invalid_response"),
    (RuntimeError("FFmpeg indisponible"), "audio_conversion"),
    (httpx.ReadTimeout("timeout"), "azure_network"),
    (RuntimeError("autre"), "unknown"),
])
def test_safe_azure_error_codes(error, expected):
    assert server.azure_transcription_error_code(error) == expected


def test_no_openai_or_tts_runtime_calls_remain():
    source = inspect.getsource(server).lower()
    for forbidden in ("whisper-1", "asyncopenai", "openaispeechtotext", "text_to_speech", "speech_synthesis"):
        assert forbidden not in source


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is installed by the production Dockerfile")
def test_ffmpeg_conversion_is_pcm16_16khz_mono_and_segmented(tmp_path):
    source = tmp_path / "source.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        silence = b"\x00\x00" * 16000
        for _ in range(56):
            wav.writeframes(silence)

    output = tmp_path / "chunks"
    output.mkdir()
    chunks = asyncio.run(server._convert_to_wav_chunks(str(source), str(output)))
    assert len(chunks) == 2
    for chunk in chunks:
        with wave.open(str(chunk), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == 16000


def test_dockerfile_installs_ffmpeg_and_prod_drops_openai():
    backend = Path(__file__).parents[1]
    dockerfile = (backend / "Dockerfile").read_text()
    requirements = (backend / "requirements-prod.txt").read_text().lower()
    assert "apt-get install -y --no-install-recommends ffmpeg" in dockerfile
    assert "openai" not in requirements