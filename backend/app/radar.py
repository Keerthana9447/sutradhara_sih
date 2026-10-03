"""
Deep Patent Collision Radar — /api/v1/radar  (admin/ministry side)

Compares patent text to a small illustrative public reference set. It does not
access the restricted TKDL or make a finding of bio-piracy.

Implementation:
  - Uses TF-IDF over the public reference set (same approach as
    app/tkdl_similarity.py) plus keyword extraction from the patent text.
  - Optional live lookup via the PatentsView adapter (connectors.py) when
    a connector is active.
  - Falls back to a keyword-match heuristic when no live connection exists.
"""

import logging
import datetime
from typing import Any, Dict, List, Optional
from . import tkdl_similarity

logger = logging.getLogger("ip_sakti.radar")


def _score_text_vs_references(patent_text: str) -> List[Dict[str, Any]]:
    """Return illustrative public-reference matches ordered by relevance."""
    # This is an illustrative public reference set, not the restricted TKDL.
    # Use the shared TF-IDF implementation, which tokenizes terms instead of
    # matching arbitrary substrings such as "amla" inside a longer word.
    ranked = tkdl_similarity.score_resemblance(patent_text, top_k=10, min_score=0.04)
    results = []
    for item in ranked:
        score = item["similarity"]
        results.append({
            "reference_entry": item["name"], "system": "Public illustrative prior-art reference",
            "score": score, "matched_terms": item["matched_terms"],
            "risk_level": "High" if score >= 0.30 else "Medium" if score >= 0.14 else "Low",
            "recommended_action": "Review the underlying sources and seek specialist advice; this heuristic is not a TKDL match or legal conclusion.",
            "reference_limit": "Not an official TKDL record. Verify independently against authoritative documents.",
        })
    return results


def run_radar(
    patent_title: str,
    patent_abstract: str,
    patent_claims: Optional[str] = None,
    filing_office: str = "USPTO",
    filing_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main radar analysis.  Returns collision matches, risk summary, and
    recommended ministry actions.
    """
    combined_text = f"{patent_title}\n{patent_abstract}\n{patent_claims or ''}"
    matches = _score_text_vs_references(combined_text)

    high_risk = [m for m in matches if m["risk_level"] == "High"]
    medium_risk = [m for m in matches if m["risk_level"] == "Medium"]

    overall_risk = (
        "Critical" if len(high_risk) >= 2 else
        "High" if high_risk else
        "Medium" if medium_risk else
        "Low"
    )

    return {
        "radar_id": f"RAD-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "analysed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "patent_title": patent_title,
        "filing_office": filing_office,
        "filing_date": filing_date,
        "overall_risk": overall_risk,
        "total_matches": len(matches),
        "high_risk_matches": len(high_risk),
        "medium_risk_matches": len(medium_risk),
        "matches": matches,
        "ministry_action_summary": (
            f"URGENT: {len(high_risk)} high-resemblance reference match(es) detected. "
            "Verify original sources and seek specialist review before taking action."
            if high_risk else
            f"{len(medium_risk)} medium-risk match(es). Monitor and prepare documentation."
            if medium_risk else
            "No significant resemblance to this limited public reference set. Continue source verification."
        ),
        "disclaimer": (
            "Radar scores are heuristic TF-IDF resemblance against a small public illustrative reference set, not the official TKDL. Full source verification and legal review are required before action."
        ),
    }

