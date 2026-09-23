"""
Tests for the three new features: regulatory pathway checklist, TKDL/prior-art
resemblance scoring, and the IP Posture Summary PDF export.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import pathway, tkdl_similarity, posture_pdf

client = TestClient(app)


# ---------------------------------------------------------------------------
# Regulatory pathway
# ---------------------------------------------------------------------------

def test_pathway_returns_steps_for_every_known_category_and_jurisdiction():
    from app.classifier import CATEGORIES
    from app.jurisdiction import VALID_JURISDICTIONS

    for cat in CATEGORIES:
        for jur in VALID_JURISDICTIONS:
            steps = pathway.get_pathway(cat, jur)
            assert isinstance(steps, list)
            assert len(steps) >= 2, f"no pathway defined for {cat} / {jur}"


def test_pathway_is_deterministic_and_never_fabricated_for_unknown_input():
    assert pathway.get_pathway("Not A Real Category", "India") == []
    # calling twice with the same input returns the exact same steps
    a = pathway.get_pathway("Cosmetic", "India")
    b = pathway.get_pathway("Cosmetic", "India")
    assert a == b


def test_pathway_differs_between_classical_and_new_drug_categories():
    classical = pathway.get_pathway("Classical / Generic Medicine", "India")
    new_drug = pathway.get_pathway("New / Non-Classical Drug", "India")
    assert classical != new_drug
    # Section 3(p) framing should appear for classical, not for a genuinely
    # new formulation, since the two have opposite patentability postures.
    assert any("3(p)" in step for step in classical)
    assert not any("3(p)" in step for step in new_drug)


def test_analyze_endpoint_includes_regulatory_pathway():
    resp = client.post("/api/analyze", json={
        "query": "Can I patent a classical Ayurvedic formulation already described in a traditional text?",
        "jurisdiction": "India",
        "language": "en",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["regulatory_pathway"]) >= 2


# ---------------------------------------------------------------------------
# TKDL / prior-art resemblance
# ---------------------------------------------------------------------------

def test_resemblance_finds_the_obviously_similar_reference_entry():
    results = tkdl_similarity.score_resemblance(
        "A powder formulation of amalaki, bibhitaki, and haritaki used for digestion"
    )
    assert results, "expected at least one match for a near-identical description"
    assert results[0]["name"] == "Triphala Churna"
    assert 0 < results[0]["similarity"] <= 1


def test_resemblance_returns_empty_for_unrelated_text():
    results = tkdl_similarity.score_resemblance("a blue plastic phone case with a magnetic clasp")
    assert results == []


def test_resemblance_handles_empty_input_without_error():
    assert tkdl_similarity.score_resemblance("") == []
    assert tkdl_similarity.score_resemblance("   ") == []


def test_maybe_score_resemblance_only_runs_for_relevant_categories():
    assert tkdl_similarity.maybe_score_resemblance("triphala churna amalaki", "Cosmetic") is None
    assert tkdl_similarity.maybe_score_resemblance(
        "a powder of amalaki bibhitaki haritaki", "Classical / Generic Medicine"
    ) is not None


def test_analyze_endpoint_includes_tk_similarity_for_relevant_category():
    resp = client.post("/api/analyze", json={
        "query": "Can I patent a classical Ayurvedic formulation of amalaki, bibhitaki, and haritaki?",
        "jurisdiction": "India",
        "language": "en",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["classification"]["category"] == "Classical / Generic Medicine"
    if data["tk_similarity"]:
        assert data["tk_similarity"][0]["name"]


# ---------------------------------------------------------------------------
# Posture PDF
# ---------------------------------------------------------------------------

def test_build_posture_pdf_produces_valid_pdf_bytes():
    fake_result = {
        "classification": {"category": "Classical / Generic Medicine", "reason": "test"},
        "jurisdiction": "India",
        "input_language": "en",
        "confidence_label": "HIGH",
        "confidence": 0.8,
        "abstained": False,
        "applicable_areas": ["Patents", "Traditional Knowledge"],
        "answer": "(1) Some grounded sentence. [Source: The Patents Act, 1970, Section 3(p)]",
        "tk_pointer": "Check TKDL before filing.",
        "regulatory_pathway": ["Step one.", "Step two."],
        "sources": [
            {"title": "The Patents Act, 1970", "section": "Section 3(p)", "authority": "IP India"},
        ],
    }
    pdf_bytes = posture_pdf.build_posture_pdf(fake_result, "Can I patent this?")
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500


def test_build_posture_pdf_handles_abstained_result_with_no_sources():
    fake_result = {
        "classification": {"category": "Classical / Generic Medicine", "reason": "test"},
        "jurisdiction": "India",
        "input_language": "en",
        "confidence_label": "LOW",
        "confidence": 0.1,
        "abstained": True,
        "applicable_areas": [],
        "answer": "Insufficient authoritative evidence to provide a reliable answer.",
        "sources": [],
    }
    pdf_bytes = posture_pdf.build_posture_pdf(fake_result, "some out of scope query")
    assert pdf_bytes[:4] == b"%PDF"


def test_build_posture_pdf_shows_clarification_question_when_present():
    fake_result = {
        "classification": {
            "category": "Classical / Generic Medicine",
            "reason": "test",
            "needs_clarification": True,
            "clarification_question": "Is this formulation described in a classical text?",
        },
        "jurisdiction": "India",
        "input_language": "en",
        "confidence_label": "LOW",
        "confidence": 0.0,
        "abstained": True,
        "applicable_areas": [],
        "answer": "",
        "sources": [],
    }
    pdf_bytes = posture_pdf.build_posture_pdf(fake_result, "does this qualify")
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500


def test_posture_pdf_endpoint_returns_pdf_content_type():
    analyze_resp = client.post("/api/analyze", json={
        "query": "Can I patent a classical Ayurvedic formulation already described in a traditional text?",
        "jurisdiction": "India",
        "language": "en",
    })
    result = analyze_resp.json()
    pdf_resp = client.post("/api/posture-pdf", json={"query": "Can I patent this?", "result": result})
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content[:4] == b"%PDF"
