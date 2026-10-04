import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import jurisdiction
from app.classifier import UNKNOWN_CATEGORY, classify


def test_trade_secret_proprietary_word_does_not_select_medicine_category():
    result = classify(
        "Can I protect my proprietary extraction process and confidential formula as a trade secret?"
    )
    assert result.intent == "Trade Secrets / Confidential Information"
    assert result.category == UNKNOWN_CATEGORY
    assert not result.needs_clarification


def test_patentability_intent_does_not_require_category_without_product_details():
    result = classify("Can I patent an Ayurvedic formulation?")
    assert result.intent == "Patent / Patentability"
    assert result.product_classification == UNKNOWN_CATEGORY
    assert not result.needs_clarification


def test_abs_intent_does_not_require_product_classification():
    result = classify(
        "What access and benefit-sharing obligations apply to a medicinal plant from a forest?"
    )
    assert result.intent == "Access and Benefit Sharing"
    assert result.category == UNKNOWN_CATEGORY
    assert not result.needs_clarification
    areas = jurisdiction.route_areas(
        "What access-and-benefit-sharing rules apply?", result.category, result.intent
    )
    assert "Access-and-Benefit-Sharing" in areas


def test_country_specific_regulatory_question_does_not_infer_product_category():
    result = classify(
        "What regulatory pathway applies to registering an Ayurvedic herbal medicine in Canada?"
    )
    assert result.intent == "Drug Regulation"
    assert result.category == UNKNOWN_CATEGORY
    assert not result.needs_clarification


def test_explicit_classical_formulation_is_classified():
    result = classify("Can I patent a classical Ayurvedic formulation?")
    assert result.intent == "Patent / Patentability"
    assert result.category == "Classical / Generic Medicine"
    assert not result.needs_clarification


def test_genuinely_ambiguous_product_classification_requests_clarification():
    result = classify("Tell me about my Ayurvedic product.")
    assert result.intent == "General IP / Regulatory Guidance"
    assert result.category == UNKNOWN_CATEGORY
    assert result.classification_required
    assert result.needs_clarification
    assert result.clarification_question


def test_off_topic_query_still_asks_for_clarification():
    result = classify("What is the boiling point of tungsten?")
    assert result.intent == "Out of Scope"
    assert result.needs_clarification
