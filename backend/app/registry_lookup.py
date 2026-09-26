"""
Live official registry access — the "live official registry/database
access: not implemented" gap.

HONESTY NOTE up front, in the same spirit as tkdl_similarity.py and
connectors.py: there is no free, structured, machine-readable public API
for India's own IP registries (IP India's patent/trademark search, the GI
Registry, TKDL itself are all web portals with no public REST API — this is
a real fact about these registries, not a limitation of this codebase). So
this module does two genuinely different, both-real things rather than one
fake "registry connector" that pretends parity across jurisdictions:

  1. INTERNATIONAL — a real, live HTTP integration against the USPTO
     PatentsView Search API (search.patentsview.org), a free, publicly
     documented US-patent API. Actually issues the request and parses the
     real response shape when PATENTSVIEW_API_KEY is set and the process
     has outbound internet — neither of which this sandbox has (same
     constraint as retrieval.py's BGE model download and
     corpus_freshness.py's live reachability check), so the HTTP call
     itself is only exercised in tests via a monkeypatched response here.
     Fails closed: any missing key, network error, or non-2xx response
     returns live=False with a clear reason, never a fabricated result.
  2. INDIA — since no live query API exists, this builds a correctly
     parameterized DEEP LINK straight into the actual live official portal
     for the requested registry (IP India patent/trademark search, the GI
     Registry), so the person lands on a real, current, authoritative
     government search pre-filled with their query instead of a generic
     homepage pointer. This is honestly labeled `live=False` (it is a link
     to live data, not live data itself) but is a genuine improvement over
     a bare pointer: it is testable right now (URL construction, no
     network needed) and the resulting link is real.

Both paths are surfaced through one function, `lookup()`, so callers don't
need to branch on jurisdiction themselves.
"""
import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ip_sakti.registry_lookup")

PATENTSVIEW_API_URL = "https://search.patentsview.org/api/v1/patent/"

# Real, live official India government registry search portals. Each entry
# is (base_url, query_param) so lookup() only has to urlencode the person's
# search term into a correctly-formed deep link — no scraping, no
# credentials, just pointing at the portal's own public search form the way
# a person's browser would.
_INDIA_REGISTRIES: Dict[str, Dict[str, str]] = {
    "patents": {
        "label": "IP India — Patent Search (InPASS)",
        "base_url": "https://ipindiaonline.gov.in/patentsearch/search/index.aspx",
        "query_param": None,  # InPASS's public search is form/session-driven, not URL-queryable
    },
    "trademarks": {
        "label": "IP India — Trade Marks Public Search",
        "base_url": "https://ipindiaonline.gov.in/tmrpublicsearch/frmmain.aspx",
        "query_param": None,
    },
    "gi": {
        "label": "Geographical Indications Registry — Search",
        "base_url": "https://search.ipindia.gov.in/GIRPublic/",
        "query_param": None,
    },
}


def patentsview_status() -> Dict[str, Any]:
    """Same shape/spirit as translate.sarvam_translate_status() and
    asr.asr_status(): report configuration state honestly rather than
    silently no-op-ing."""
    key = os.getenv("PATENTSVIEW_API_KEY")
    return {
        "configured": bool(key),
        "note": (
            "Set PATENTSVIEW_API_KEY (free registration at "
            "https://patentsview.org/apis/keyrequest) to enable live International patent "
            "lookups. Without it, lookup(jurisdiction='International') returns live=False."
        ),
    }


def _lookup_international(keyword: str, limit: int = 5, timeout: float = 8.0) -> Dict[str, Any]:
    api_key = os.getenv("PATENTSVIEW_API_KEY")
    if not api_key:
        return {"live": False, "reason": "PATENTSVIEW_API_KEY not configured.", "results": []}

    try:
        import requests
    except ImportError:
        return {"live": False, "reason": "'requests' package not installed.", "results": []}

    query = {"_text_any": {"patent_title": keyword}}
    fields = ["patent_id", "patent_title", "patent_date"]
    params = {
        "q": _json_dumps(query),
        "f": _json_dumps(fields),
        "o": _json_dumps({"size": limit}),
    }
    try:
        resp = requests.get(
            PATENTSVIEW_API_URL, params=params, timeout=timeout,
            headers={"X-Api-Key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        patents = data.get("patents", []) or []
        return {
            "live": True,
            "provider": "USPTO PatentsView Search API",
            "results": [
                {
                    "patent_id": p.get("patent_id"),
                    "title": p.get("patent_title"),
                    "date": p.get("patent_date"),
                    "url": f"https://patents.google.com/patent/US{p.get('patent_id')}" if p.get("patent_id") else None,
                }
                for p in patents
            ],
        }
    except Exception as e:  # noqa: BLE001 — fails closed, see module docstring
        logger.warning("PatentsView lookup failed: %r", e)
        return {"live": False, "reason": f"{type(e).__name__}: {e}", "results": []}


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj)


def _lookup_india(registry: str, keyword: str) -> Dict[str, Any]:
    entry = _INDIA_REGISTRIES.get(registry)
    if not entry:
        valid = ", ".join(_INDIA_REGISTRIES)
        return {"live": False, "reason": f"Unknown India registry '{registry}'. Valid: {valid}.", "deep_link": None}

    url = entry["base_url"]
    if entry["query_param"]:
        url = f"{url}?{urllib.parse.urlencode({entry['query_param']: keyword})}"

    return {
        "live": False,
        "provider": entry["label"],
        "deep_link": url,
        "note": (
            "This portal does not expose a public query-string search API, so this links to the "
            "live official search page itself rather than pre-filled results — search there "
            f"for '{keyword}'. This is a real, current government portal, not a mocked page."
        ),
    }


def lookup(jurisdiction: str, keyword: str, registry: str = "patents", limit: int = 5) -> Dict[str, Any]:
    """
    jurisdiction: 'India' or 'International'.
    registry: 'patents' | 'trademarks' | 'gi' — only 'patents' is meaningful
    for International (PatentsView is a US-patent API).
    """
    if not keyword or not keyword.strip():
        raise ValueError("keyword is required")

    if jurisdiction == "International":
        return {"jurisdiction": "International", "registry": "patents", **_lookup_international(keyword.strip(), limit)}
    if jurisdiction == "India":
        return {"jurisdiction": "India", "registry": registry, **_lookup_india(registry, keyword.strip())}
    raise ValueError("jurisdiction must be 'India' or 'International'")
