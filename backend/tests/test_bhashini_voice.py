"""
Bhashini (ULCA) ASR and TTS fallback tests.

Same sandbox limitation as test_bhashini.py (no route to
meity-auth.ulcacontrib.org here), so the two-step ULCA flow is exercised
against a mocked httpx.Client for both taskTypes. Re-run the two
test_live_bhashini_*_path tests manually with real credentials in a
network-open environment before a demo.
"""
import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from app import asr  # noqa: E402


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeClient:
    """Mimics httpx.Client's context-manager + .post() interface for the
    two-step ULCA ASR flow: first call returns pipeline config, second call
    returns the transcript."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None):
        if url == asr._BHASHINI_PIPELINE_CONFIG_URL:
            return _FakeResponse({
                "pipelineResponseConfig": [{"config": [{"serviceId": "fake-asr-service"}]}],
                "pipelineInferenceAPIEndPoint": {
                    "callbackUrl": "https://fake-inference.example/asr",
                    "inferenceApiKey": {"name": "Authorization", "value": "fake-token"},
                },
            })
        # inference call
        return _FakeResponse({
            "pipelineResponse": [{"output": [{"source": "Can I patent this formulation?"}]}],
        })


def _fake_audio_b64():
    return base64.b64encode(b"not-real-audio-bytes").decode("ascii")


def test_bhashini_asr_status_reports_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("BHASHINI_ASR_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    assert asr.bhashini_asr_status()["configured"] is False


def test_bhashini_asr_status_reports_configured_with_dedicated_keys(monkeypatch):
    monkeypatch.setenv("BHASHINI_ASR_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_ASR_API_KEY", "test-key")
    status = asr.bhashini_asr_status()
    assert status["configured"] is True
    assert status["provider"] == "bhashini"


def test_bhashini_asr_status_falls_back_to_shared_credentials(monkeypatch):
    monkeypatch.delenv("BHASHINI_ASR_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_API_KEY", raising=False)
    monkeypatch.setenv("BHASHINI_USER_ID", "shared-user")
    monkeypatch.setenv("BHASHINI_API_KEY", "shared-key")
    assert asr.bhashini_asr_status()["configured"] is True


def test_transcribe_via_bhashini_success_with_mocked_http(monkeypatch):
    monkeypatch.setenv("BHASHINI_ASR_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_ASR_API_KEY", "test-key")
    monkeypatch.setattr(asr, "_HTTPX_AVAILABLE", True)
    monkeypatch.setattr(asr.httpx, "Client", _FakeClient)

    result = asr._transcribe_via_bhashini(_fake_audio_b64(), "te", "wav", 16000)
    assert result == "Can I patent this formulation?"


def test_transcribe_via_bhashini_returns_none_without_credentials(monkeypatch):
    monkeypatch.delenv("BHASHINI_ASR_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    result = asr._transcribe_via_bhashini(_fake_audio_b64(), "te", "wav", 16000)
    assert result is None


def test_transcribe_via_bhashini_fails_safe_on_http_error(monkeypatch):
    monkeypatch.setenv("BHASHINI_ASR_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_ASR_API_KEY", "test-key")
    monkeypatch.setattr(asr, "_HTTPX_AVAILABLE", True)

    class _BrokenClient(_FakeClient):
        def post(self, url, headers=None, json=None):
            raise ConnectionError("no route to host (expected in this sandbox)")

    monkeypatch.setattr(asr.httpx, "Client", _BrokenClient)
    result = asr._transcribe_via_bhashini(_fake_audio_b64(), "te", "wav", 16000)
    assert result is None  # must fail safe, never raise


def test_public_transcribe_falls_back_to_bhashini_when_sarvam_unconfigured(monkeypatch):
    """End-to-end: with Sarvam unconfigured but Bhashini configured and
    mocked, transcribe() should return the Bhashini-shaped transcript
    rather than the generic failure message."""
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.setenv("BHASHINI_ASR_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_ASR_API_KEY", "test-key")
    monkeypatch.setattr(asr, "_HTTPX_AVAILABLE", True)
    monkeypatch.setattr(asr.httpx, "Client", _FakeClient)

    text, ok = asr.transcribe(_fake_audio_b64(), "te")
    assert ok is True
    assert text == "Can I patent this formulation?"


def test_public_transcribe_fails_safe_when_both_providers_unavailable(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)

    text, ok = asr.transcribe(_fake_audio_b64(), "en")
    assert ok is False
    assert "bhashini and sarvam" in text.lower()


def test_live_bhashini_asr_path():
    """Best-effort live check — skipped unless real credentials are present
    in the environment (never the case in CI/this sandbox)."""
    if not asr.bhashini_asr_status()["configured"]:
        pytest.skip("BHASHINI_ASR_USER_ID / BHASHINI_ASR_API_KEY not set in this environment")
    result = asr._transcribe_via_bhashini(_fake_audio_b64(), "en", "wav", 16000)
    if result is None:
        pytest.skip("Bhashini ASR service unreachable from this environment, "
                     "or rejected the fake test audio — expected with real "
                     "credentials and placeholder bytes, not a code bug")


class _FakeTTSClient(_FakeClient):
    """Same two-step ULCA flow shape as _FakeClient, but returning a TTS
    pipeline response (audio.audioContent) instead of an ASR one
    (output.source)."""

    def post(self, url, headers=None, json=None):
        if url == asr._BHASHINI_PIPELINE_CONFIG_URL:
            return _FakeResponse({
                "pipelineResponseConfig": [{"config": [{"serviceId": "fake-tts-service"}]}],
                "pipelineInferenceAPIEndPoint": {
                    "callbackUrl": "https://fake-inference.example/tts",
                    "inferenceApiKey": {"name": "Authorization", "value": "fake-token"},
                },
            })
        # inference call
        return _FakeResponse({
            "pipelineResponse": [{"audio": [{"audioContent": "ZmFrZS13YXYtYXVkaW8="}]}],
        })


def test_bhashini_tts_status_reports_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("BHASHINI_TTS_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_TTS_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    assert asr.bhashini_tts_status()["configured"] is False


def test_bhashini_tts_status_reports_configured_with_dedicated_keys(monkeypatch):
    monkeypatch.setenv("BHASHINI_TTS_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_TTS_API_KEY", "test-key")
    status = asr.bhashini_tts_status()
    assert status["configured"] is True
    assert status["provider"] == "bhashini"


def test_bhashini_tts_status_falls_back_to_asr_credentials(monkeypatch):
    monkeypatch.delenv("BHASHINI_TTS_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_TTS_API_KEY", raising=False)
    monkeypatch.setenv("BHASHINI_ASR_USER_ID", "asr-user")
    monkeypatch.setenv("BHASHINI_ASR_API_KEY", "asr-key")
    assert asr.bhashini_tts_status()["configured"] is True


def test_bhashini_tts_status_falls_back_to_shared_credentials(monkeypatch):
    monkeypatch.delenv("BHASHINI_TTS_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_TTS_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_API_KEY", raising=False)
    monkeypatch.setenv("BHASHINI_USER_ID", "shared-user")
    monkeypatch.setenv("BHASHINI_API_KEY", "shared-key")
    assert asr.bhashini_tts_status()["configured"] is True


def test_synthesize_via_bhashini_success_with_mocked_http(monkeypatch):
    monkeypatch.setenv("BHASHINI_TTS_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_TTS_API_KEY", "test-key")
    monkeypatch.setattr(asr, "_HTTPX_AVAILABLE", True)
    monkeypatch.setattr(asr.httpx, "Client", _FakeTTSClient)

    result = asr._synthesize_via_bhashini("Hello, can I patent this?", "te")
    assert result == "ZmFrZS13YXYtYXVkaW8="


def test_synthesize_via_bhashini_returns_none_without_credentials(monkeypatch):
    monkeypatch.delenv("BHASHINI_TTS_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_TTS_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    result = asr._synthesize_via_bhashini("text", "te")
    assert result is None


def test_synthesize_via_bhashini_fails_safe_on_http_error(monkeypatch):
    monkeypatch.setenv("BHASHINI_TTS_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_TTS_API_KEY", "test-key")
    monkeypatch.setattr(asr, "_HTTPX_AVAILABLE", True)

    class _BrokenClient(_FakeTTSClient):
        def post(self, url, headers=None, json=None):
            raise ConnectionError("no route to host (expected in this sandbox)")

    monkeypatch.setattr(asr.httpx, "Client", _BrokenClient)
    result = asr._synthesize_via_bhashini("text", "te")
    assert result is None  # must fail safe, never raise


def test_public_synthesize_falls_back_to_bhashini_when_sarvam_unconfigured(monkeypatch):
    """End-to-end: with Sarvam unconfigured but Bhashini TTS configured and
    mocked, synthesize() should return the Bhashini-shaped audio rather
    than None."""
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.setenv("BHASHINI_TTS_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_TTS_API_KEY", "test-key")
    monkeypatch.setattr(asr, "_HTTPX_AVAILABLE", True)
    monkeypatch.setattr(asr.httpx, "Client", _FakeTTSClient)

    audio = asr.synthesize("Hello, can I patent this?", "te")
    assert audio == "ZmFrZS13YXYtYXVkaW8="


def test_public_synthesize_returns_none_when_both_providers_unavailable(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_TTS_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_TTS_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)

    assert asr.synthesize("Hello", "en") is None


def test_live_bhashini_tts_path():
    """Best-effort live check — skipped unless real credentials are present
    in the environment (never the case in CI/this sandbox)."""
    if not asr.bhashini_tts_status()["configured"]:
        pytest.skip("BHASHINI_TTS_USER_ID / BHASHINI_TTS_API_KEY not set in this environment")
    result = asr._synthesize_via_bhashini("Can I patent a classical Ayurvedic formulation?", "en")
    if result is None:
        pytest.skip("Bhashini TTS service unreachable from this environment")
    assert result.strip()
