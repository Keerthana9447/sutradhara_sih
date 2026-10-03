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

from . import db

_DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "eval_dataset.json")

_CITATION_TAG_RE = re.compile(r"\[Source:[^\]]*\]")


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
    abs_checklist_checked = abs_checklist_correct = 0
    jurisdiction_violations_total = 0
    citation_integrity_violations_total = 0
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

        # --- Classification accuracy ---
        expected_category = item.get("expected_category")
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
        "abstention_accuracy": _rate(abstain_correct, abstain_checked),
        "abstention_items_checked": abstain_checked,
        "clarification_accuracy": _rate(clarification_correct, clarification_checked),
        "clarification_items_checked": clarification_checked,
        "citation_hit_rate": _rate(citation_hit, citation_checked),
        "citation_items_checked": citation_checked,
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
