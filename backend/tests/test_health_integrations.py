import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_integration_modes_without_exposing_credentials(monkeypatch):
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "health-secret-sentinel")
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    integrations = body["integrations"]
    assert integrations["core_analysis"]["mode"] == "LIVE"
    assert integrations["tkdl"]["mode"] == "REFERENCE_ONLY"
    assert integrations["tkdl"]["connected"] is False
    assert integrations["india_patent_trademark_registry"]["mode"] == "FALLBACK"
    assert integrations["india_patent_trademark_registry"]["live_search"] is False
    assert integrations["graph"]["mode"] in {"LIVE", "REFERENCE"}
    assert integrations["asr"]["supported_languages"] == ["en", "hi", "te", "ta", "ml", "sa"]
    assert integrations["tts"]["supported_languages"] == ["en", "hi", "te", "ta", "ml", "sa"]
    assert integrations["patentsview"]["configured"] is True
    assert "health-secret-sentinel" not in response.text


def test_static_graph_api_is_explicitly_reference_data():
    with TestClient(app) as client:
        response = client.get("/api/graph")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "REFERENCE"
    assert body["live_government_data"] is False
