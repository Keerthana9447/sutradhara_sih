"""Shared analysis annotations and consent access logging."""
import datetime
from typing import Any, Dict, List

from . import db, retrieval

REGIMES = (
    ("patent", "Patents"),
    ("trademark", "Trademarks"),
    ("geographical_indication", "Geographical Indications"),
    ("copyright", "Copyright"),
    ("design", "Designs"),
    ("trade_secret", "Trade Secrets"),
    ("plant_variety", "Plant Variety Protection"),
)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _dump(row: Any) -> Dict[str, Any]:
    return dict(row)


def regime_verdicts(category: str, areas: List[str], sources: List[Dict[str, Any]],
                    jurisdiction_name: str) -> List[Dict[str, Any]]:
    """Return cautious evidence-state indicators, never a legal eligibility opinion."""
    mapped = set(areas)
    verdicts = []
    for key, label in REGIMES:
        if label not in mapped:
            status = "maybe_open"
            reason = "Not specifically mapped by this query; assess the facts and obtain regime-specific advice."
        elif key == "patent" and category == "Classical / Generic Medicine":
            status = "barred"
            reason = "The classification indicates a classical formulation; sections 3(p), 3(e), and/or 3(d) may be material. This is a screening flag, not a final legal determination."
        else:
            status = "open"
            reason = "A potentially relevant path is identified; formal eligibility depends on the facts, applicable law, and supporting evidence. This screening result is not legal advice."
        verdicts.append({
            "regime": key, "label": label, "verdict": status,
            "jurisdiction": jurisdiction_name, "basis": reason,
            "is_legal_opinion": False,
        })
    return verdicts


def log_consent_access(consent_id: str, actor: str) -> List[Dict[str, Any]]:
    from . import privacy
    if not actor or not actor.strip():
        raise ValueError("A verified actor identity is required.")
    if not privacy.is_consent_valid(consent_id):
        raise ValueError("Consent is missing, not granted, revoked, or expired.")
    conn = db.get_conn()
    exists = conn.execute(
        "SELECT 1 FROM consent_artifacts WHERE consent_id = ?", (consent_id,)
    ).fetchone()
    if exists is None:
        conn.close()
        raise ValueError("Consent artifact not found.")
    conn.execute(
        "INSERT INTO consent_access_log (consent_id, actor, accessed_at) VALUES (?, ?, ?)",
        (consent_id, actor, _now()),
    )
    conn.commit()
    rows = conn.execute(
        "SELECT actor, accessed_at FROM consent_access_log WHERE consent_id = ? ORDER BY id",
        (consent_id,),
    ).fetchall()
    conn.close()
    return [_dump(row) for row in rows]


def annotate_analysis(response: Dict[str, Any], query_depth: str) -> Dict[str, Any]:
    """Attach per-answer source-citation and jurisdiction integrity checks."""
    sources = response.get("sources") or []
    areas = response.get("applicable_areas") or []
    jurisdiction_name = response.get("jurisdiction", "India")
    corpus = {doc["id"]: doc for doc in retrieval._CORPUS}
    expected_pairs = set()
    sources_in_corpus = True
    jurisdiction_isolated = True
    for source in sources:
        source = source.model_dump() if hasattr(source, "model_dump") else source
        known = corpus.get(source.get("id"))
        if known is None or known.get("title") != source.get("title") or known.get("section") != source.get("section"):
            sources_in_corpus = False
        else:
            expected_pairs.add((known["title"], known["section"]))
        if source.get("jurisdiction") != jurisdiction_name:
            jurisdiction_isolated = False
    answer_text = response.get("answer", "")
    citation_count = answer_text.count("[Source:")
    citations_match_sources = (
        citation_count == len(expected_pairs)
        and all(f"[Source: {title}, {section}]" in answer_text for title, section in expected_pairs)
    )
    checks = {
        "citations_match_retrieved_sources": citations_match_sources,
        "sources_exist_in_corpus": sources_in_corpus,
        "sources_match_selected_jurisdiction": jurisdiction_isolated,
    }
    score = round(100 * sum(checks.values()) / len(checks))
    suggestion = None
    if score < 85:
        suggestion = {"quick": "guided", "guided": "deep"}.get(query_depth)
    classification = response.get("classification") or {}
    if hasattr(classification, "model_dump"):
        classification = classification.model_dump()
    response.update({
        "query_depth": query_depth,
        "suggested_query_depth": suggestion,
        "eval_score": score,
        "eval_method": "Per-answer deterministic integrity checks: citation labels match the retrieved source set, source IDs and metadata exist in the corpus, and every source matches the selected jurisdiction. This does not assess legal or factual correctness.",
        "eval_checks": checks,
        "regime_verdicts": regime_verdicts(
            classification.get("category", ""),
            areas,
            sources,
            response.get("jurisdiction", "India"),
        ),
    })
    return response
