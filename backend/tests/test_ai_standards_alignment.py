import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import privacy  # noqa: E402


def test_ai_standards_alignment_names_a_real_framework():
    result = privacy.ai_standards_alignment()
    assert "NIST AI Risk Management Framework" in result["framework"]


def test_ai_standards_alignment_is_explicit_about_not_being_a_certification():
    result = privacy.ai_standards_alignment()
    assert "not a compliance claim" in result["framework_note"] or "certification" in result["framework_note"]


def test_ai_standards_alignment_covers_all_four_nist_functions():
    result = privacy.ai_standards_alignment()
    assert set(result["functions"].keys()) == {"govern", "map", "measure", "manage"}
    for fn in result["functions"].values():
        assert fn["nist_description"]
        assert len(fn["addressed_by"]) >= 1


def test_ai_standards_alignment_honestly_reports_the_fairness_finding():
    result = privacy.ai_standards_alignment()
    fairness = result["trustworthiness_characteristics"]["fair_with_harmful_bias_managed"]
    # Closed from a flat "not addressed" to a real, narrow, honestly-reported
    # partial check (see app/bias_audit.py) — it must not overclaim full
    # coverage, and it must keep disclosing the real drift the audit found.
    assert fairness["addressed"] == "partial"
    assert "bias_audit.py" in fairness["detail"]
    assert "individual-vs-corporation axis" in fairness["detail"]
    assert "drift" in fairness["detail"].lower()


def test_ai_standards_alignment_covers_all_seven_trustworthiness_characteristics():
    result = privacy.ai_standards_alignment()
    expected = {
        "validity_and_reliability", "safety", "security_and_resilience",
        "accountability_and_transparency", "explainability_and_interpretability",
        "privacy_enhanced", "fair_with_harmful_bias_managed",
    }
    assert set(result["trustworthiness_characteristics"].keys()) == expected


def test_compliance_status_links_to_the_ai_standards_alignment():
    status = privacy.compliance_status()
    assert status["recognised_ai_application_standards"]["implemented"] == "partial"
