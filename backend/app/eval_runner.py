"""
Real evaluation benchmark.

db.get_eval_summary() (the original /api/eval endpoint) is honest about its
own limits: it reports live session counters (total queries, abstention
rate, average confidence) but explicitly says "Answer accuracy, citation
correctness and classification accuracy require manual review against the
verified test set ... and are not auto-computed in this prototype."

This module is that automation. It runs every labeled item in
data/eval_dataset.json through the actual FastAPI app (via TestClient — a
real HTTP-shaped call through main.analyze(), not a hand-rolled shortcut
that could drift from production behavior) and grades the response against
machine-checkable expectations:

  - classification_accuracy  — predicted category matches the labeled one
    (only over items with a non-null expected_category)
  - abstention_accuracy      — abstained flag matches the labeled expectation
  - clarification_accuracy   — needs_clarification flag matches expectation
  - citation_hit_rate        — for items with expected_source_ids, at least
    one expected id appears in the returned sources (recall@k, k=5)
  - jurisdiction_isolation_violations — HARD INVARIANT, checked on every
    single item regardless of its own labels: no returned source's
    `jurisdiction` field may differ from the jurisdiction that was
    requested. This is the single most safety-critical number in the whole
    report — any value above 0 means the India/International wall failed.
  - citation_integrity_violations — HARD INVARIANT: every "[Source: Title,
    Section]" tag that appears in the generated answer text must correspond
    to one of the sources actually returned in `sources`. Catches template
    bugs or (if ever re-enabled) LLM-paraphrase drift that the citation
    guard in llm.py was supposed to catch but didn't.
  - avg_latency_ms, tkdl_similarity_coverage, regulatory_pathway_coverage —
    additive, non-pass/fail signals (not accuracy claims) showing real
    average response time and how often the newer TKDL-similarity and
    regulatory-pathway features actually produced output for these labeled
    queries.

This does NOT claim to be a full legal-accuracy audit — a human subject
-matter expert review is still the real bar for whether an *answer's legal
content* is correct. What it does replace is "trust me, I tested it once" —
these numbers are freshly computed from the current corpus + code on every
run, and the report says exactly which items failed and why.
"""
import json
import os
import re
import time
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from . import db, retrieval

_DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "eval_dataset.json")

_CITATION_TAG_RE = re.compile(r"\[Source:[^\]]*\]")
_CLAIM_LINE_RE = re.compile(r"^\s*\(\d+\)\s*(.*?)\s*$")
_CLAIM_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_CLAIM_STOP_WORDS = {
    "about", "after", "also", "and", "are", "arising", "based", "being",
    "from", "general", "including", "into", "more", "other", "over",
    "provides", "relevant", "that", "their", "thereof", "these", "this",
    "under", "which", "with",
}


