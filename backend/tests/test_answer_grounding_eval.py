import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import retrieval
from app.eval_runner import _evaluate_claim_support


def test_claim_support_uses_cited_corpus_summary_not_only_source_presence():
    document = retrieval.get_document("IN-PAT-3P")
    source_ref = {
        "id": document["id"],
        "title": document["title"],
        "section": document["section"],
        "jurisdiction": document["jurisdiction"],
    }
    supported_answer = (
        f"(1) {document['summary']} "
        f"[Source: {document['title']}, {document['section']}]"
    )
    report = _evaluate_claim_support(supported_answer, [source_ref])
    assert report["claim_count"] == 1
    assert report["supported_claim_count"] == 1
    assert report["unsupported_claim_count"] == 0


def test_claim_support_flags_unsupported_claim_even_when_citation_is_present():
    document = retrieval.get_document("IN-PAT-3P")
    source_ref = {
        "id": document["id"],
        "title": document["title"],
        "section": document["section"],
        "jurisdiction": document["jurisdiction"],
    }
    unsupported_answer = (
        f"(1) This provision grants an automatic patent to every herbal product. "
        f"[Source: {document['title']}, {document['section']}]"
    )
    report = _evaluate_claim_support(unsupported_answer, [source_ref])
    assert report["claim_count"] == 1
    assert report["supported_claim_count"] == 0
    assert report["unsupported_claim_count"] == 1


def test_claim_support_rejects_a_citation_not_in_retrieved_sources():
    document = retrieval.get_document("IN-PAT-3P")
    answer_text = (
        "(1) Traditional knowledge can be excluded from patentability. "
        "[Source: Invented Authority, Section 999]"
    )
    report = _evaluate_claim_support(answer_text, [document])
    assert report["unsupported_claim_count"] == 1
