"""Regression guard for the case-law evidence gap."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import retrieval  # noqa: E402


def test_corpus_has_multiple_case_law_entries():
    case_law_ids = {
        document["id"]
        for document in retrieval._CORPUS
        if document["id"].startswith("IN-CASELAW-")
    }
    assert {
        "IN-CASELAW-DIVYA-PHARMACY",
        "IN-CASELAW-GUJARAT-BOTTLING",
        "IN-CASELAW-TEABOARD-ITC",
        "IN-CASELAW-BURLINGTON-1995",
        "IN-CASELAW-AMEX-PRIYA-PURI-2006",
    } <= case_law_ids
    assert len(case_law_ids) >= 5
