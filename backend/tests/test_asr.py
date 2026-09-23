"""Sarvam speech-to-text and text-to-speech provider tests."""
import base64
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import asr  # noqa: E402


class _FakeSpeechToText:
    def __init__(self, transcript="Can I patent this formulation?", error=None):
        self.transcript = transcript
        self.error = error
        self.last_file = None

    def transcribe(self, **kwargs):
        if self.error:
            raise self.error
        self.last_file = kwargs["file"].read()
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


def test_transcribe_fails_safe_on_sarvam_error(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    _FAKE_CLIENT.speech_to_text.error = ConnectionError("service unavailable")
    assert asr._transcribe_via_sarvam(_fake_audio_b64(), "wav") is None


def test_public_transcribe_success(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    text, ok = asr.transcribe(_fake_audio_b64(), "en")
    assert ok is True
    assert text == "Can I patent this formulation?"


def test_synthesize_success(monkeypatch):
    _enable_fake_sarvam(monkeypatch)
    audio = asr.synthesize("Hello", "te")
    assert audio == base64.b64encode(b"RIFF-fake-wav").decode("ascii")
    assert _FAKE_CLIENT.text_to_speech.last_kwargs["model"] == "bulbul:v3"
    assert _FAKE_CLIENT.text_to_speech.last_kwargs["language_code"] == "te-IN"


def test_public_transcribe_rejects_unsupported_language():
    text, ok = asr.transcribe(_fake_audio_b64(), "fr")
    assert ok is False
    assert "isn't supported" in text.lower()


def test_public_transcribe_rejects_empty_audio():
    text, ok = asr.transcribe("", "en")
    assert ok is False
    assert "no audio" in text.lower()
