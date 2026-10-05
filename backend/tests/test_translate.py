"""
Tests for translate.py's provider chain (Bhashini primary, Sarvam fallback,
Google/MyMemory further fallback) across all six of this app's supported
languages: en, hi, sa, te, ta, ml.
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import translate  # noqa: E402
from app import asr  # noqa: E402
from app import language  # noqa: E402
from app.main import translate_batch  # noqa: E402
from app.schemas import TranslateBatchRequest  # noqa: E402
from pydantic import ValidationError  # noqa: E402

ALL_SIX_LANGUAGES = {"en", "hi", "sa", "te", "ta", "ml"}


# ---------------------------------------------------------------------------
# Cross-module consistency: the app only ever detects/requests these six
# languages (see language.py), so every provider-facing map in translate.py
# and asr.py must actually cover all six -- a silently missing entry is
# exactly the bug this test file exists to catch (see asr.py's previous
# SUPPORTED_ASR_LANGUAGES gap, which excluded Sanskrit entirely).
# ---------------------------------------------------------------------------
def test_translate_lang_map_covers_all_six_languages():
    assert ALL_SIX_LANGUAGES <= set(translate._LANG_MAP.keys())


def test_mymemory_lang_map_covers_all_six_languages():
    assert ALL_SIX_LANGUAGES <= set(translate._MYMEMORY_LANG_MAP.keys())


def test_sarvam_translate_lang_map_covers_all_six_languages():
    assert ALL_SIX_LANGUAGES <= set(translate._SARVAM_LANG_MAP.keys())


def test_asr_supported_languages_matches_all_six():
    assert set(asr.SUPPORTED_ASR_LANGUAGES) == ALL_SIX_LANGUAGES


def test_asr_tts_and_asr_language_code_maps_cover_all_six():
    assert ALL_SIX_LANGUAGES <= set(asr._LANGUAGE_CODES.keys())
    assert ALL_SIX_LANGUAGES <= set(asr._SARVAM_ASR_LANGUAGE_CODES.keys())


def test_language_detection_covers_all_six_languages():
    # Sanity: language.py can actually round-trip each of the six codes
    # translate.py/asr.py need to receive.
    samples = {
        "en": "Can I patent this formulation?",
        "hi": "क्या मैं इस फॉर्मूलेशन का पेटेंट करा सकता हूँ?",
        "te": "నేను ఈ ఫార్ములేషన్‌ను పేటెంట్ చేయగలనా?",
        "ta": "இந்த சூத்திரத்தை நான் காப்புரிமை பெறலாமா?",
        "ml": "എനിക്ക് ഈ ഫോർമുലേഷൻ പേറ്റന്റ് ചെയ്യാമോ?",
        "sa": "अस्ति किं एतत् पेटेंट कर्तुं शक्नोमि",
    }
    for expected_lang, text in samples.items():
        assert language.detect_language(text) == expected_lang


# ---------------------------------------------------------------------------
# Bhashini-first, Sarvam-fallback ordering — the actual behavior the
# problem statement asks for ("leveraging national language infrastructure
# such as Bhashini"), verified per-language rather than assumed from one
# happy-path check.
# ---------------------------------------------------------------------------
class _FakeHttpxResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def _bhashini_config_response():
    return _FakeHttpxResponse({
        "pipelineInferenceAPIEndPoint": {
            "callbackUrl": "https://fake-bhashini-inference/translate",
            "inferenceApiKey": {"name": "Authorization", "value": "fake-inference-key"},
        },
        "pipelineResponseConfig": [{"config": [{"serviceId": "fake-nmt-service"}]}],
    })


def _bhashini_inference_response(translated_text):
    return _FakeHttpxResponse({
        "pipelineResponse": [{"output": [{"target": translated_text}]}]
    })


class _FakeHttpxClient:
    """Mimics httpx.Client as a context manager, returning the config
    response first and the inference response second -- same two-call
    shape _bhashini_translate_one actually makes."""

    def __init__(self, translated_text="अनुवादित पाठ", fail=False):
        self.translated_text = translated_text
        self.fail = fail
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, headers=None, json=None):
        self.calls += 1
        if self.fail:
            raise ConnectionError("Bhashini unreachable")
        if self.calls == 1:
            return _bhashini_config_response()
        return _bhashini_inference_response(self.translated_text)


def _enable_bhashini(monkeypatch, fail=False, translated_text="अनुवादित पाठ"):
    monkeypatch.setenv("BHASHINI_NMT_USER_ID", "test-user")
    monkeypatch.setenv("BHASHINI_NMT_API_KEY", "test-key")
    monkeypatch.setattr(translate, "_HTTPX_AVAILABLE", True)
    fake_client = _FakeHttpxClient(translated_text=translated_text, fail=fail)
    fake_httpx_module = SimpleNamespace(Client=lambda timeout=None: fake_client)
    monkeypatch.setattr(translate, "httpx", fake_httpx_module)
    return fake_client


def _clear_all_providers(monkeypatch):
    for key in ("BHASHINI_NMT_USER_ID", "BHASHINI_NMT_API_KEY", "BHASHINI_USER_ID",
                "BHASHINI_API_KEY", "SARVAM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(translate, "_AVAILABLE", False)  # disable Google/MyMemory too


def test_bhashini_status_reports_configured(monkeypatch):
    _enable_bhashini(monkeypatch)
    assert translate.bhashini_status()["configured"] is True


def test_bhashini_status_reports_unconfigured(monkeypatch):
    _clear_all_providers(monkeypatch)
    assert translate.bhashini_status()["configured"] is False


def test_bhashini_tried_as_primary_for_every_language(monkeypatch):
    for lang in ("hi", "te", "ta", "ml", "sa"):
        translate._CACHE.clear()
        fake_client = _enable_bhashini(monkeypatch, translated_text=f"translated-{lang}")
        text, ok = translate.translate_text("Some grounded English answer text.", lang)
        assert ok is True, f"failed for {lang}"
        assert text == f"translated-{lang}", f"failed for {lang}"
        assert fake_client.calls == 2, f"Bhashini wasn't actually called for {lang}"


def test_falls_back_to_sarvam_when_bhashini_fails(monkeypatch):
    translate._CACHE.clear()
    _enable_bhashini(monkeypatch, fail=True)
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    monkeypatch.setattr(translate, "_SARVAM_AVAILABLE", True)

    class _FakeSarvamTranslateClient:
        def __init__(self, **kwargs):
            self.text = SimpleNamespace(translate=self._translate)

        def _translate(self, **kwargs):
            return SimpleNamespace(translated_text="sarvam-fallback-translation")

    monkeypatch.setattr(translate, "SarvamAI", _FakeSarvamTranslateClient)
    monkeypatch.setattr(translate, "_AVAILABLE", False)  # force past Bhashini+Sarvam only

    text, ok = translate.translate_text("Some grounded English answer text.", "te")
    assert ok is True
    assert text == "sarvam-fallback-translation"


def test_returns_original_text_with_ok_false_when_everything_fails(monkeypatch):
    translate._CACHE.clear()
    _clear_all_providers(monkeypatch)
    original = "Some grounded English answer text."
    text, ok = translate.translate_text(original, "te")
    assert ok is False
    assert text == original  # never silently loses content


def test_translate_to_english_is_a_noop_for_english_source():
    text, ok = translate.translate_to_english("already English", "en")
    assert (text, ok) == ("already English", True)


def test_translate_text_is_a_noop_for_english_target():
    text, ok = translate.translate_text("already English", "en")
    assert (text, ok) == ("already English", True)


def test_translate_batch_translates_each_text_to_all_supported_languages(monkeypatch):
    calls = []

    def fake_translate(text, target):
        calls.append((text, target))
        return f"{target}:{text}", True

    monkeypatch.setattr(translate, "translate_text", fake_translate)
    for target in sorted(ALL_SIX_LANGUAGES):
        response = translate_batch(TranslateBatchRequest(
            texts=["Button label", "Generated legal guidance"],
            target_language=target,
            external_processing_consent=True,
        ))
        assert response["target_language"] == target
        assert [item["translated"] for item in response["results"]] == [
            f"{target}:Button label",
            f"{target}:Generated legal guidance",
        ]
        assert all(item["success"] for item in response["results"])
    assert len(calls) == len(ALL_SIX_LANGUAGES) * 2


def test_translate_batch_reports_long_text_failure_without_skipping_other_items(monkeypatch):
    monkeypatch.setattr(translate, "translate_text", lambda text, target: (f"{target}:{text}", True))
    response = translate_batch(TranslateBatchRequest(
        texts=["Short label", "x" * 6001],
        target_language="te",
        external_processing_consent=True,
    ))
    assert response["results"][0]["success"] is True
    assert response["results"][1]["success"] is False
    assert response["results"][1]["translated"] == "x" * 6001
    assert "6000-character" in response["results"][1]["reason"]


def test_translate_batch_rejects_unsupported_language():
    with pytest.raises(ValidationError):
        TranslateBatchRequest(texts=["Hello"], target_language="fr")