def _load_dataset() -> List[Dict[str, Any]]:
    with open(_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_citation_integrity(answer_text: str, sources: List[Dict[str, Any]]) -> List[str]:
    """Returns a list of citation tags found in the answer that do NOT match
    any source actually present in the returned sources.

    NOTE: titles/sections in this corpus routinely contain their own commas
    (e.g. "The Drugs and Cosmetics Act, 1940 and Rules, 1945"), so this
    compares the WHOLE "[Source: ...]" tag as one string against the whole
    expected tag built the same way answer.py builds it — splitting the tag
    on its first comma to separate "title" from "section" would misparse
    exactly those multi-comma titles and produce false-positive violations.
    """
    expected_tags = {f"[Source: {s['title']}, {s['section']}]" for s in sources}
    return [tag for tag in _CITATION_TAG_RE.findall(answer_text or "") if tag not in expected_tags]


def _claim_tokens(text: str) -> set[str]:
    return {
        token for token in _CLAIM_TOKEN_RE.findall((text or "").lower())
        if token not in _CLAIM_STOP_WORDS
    }


def _evaluate_claim_support(
    answer_text: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Check numbered legal claim paragraphs against their exact cited source.

    This is a deterministic evidence-overlap check, not legal reasoning or a
    substitute for expert review. The answer template places each corpus
    summary in a numbered paragraph with its source tag, which makes this a
    useful regression signal without an external LLM judge.
    """
    by_tag = {
        f"[Source: {source['title']}, {source['section']}]": source
        for source in sources
    }
    claims = []
    for line in (answer_text or "").splitlines():
        match = _CLAIM_LINE_RE.match(line)
        if not match:
            continue
        paragraph = match.group(1)
        tags = _CITATION_TAG_RE.findall(paragraph)
        claim = _CITATION_TAG_RE.sub("", paragraph).strip()
        claim_terms = _claim_tokens(claim)
        if not claim_terms:
            continue

        cited_source = by_tag.get(tags[0]) if len(tags) == 1 else None
        evidence_text = ""
        if cited_source:
            corpus_source = retrieval.get_document(cited_source.get("id", "")) or cited_source
            evidence_text = " ".join(
                str(corpus_source.get(field, ""))
                for field in ("title", "section", "summary", "domain", "authority")
            )
        evidence_terms = _claim_tokens(evidence_text)
        overlap = len(claim_terms & evidence_terms) / len(claim_terms) if claim_terms else 0.0
        supported = bool(cited_source and cited_source.get("jurisdiction") in {"India", "International"}
                         and overlap >= 0.55)
        claims.append({
            "claim": claim,
            "citation": tags[0] if len(tags) == 1 else None,
            "supported": supported,
            "keyword_overlap": round(overlap, 3),
        })
    return {
        "claims": claims,
        "claim_count": len(claims),
        "supported_claim_count": sum(1 for claim in claims if claim["supported"]),
        "unsupported_claim_count": sum(1 for claim in claims if not claim["supported"]),
    }


def run_benchmark(app) -> Dict[str, Any]:
    db.init_db()  # idempotent (CREATE TABLE IF NOT EXISTS) — TestClient used
    # without the `with` context manager below does not fire FastAPI's
    # startup event, so /api/analyze's own db.log_audit() call would
    # otherwise hit a missing table on a fresh environment.
    client = TestClient(app)
    dataset = _load_dataset()

    per_item = []
    classification_checked = classification_correct = 0
    abstain_checked = abstain_correct = 0
    clarification_checked = clarification_correct = 0
    citation_checked = citation_hit = 0
    intent_checked = intent_correct = 0
    jurisdiction_checked = jurisdiction_correct = 0
    product_classification_checked = product_classification_correct = 0
    abs_checklist_checked = abs_checklist_correct = 0
    jurisdiction_violations_total = 0
    citation_integrity_violations_total = 0
    claim_count_total = supported_claim_count_total = 0
    citation_support_count_total = citation_claim_count_total = 0
    answer_grounding_checked = grounded_answer_count = unsupported_answer_count = 0
    expected_citation_checked = expected_citation_correct = 0
    total_latency_ms = 0.0
    tkdl_present_count = 0
    pathway_present_count = 0

    for item in dataset:
        payload = {
            "query": item["query"],
            "jurisdiction": item["jurisdiction"],
            "language": item.get("language", "en"),
        }
        if item.get("confirmed_category"):
            payload["confirmed_category"] = item["confirmed_category"]
        start_time = time.perf_counter()
        resp = client.post("/api/analyze", json=payload)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        total_latency_ms += elapsed_ms
        result = {"id": item["id"], "http_status": resp.status_code, "latency_ms": round(elapsed_ms, 1), "checks": {}}

        if resp.status_code != 200:
            result["checks"]["http_ok"] = False
            per_item.append(result)
            continue

        body = resp.json()
        sources = body.get("sources", [])
        source_ids = {s["id"] for s in sources}
        classification = body.get("classification", {})
        expected_intent = item.get("expected_intent")
        if expected_intent:
            intent_checked += 1
            intent_ok = classification.get("intent") == expected_intent
            intent_correct += int(intent_ok)
            result["checks"]["intent"] = {
                "expected": expected_intent,
                "actual": classification.get("intent"),
                "pass": intent_ok,
            }

        jurisdiction_checked += 1
        jurisdiction_ok = (
            body.get("jurisdiction") == item["jurisdiction"]
            and all(source.get("jurisdiction") == item["jurisdiction"] for source in sources)
        )
        jurisdiction_correct += int(jurisdiction_ok)
        result["checks"]["jurisdiction_accuracy"] = {
            "expected": item["jurisdiction"],
            "actual": body.get("jurisdiction"),
            "pass": jurisdiction_ok,
        }

        expected_category = item.get("expected_category")
        if expected_category:
            product_classification_checked += 1
            actual_category = classification.get(
                "product_classification", classification.get("category")
            )
            category_ok = actual_category == expected_category
            product_classification_correct += int(category_ok)
            result["checks"]["product_classification"] = {
                "expected": expected_category,
                "actual": actual_category,
                "pass": category_ok,
            }

        # --- Feature-coverage counters (how often these newer, non-core
        # features actually produce something for a labeled query — not a
        # pass/fail check, just an honest usage signal) ---
        if body.get("tk_similarity"):
            tkdl_present_count += 1
        if body.get("regulatory_pathway"):
            pathway_present_count += 1

        # --- Hard invariant 1: jurisdiction isolation, checked on every item ---
        jur_violations = [s["id"] for s in sources if s.get("jurisdiction") != item["jurisdiction"]]
        if jur_violations:
            jurisdiction_violations_total += len(jur_violations)
        result["checks"]["jurisdiction_isolation_violations"] = jur_violations

        # --- Hard invariant 2: citation integrity, checked on every item ---
        citation_violations = _check_citation_integrity(body.get("answer", ""), sources)
        if citation_violations:
            citation_integrity_violations_total += len(citation_violations)
        result["checks"]["citation_integrity_violations"] = citation_violations
        cited_titles = set(_CITATION_TAG_RE.findall(body.get("answer", "")))
        cited_source_ids = {
            source["id"] for source in sources
            if f"[Source: {source['title']}, {source['section']}]" in cited_titles
        }
        claim_report = _evaluate_claim_support(body.get("answer", ""), sources)
        claims = claim_report["claims"]
        claim_count_total += claim_report["claim_count"]
        supported_claim_count_total += claim_report["supported_claim_count"]
        citation_claim_count_total += claim_report["claim_count"]
        citation_support_count_total += claim_report["supported_claim_count"]
        if not body.get("abstained") and body.get("answer"):
            answer_grounding_checked += 1
            item_grounded = bool(claims) and claim_report["unsupported_claim_count"] == 0
            grounded_answer_count += int(item_grounded)
            unsupported_answer_count += int(not item_grounded)
        else:
            item_grounded = claim_report["unsupported_claim_count"] == 0
        result["checks"]["claim_evidence_alignment"] = {
            "claim_count": claim_report["claim_count"],
            "supported_claim_count": claim_report["supported_claim_count"],
            "unsupported_claim_count": claim_report["unsupported_claim_count"],
            "pass": item_grounded,
        }

        # --- Classification accuracy ---
        if expected_category:
            classification_checked += 1
            actual_category = body["classification"]["category"]
            ok = actual_category == expected_category
            classification_correct += int(ok)
            result["checks"]["classification"] = {
                "expected": expected_category, "actual": actual_category, "pass": ok,
            }

        # --- Clarification accuracy ---
        if "expect_clarification" in item:
            clarification_checked += 1
            actual = body["classification"]["needs_clarification"]
            ok = actual == item["expect_clarification"]
            clarification_correct += int(ok)
            result["checks"]["clarification"] = {
                "expected": item["expect_clarification"], "actual": actual, "pass": ok,
            }

        # --- Abstention accuracy ---
        if "expect_abstain" in item:
            abstain_checked += 1
            actual = body["abstained"]
            ok = actual == item["expect_abstain"]
            abstain_correct += int(ok)
            result["checks"]["abstention"] = {
                "expected": item["expect_abstain"], "actual": actual, "pass": ok,
            }

        # --- Citation hit rate (recall@k over expected source ids) ---
        expected_sources = item.get("expected_source_ids") or []
        if expected_sources:
            citation_checked += 1
            hit = bool(source_ids & set(expected_sources))
            citation_hit += int(hit)
            result["checks"]["citation_hit"] = {
                "expected_any_of": expected_sources, "actual": sorted(source_ids), "pass": hit,
            }
            result["checks"]["relevant_source_retrieval"] = {
                "expected_any_of": expected_sources, "pass": hit,
            }
            expected_citation_checked += 1
            cited_expected = bool(cited_source_ids & set(expected_sources))
            expected_citation_correct += int(cited_expected)
            result["checks"]["expected_source_cited"] = {
                "expected_any_of": expected_sources,
                "cited_source_ids": sorted(cited_source_ids),
                "pass": cited_expected,
            }

        # --- ABS checklist trigger check ---
        if item.get("expect_abs_checklist"):
            abs_checklist_checked += 1
            checklist = body.get("abs_checklist")
            ok = bool(checklist and checklist.get("biological_resource_involved"))
            abs_checklist_correct += int(ok)
            result["checks"]["abs_checklist_triggered"] = {"pass": ok}

        per_item.append(result)

    def _rate(correct, total):
        return round(correct / total, 3) if total else None

    report = {
        "total_items": len(dataset),
        "classification_accuracy": _rate(classification_correct, classification_checked),
        "classification_items_checked": classification_checked,
        "intent_accuracy": _rate(intent_correct, intent_checked),
        "intent_items_checked": intent_checked,
        "jurisdiction_accuracy": _rate(jurisdiction_correct, jurisdiction_checked),
        "jurisdiction_items_checked": jurisdiction_checked,
        "product_classification_accuracy": _rate(
            product_classification_correct, product_classification_checked
        ),
        "product_classification_items_checked": product_classification_checked,
        "abstention_accuracy": _rate(abstain_correct, abstain_checked),
        "abstention_items_checked": abstain_checked,
        "clarification_accuracy": _rate(clarification_correct, clarification_checked),
        "clarification_items_checked": clarification_checked,
        "citation_hit_rate": _rate(citation_hit, citation_checked),
        "citation_items_checked": citation_checked,
        "expected_citation_correctness": _rate(
            expected_citation_correct, expected_citation_checked
        ),
        "expected_citation_items_checked": expected_citation_checked,
        "answer_grounding_rate": _rate(grounded_answer_count, answer_grounding_checked),
        "answer_grounding_items_checked": answer_grounding_checked,
        "supported_claim_rate": _rate(supported_claim_count_total, claim_count_total),
        "claim_items_checked": claim_count_total,
        "citation_support_rate": _rate(citation_support_count_total, citation_claim_count_total),
        "citation_support_items_checked": citation_claim_count_total,
        "unsupported_answer_rate": _rate(unsupported_answer_count, answer_grounding_checked),
        "claim_count": claim_count_total,
        "abs_checklist_accuracy": _rate(abs_checklist_correct, abs_checklist_checked),
        "jurisdiction_isolation_violations": jurisdiction_violations_total,
        "citation_integrity_violations": citation_integrity_violations_total,
        "avg_latency_ms": round(total_latency_ms / len(dataset), 1) if dataset else 0.0,
        "tkdl_similarity_coverage": _rate(tkdl_present_count, len(dataset)),
        "regulatory_pathway_coverage": _rate(pathway_present_count, len(dataset)),
        "per_item": per_item,
        "note": (
            "Freshly computed against the current corpus and code on every call to "
            "/api/eval/benchmark — not a cached or hand-picked demo number. "
            "jurisdiction_isolation_violations and citation_integrity_violations must "
            "both be 0; anything else is a correctness bug, not a soft accuracy metric. "
            "This does not replace human legal-accuracy review of the underlying corpus "
            "content itself — see data/eval_dataset.json for the full labeled set."
        ),
    }
    return report
