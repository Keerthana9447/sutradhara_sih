import os
import sys
import json

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import db, features, privacy  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", str(tmp_path / "feature-workflows.db"))
    db.init_db()


@pytest.fixture
def user():
    created = db.create_user("owner@example.com", "Owner", "correct-horse")
    return created, db.create_auth_session(created["id"])


def test_regime_matrix_has_all_seven_and_analysis_score_is_explainable():
    verdicts = features.regime_verdicts(
        "Classical / Generic Medicine", ["Patents"],
        [{"domain": "Patents"}], "India",
    )
    assert len(verdicts) == 7
    patent = next(item for item in verdicts if item["regime"] == "patent")
    assert patent["verdict"] == "barred"
    response = features.annotate_analysis({
        "confidence": 0.8,
        "sources": [{"relevance_score": 0.5}],
        "applicable_areas": ["Patents"],
        "classification": {"category": "New / Non-Classical Drug"},
        "jurisdiction": "India",
    }, "quick")
    assert 0 <= response["eval_score"] <= 100
    assert response["suggested_query_depth"] in ("guided", "deep")
    assert "does not assess legal or factual correctness" in response["eval_method"]


def test_analysis_api_returns_eval_and_regime_matrix(fresh_db):
    with TestClient(app) as client:
        response = client.post("/api/analyze", json={
            "query": "Can I patent a classical Ayurvedic formulation from Triphala?",
            "jurisdiction": "India",
            "language": "en",
            "query_depth": "quick",
        })
    assert response.status_code == 200
    payload = response.json()
    assert payload["query_depth"] == "quick"
    assert isinstance(payload["eval_score"], (int, float))
    assert len(payload["regime_verdicts"]) == 7
    conn = db.get_conn()
    row = conn.execute("SELECT corpus_snapshot_json FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert row is not None
    snapshot = json.loads(row["corpus_snapshot_json"])
    assert set(snapshot) == {source["id"] for source in payload["sources"]}
    assert all(isinstance(version, str) for version in snapshot.values())


def test_consent_access_log_requires_valid_consent_and_lists_each_actor(fresh_db):
    consent = privacy.request_consent("owner@example.com", "purpose", ["product data"])
    with pytest.raises(ValueError, match="not granted"):
        features.log_consent_access(consent["consent_id"], "user:1")
    privacy.grant_consent(consent["consent_id"])
    first = features.log_consent_access(consent["consent_id"], "user:1")
    assert len(first) == 1
    assert first[0]["actor"] == "user:1"
    assert first[0]["accessed_at"]
    entries = features.log_consent_access(consent["consent_id"], "user:2")
    assert [entry["actor"] for entry in entries] == ["user:1", "user:2"]


def test_consent_access_endpoint_scopes_to_own_grant(fresh_db, user):
    owner, token = user
    consent = privacy.request_consent(owner["email"], "purpose", ["product data"])
    privacy.grant_consent(consent["consent_id"])
    stranger = db.create_user("stranger@example.com", "Stranger", "correct-horse")
    stranger_token = db.create_auth_session(stranger["id"])
    with TestClient(app) as client:
        forbidden = client.post(
            f"/api/privacy/consent/{consent['consent_id']}/access",
            headers={"Authorization": f"Bearer {stranger_token}"},
        )
        allowed = client.post(
            f"/api/privacy/consent/{consent['consent_id']}/access",
            headers={"Authorization": f"Bearer {token}"},
        )
        listed = client.get("/api/privacy/consents", headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 404
    assert allowed.status_code == 200
    assert allowed.json()["access_log"][0]["actor"] == f"user:{owner['id']}"
    assert listed.status_code == 200
    assert listed.json()[0]["access_log"][0]["actor"] == f"user:{owner['id']}"


def test_account_deletion_removes_legacy_personal_records(fresh_db, user):
    owner, _ = user
    consent = privacy.request_consent(owner["email"], "purpose", ["product data"])
    privacy.grant_consent(consent["consent_id"])
    features.log_consent_access(consent["consent_id"], f"user:{owner['id']}")
    deleted = privacy.delete_account(owner["id"])
    assert deleted["formulation_dossiers"] == 0
    assert deleted["dossier_history"] == 0
    assert deleted["prahari_alerts"] == 0
    assert deleted["form7a_drafts"] == 0
    assert deleted["consent_artifacts"] == 1
    assert deleted["consent_access_log"] == 1


def test_unimplemented_legacy_workflow_routes_are_not_registered():
    removed_paths = {
        "/api/v1/draft", "/api/v1/form7a",
        "/api/v1/prahari/{alert_id}/form7a", "/api/cultivator/assessment",
        "/api/v1/broadcasts", "/api/v1/broadcasts/publish",
        "/api/v1/broadcasts/{broadcast_id}", "/api/v1/enhance-broadcast",
        "/api/v1/dossiers/{dossier_id}/objections",
    }
    registered = {route.path for route in app.routes}
    assert removed_paths.isdisjoint(registered)
    assert {
        "/api/v1/dossiers",
        "/api/v1/dossiers/{dossier_id}",
        "/api/v1/dossiers/{dossier_id}/classify",
        "/api/v1/dossiers/{dossier_id}/map",
        "/api/v1/dossiers/{dossier_id}/review",
        "/api/v1/prahari",
        "/api/v1/prahari/{alert_id}",
    } <= registered


def test_deep_query_depth_increases_retrieval_cap(monkeypatch):
    from app import dag, retrieval

    observed = []

    def fake_retrieve(queries, jurisdiction, areas, top_k):
        observed.append(top_k)
        return [
            {"id": f"source-{i}", "relevance_score": 1 - i / 100, "domain": "Patents"}
            for i in range(top_k)
        ]

    monkeypatch.setattr(retrieval, "retrieve", fake_retrieve)
    result = dag._retrieve({
        "query": "patent",
        "jur": "India",
        "query_variants": ["patent"],
        "query_depth": "deep",
        "retrieval_query": "patent",
        "areas": ["Patents"],
        "research_plan": [],
        "planning_mode": "deterministic_fallback",
    })
    assert observed == [10]
    assert len(result["retrieved"]) == 10
