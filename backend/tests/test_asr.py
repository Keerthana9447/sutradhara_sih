"""Sarvam speech-to-text and text-to-speech provider tests."""
import base64
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import asr  # noqa: E402


class _FakeSpeechToText:
    def __init__(self, transcript="Can I patent this formulation?", error=None):
        self.transcript = transcript
        self.error = error
        self.last_file = None
        self.last_kwargs = None

    def transcribe(self, **kwargs):
        if self.error:
            raise self.error
        self.last_file = kwargs["file"].read()
        self.last_kwargs = kwargs
        return SimpleNamespace(transcript=self.transcript)


class _FakeTextToSpeech:
    def __init__(self, error=None):
        self.error = error
        self.last_kwargs = None

    def convert(self, **kwargs):
        if self.error:
            raise self.error
        self.last_kwargs = kwargs
        return SimpleNamespace(audios=[base64.b64encode(b"RIFF-fake-wav").decode("ascii")])


class _FakeClient:
    def __init__(self, speech_to_text=None, text_to_speech=None):
        self.speech_to_text = speech_to_text or _FakeSpeechToText()
        self.text_to_speech = text_to_speech or _FakeTextToSpeech()


_FAKE_CLIENT = _FakeClient()


def _fake_audio_b64():
    return base64.b64encode(b"not-real-audio-bytes").decode("ascii")


def _enable_fake_sarvam(monkeypatch):
    for key in (
        "BHASHINI_ASR_USER_ID",
        "BHASHINI_ASR_API_KEY",
        "BHASHINI_TTS_USER_ID",
        "BHASHINI_TTS_API_KEY",
        "BHASHINI_USER_ID",
        "BHASHINI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    monkeypatch.setattr(asr, "_SARVAM_AVAILABLE", True)
    monkeypatch.setattr(asr, "SarvamAI", lambda **kwargs: _FAKE_CLIENT)
    _FAKE_CLIENT.speech_to_text.error = None
    _FAKE_CLIENT.text_to_speech.error = None


def test_asr_status_reports_unconfigured_without_sarvam_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert asr.asr_status()["configured"] is False


def test_asr_status_reports_configured_with_sarvam_key(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    status = asr.asr_status()
    assert status["configured"] is True
    assert status["provider"] == "sarvam"


def test_transcribe_via_sarvam_success(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    result = asr._transcribe_via_sarvam(_fake_audio_b64(), "webm")
    assert result == "Can I patent this formulation?"
    assert _FAKE_CLIENT.speech_to_text.last_file == b"not-real-audio-bytes"


def test_transcribe_via_sarvam_passes_correct_language_code(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    asr._transcribe_via_sarvam(_fake_audio_b64(), "webm", source_language="ta")
    assert _FAKE_CLIENT.speech_to_text.last_kwargs["language_code"] == "ta-IN"


def test_transcribe_via_sarvam_sanskrit_uses_real_sanskrit_code_not_hindi(monkeypatch):
    # ASR (Saaras v3) supports Sanskrit natively, unlike TTS (Bulbul) — this
    # must NOT be silently routed to Hindi the way TTS's language map does.
    _enable_fake_sarvam(monkeypatch)
    asr._transcribe_via_sarvam(_fake_audio_b64(), "webm", source_language="sa")
    assert _FAKE_CLIENT.speech_to_text.last_kwargs["language_code"] == "sa-IN"


def test_transcribe_fails_safe_on_sarvam_error(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    _FAKE_CLIENT.speech_to_text.error = ConnectionError("service unavailable")
    assert asr._transcribe_via_sarvam(_fake_audio_b64(), "wav") is None


def test_public_transcribe_success(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    text, ok = asr.transcribe(_fake_audio_b64(), "en")
    assert ok is True
    assert text == "Can I patent this formulation?"


def test_public_transcribe_supports_sanskrit(monkeypatch):
    # Was previously hard-rejected before even trying a provider — Sanskrit
    # is one of this app's six supported languages and Saaras v3 supports
    # it natively, so it must not be excluded from SUPPORTED_ASR_LANGUAGES.
    _enable_fake_sarvam(monkeypatch)
    text, ok = asr.transcribe(_fake_audio_b64(), "sa")
    assert ok is True
    assert _FAKE_CLIENT.speech_to_text.last_kwargs["language_code"] == "sa-IN"


@pytest.mark.parametrize(
    ("language", "language_code"),
    [
        ("en", "en-IN"),
        ("hi", "hi-IN"),
        ("te", "te-IN"),
        ("ta", "ta-IN"),
        ("ml", "ml-IN"),
        ("sa", "sa-IN"),
    ],
)
def test_public_transcribe_passes_language_to_sarvam(monkeypatch, language, language_code):
    _enable_fake_sarvam(monkeypatch)
    text, ok = asr.transcribe(_fake_audio_b64(), language)
    assert ok is True
    assert text == "Can I patent this formulation?"
    assert _FAKE_CLIENT.speech_to_text.last_kwargs["language_code"] == language_code


def test_all_six_supported_languages_are_asr_enabled():
    assert set(asr.SUPPORTED_ASR_LANGUAGES) == {"en", "hi", "te", "ta", "ml", "sa"}


@pytest.mark.parametrize(
    ("language", "language_code"),
    [
        ("en", "en-IN"),
        ("hi", "hi-IN"),
        ("te", "te-IN"),
        ("ta", "ta-IN"),
        ("ml", "ml-IN"),
        ("sa", "hi-IN"),
    ],
)
def test_synthesize_passes_supported_language_to_sarvam(monkeypatch, language, language_code):
    _enable_fake_sarvam(monkeypatch)
    audio = asr.synthesize("Hello", language)
    assert audio == base64.b64encode(b"RIFF-fake-wav").decode("ascii")
    assert _FAKE_CLIENT.text_to_speech.last_kwargs["language_code"] == language_code


def test_synthesize_success(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    audio = asr.synthesize("Hello", "te")
    assert audio == base64.b64encode(b"RIFF-fake-wav").decode("ascii")
    assert _FAKE_CLIENT.text_to_speech.last_kwargs["model"] == "bulbul:v3"
    assert _FAKE_CLIENT.text_to_speech.last_kwargs["language_code"] == "te-IN"


def test_synthesize_sanskrit_routes_to_hindi_voice_since_bulbul_lacks_sanskrit(monkeypatch):
    # Bulbul v3 (TTS) does NOT support Sanskrit (confirmed against Sarvam's
    # own docs: 10 Indian languages, Sanskrit not among them) — unlike ASR,
    # this one SHOULD fall back to the closest available voice (Hindi).
    _enable_fake_sarvam(monkeypatch)
    asr.synthesize("नमस्ते", "sa")
    assert _FAKE_CLIENT.text_to_speech.last_kwargs["language_code"] == "hi-IN"


def test_public_transcribe_rejects_unsupported_language():
    text, ok = asr.transcribe(_fake_audio_b64(), "fr")
    assert ok is False
    assert "isn't supported" in text.lower()


def test_public_transcribe_rejects_empty_audio():
    text, ok = asr.transcribe("", "en")
    assert ok is False
    assert "no audio" in text.lower()
