import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app


def test_trade_secret_answer_excludes_unrelated_patent_and_drug_sources():
    query = (
        "Our proprietary Ayurvedic formula is confidential. "
        "What trade-secret protections may apply in India?"
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={"query": query, "jurisdiction": "India", "language": "en"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["intent"] == "Trade Secrets / Confidential Information"
    assert body["classification"]["product_classification"] == "Unknown / Not Required"
    assert body["sources"]
    assert all(source["domain"] == "Trade Secrets" for source in body["sources"])
    assert "Section 3(p)" not in body["answer"]
    assert "Drug regulation" not in body["answer"]
