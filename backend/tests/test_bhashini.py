"""
Bhashini (ULCA) provider tests.

This sandbox's network egress does not include meity-auth.ulcacontrib.org
(same restriction that keeps the BGE/fastembed dense-retrieval backend on
its TF-IDF fallback — see retrieval.py), so the two-step ULCA HTTP flow is
exercised here against a mocked httpx.Client rather than the live service.
This proves the request/response wiring is correct; it does not prove the
live Bhashini service is reachable or that its current API shape matches
this mock exactly — re-run test_live_bhashini_path manually with real
credentials in a network-open environment before a demo.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from app import translate  # noqa: E402


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeClient:
    """Mimics httpx.Client's context-manager + .post() interface for the
    two-step ULCA flow: first call returns pipeline config, second call
    returns the translated text."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None):
        if url == translate._BHASHINI_PIPELINE_CONFIG_URL:
            return _FakeResponse({
                "pipelineResponseConfig": [{"config": [{"serviceId": "fake-mt-service"}]}],
                "pipelineInferenceAPIEndPoint": {
                    "callbackUrl": "https://fake-inference.example/translate",
                    "inferenceApiKey": {"name": "Authorization", "value": "fake-token"},
                },
            })
        # inference call
        source_text = json["inputData"]["input"][0]["source"]
        return _FakeResponse({
            "pipelineResponse": [{"output": [{"source": source_text, "target": f"[te]{source_text}"}]}],
        })


def test_bhashini_status_reports_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    status = translate.bhashini_status()
    assert status["configured"] is False


def test_bhashini_status_reports_configured_when_credentials_set(monkeypatch):
    monkeypatch.setenv("BHASHINI_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_API_KEY", "test-key")
    status = translate.bhashini_status()
    assert status["configured"] is True


def test_bhashini_translate_one_success_with_mocked_http(monkeypatch):
    monkeypatch.setenv("BHASHINI_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_API_KEY", "test-key")
    monkeypatch.setattr(translate, "_HTTPX_AVAILABLE", True)
    monkeypatch.setattr(translate.httpx, "Client", _FakeClient)

    result = translate._bhashini_translate_one("Can I patent this?", "en", "te")
    assert result == "[te]Can I patent this?"


def test_bhashini_translate_one_returns_none_without_credentials(monkeypatch):
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    result = translate._bhashini_translate_one("text", "en", "te")
    assert result is None


def test_bhashini_translate_one_fails_safe_on_http_error(monkeypatch):
    monkeypatch.setenv("BHASHINI_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_API_KEY", "test-key")
    monkeypatch.setattr(translate, "_HTTPX_AVAILABLE", True)

    class _BrokenClient(_FakeClient):
        def post(self, url, headers=None, json=None):
            raise ConnectionError("no route to host (expected in this sandbox)")

    monkeypatch.setattr(translate.httpx, "Client", _BrokenClient)
    result = translate._bhashini_translate_one("text", "en", "te")
    assert result is None  # must fail safe, never raise


def test_provider_chain_prefers_bhashini_when_configured(monkeypatch):
    """End-to-end: with Bhashini configured and mocked, translate_text()
    should return the Bhashini-shaped output rather than falling through to
    Google/MyMemory."""
    monkeypatch.setenv("BHASHINI_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_API_KEY", "test-key")
    monkeypatch.setattr(translate, "_HTTPX_AVAILABLE", True)
    monkeypatch.setattr(translate.httpx, "Client", _FakeClient)
    translate._CACHE.clear()

    text, ok = translate.translate_text("Can I patent this?", "te")
    assert ok is True
    assert text == "[te]Can I patent this?"


def test_live_bhashini_path():
    """Best-effort live check — skipped unless real credentials are present
    in the environment (never the case in CI/this sandbox)."""
    if not translate.bhashini_status()["configured"]:
        pytest.skip("BHASHINI_USER_ID / BHASHINI_API_KEY not set in this environment")
    result = translate._bhashini_translate_one("Can I patent a classical Ayurvedic formulation?", "en", "hi")
    if result is None:
        pytest.skip("Bhashini service unreachable from this environment")
    assert result.strip()
