import os
import sys
import io
import json
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import dag, db, features, language, main, ocr_digitize, privacy
from app.schemas import SessionAnalyzeRequest


def test_non_english_analysis_uses_local_fallback_without_external_consent(monkeypatch):
    monkeypatch.setattr(dag.translate, "translate_to_english", lambda *args: (_ for _ in ()).throw(AssertionError("external translation called")))
    monkeypatch.setattr(language, "fallback_normalize", lambda text: "local normalized query")
    result = dag._normalize_language({"query": "తెలుగు ప్రశ్న", "external_processing_consent": False})
    assert result["input_language"] == "te"
    assert result["retrieval_query"] == "local normalized query"


def test_research_planner_is_not_called_without_external_consent(monkeypatch):
    monkeypatch.setattr(dag.llm, "plan_research", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("planner called")))
    result = dag._plan_research({
        "query": "private formulation details",
        "retrieval_query": "private formulation details",
        "jur": "India",
        "areas": ["Patents"],
        "external_processing_consent": False,
    })
    assert result == {"research_plan": [], "planning_mode": "deterministic_fallback"}


def test_answer_paraphrase_is_not_called_without_external_consent(monkeypatch):
    grounded = "Answer. [Source: Act, Section 1]"
    monkeypatch.setattr(dag.llm, "paraphrase_answer", lambda *args: (_ for _ in ()).throw(AssertionError("paraphrase called")))
    result = dag._paraphrase({"generated_answer": grounded, "external_processing_consent": False})
    assert result == {"generated_answer": grounded, "used_llm": False}


import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def consent_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", str(tmp_path / "external-consent.db"))
    db.init_db()

def test_translation_endpoint_rejects_missing_external_consent(consent_db):
    with TestClient(app) as client:
        response = client.post("/api/translate", json={"texts": ["hello"], "target_language": "hi"})
    assert response.status_code == 403

def test_speech_endpoints_reject_missing_external_consent(consent_db):
    with TestClient(app) as client:
        asr_response = client.post("/api/asr/transcribe", json={"audio_base64": "YQ==", "source_language": "en"})
        tts_response = client.post("/api/tts/synthesize", json={"text": "Hello", "language": "en"})
    assert asr_response.status_code == 403
    assert tts_response.status_code == 403


def test_session_analysis_passes_external_processing_consent_to_pipeline(monkeypatch):
    captured = {}

    def fake_pipeline(state):
        captured.update(state)
        return {
            "classification": {
                "category": "Classical / Generic Medicine",
                "confidence": 0.9,
                "reason": "Traditional source indicated.",
            },
            "jurisdiction": "India",
            "applicable_areas": [],
            "answer": "Translated answer",
            "confidence": 0.9,
            "confidence_label": "high",
            "confidence_breakdown": {},
            "sources": [],
            "abstained": False,
            "answer_language": "hi",
            "translation_available": True,
        }

    monkeypatch.setattr(dag, "run_analyze_pipeline", fake_pipeline)
    monkeypatch.setattr(features, "annotate_analysis", lambda *args: None)
    request = SessionAnalyzeRequest(
        query="Hindi language test",
        jurisdiction="India",
        language="hi",
        external_processing_consent=True,
    )

    response = main.analyze_with_session(request)

    assert response.answer_language == "hi"
    assert captured["external_processing_consent"] is True


def test_research_planner_obeys_blocked_cross_border_destination(monkeypatch):
    monkeypatch.setattr(dag.llm, "_RESEARCH_PLANNER_ENABLED", True)
    monkeypatch.setattr(dag.llm, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(dag.privacy, "check_transfer", lambda *args: {"decision": "blocked"})
    monkeypatch.setattr(dag.llm, "plan_research", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("blocked planner called")))
    result = dag._plan_research({
        "query": "question", "retrieval_query": "question", "jur": "India",
        "areas": ["Patents"], "external_processing_consent": True,
    })
    assert result["planning_mode"] == "deterministic_fallback"


def test_ocr_endpoint_requires_consent_for_authenticated_user(consent_db):
    user = db.create_user("ocr@example.com", "OCR User", "long-enough-password")
    token = db.create_auth_session(user["id"])
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ocr",
            headers={"Authorization": f"Bearer {token}"},
            json={"image_base64": "YQ==", "mime_type": "image/jpeg"},
        )
    assert response.status_code == 403


def test_ocr_endpoint_reports_unconfigured_provider_instead_of_placeholder(consent_db, monkeypatch):
    monkeypatch.setattr(ocr_digitize, "GROQ_API_KEY", "")
    monkeypatch.setattr(privacy, "check_transfer", lambda *args: {"decision": "allowed"})
    user = db.create_user("ocr-config@example.com", "OCR User", "long-enough-password")
    token = db.create_auth_session(user["id"])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ocr",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "image_base64": "YQ==",
                "mime_type": "image/jpeg",
                "external_processing_consent": True,
            },
        )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_ocr_provider_failure_is_not_returned_as_empty_success(monkeypatch):
    monkeypatch.setattr(ocr_digitize, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        ocr_digitize,
        "_call_vision_llm",
        lambda *args: (_ for _ in ()).throw(ocr_digitize.OCRProviderError("provider failed")),
    )

    with pytest.raises(ocr_digitize.OCRProviderError, match="provider failed"):
        ocr_digitize.digitise_manuscript("YQ==")


def test_ocr_provider_http_error_exposes_safe_reason(monkeypatch):
    monkeypatch.setattr(ocr_digitize, "GROQ_API_KEY", "test-key")
    error_body = b'{"error":{"message":"model is unavailable"}}'
    http_error = urllib.error.HTTPError(
        ocr_digitize.GROQ_API_URL,
        400,
        "Bad Request",
        hdrs=None,
        fp=io.BytesIO(error_body),
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(http_error))

    with pytest.raises(ocr_digitize.OCRProviderError, match="model is unavailable"):
        ocr_digitize._call_vision_llm("YQ==")


def test_ocr_provider_authorization_error_points_to_key_or_model_access(monkeypatch):
    monkeypatch.setattr(ocr_digitize, "GROQ_API_KEY", "test-key")
    http_error = urllib.error.HTTPError(
        ocr_digitize.GROQ_API_URL,
        403,
        "Forbidden",
        hdrs=None,
        fp=io.BytesIO(b"Forbidden"),
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(http_error))

    with pytest.raises(ocr_digitize.OCRProviderError, match="verify GROQ_API_KEY and vision-model access"):
        ocr_digitize._call_vision_llm("YQ==")


def test_ocr_provider_request_uses_configured_vision_model(monkeypatch):
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{}"}}]}'

    captured = {}

    def fake_urlopen(request, **kwargs):
        captured.update(json.loads(request.data))
        return _Response()

    monkeypatch.setattr(ocr_digitize, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ocr_digitize, "GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert ocr_digitize._call_vision_llm("YQ==") == {}
    assert captured["model"] == "qwen/qwen3.8-27b"
