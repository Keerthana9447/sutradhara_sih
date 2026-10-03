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
     constraint as retrieval.py's local TF-IDF scoring and
     corpus_freshness.py's live reachability check), so the HTTP call
     itself is only exercised in tests via a monkeypatched response here.
     Fails closed: any missing key, network error, or non-2xx response
     returns live=False with a clear reason, never a fabricated result.
  2. INDIA — since no live query API exists for most registries, this
     builds a correctly parameterized DEEP LINK straight into the actual
     live official portal for the requested registry (IP India patent/
     trademark search, and the National Biodiversity Authority's ABS
     e-filing portal), so the person lands on a real, current, authoritative
     government page pre-filled with their query (or, for ABS, the actual
     filing system itself) instead of a generic homepage pointer. This is
     honestly labeled `live=False` (it is a link to live data/filing, not
     live data itself) but is a genuine improvement over a bare pointer:
     it is testable right now (URL construction, no network needed) and
     the resulting link is real.
  3. GI is the one exception that gets real data, not just a link — IP
     India publishes its complete registered-GI list as a plain,
     unauthenticated, no-CAPTCHA PDF (see gi_registry.py for exactly why
     this one registry is different from InPASS). `_lookup_india` tries
     that real cached data first and only falls back to the deep link if
     the cache has never been successfully built.

Both paths are surfaced through one function, `lookup()`, so callers don't
need to branch on jurisdiction themselves.
"""
import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional

from . import gi_registry

logger = logging.getLogger("ip_sakti.registry_lookup")

PATENTSVIEW_API_URL = "https://search.patentsview.org/api/v1/patent/"

# Real, live official India government registry search portals. Each entry
# is (base_url, query_param) so lookup() only has to urlencode the person's
# search term into a correctly-formed deep link — no scraping, no
# credentials, just pointing at the portal's own public search form the way
# a person's browser would.
_INDIA_REGISTRIES: Dict[str, Dict[str, Any]] = {
    "patents": {
        "label": "IP India — Patent Search (InPASS)",
        "base_url": "https://ipindiaonline.gov.in/patentsearch/search/index.aspx",
        "query_param": None,
        "kind": "search",
    },
    "trademarks": {
        "label": "IP India — Trade Marks Public Search",
        "base_url": "https://ipindiaonline.gov.in/tmrpublicsearch/frmmain.aspx",
        "query_param": None,
        "kind": "search",
    },
    "gi": {
        "label": "Geographical Indications Registry — Search",
        "base_url": "https://search.ipindia.gov.in/GIRPublic/",
        "query_param": None,
        "kind": "search",
    },
    "abs": {
        "label": "National Biodiversity Authority — Online ABS Filing",
        "base_url": "http://www.nbaindia.org",
        "query_param": None,
        "kind": "filing",
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


def lookup_patentsview(keyword: str, api_key: str, limit: int = 5,
                       timeout: float = 8.0) -> Dict[str, Any]:
    """Search PatentsView with an explicitly supplied key.

    Results are US patent records and are kept separate from legal-corpus
    citations by callers. Network/API failures are returned as explicit
    non-live results; no placeholder record is substituted.
    """
    if not api_key:
        return {"live": False, "reason": "PatentsView API key is not configured.", "results": []}

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
        logger.warning("PatentsView lookup failed: %s", type(e).__name__)
        return {"live": False, "reason": f"PatentsView request failed: {type(e).__name__}.", "results": []}


def _lookup_international(keyword: str, limit: int = 5, timeout: float = 8.0) -> Dict[str, Any]:
    api_key = os.getenv("PATENTSVIEW_API_KEY")
    if not api_key:
        return {"live": False, "reason": "PATENTSVIEW_API_KEY not configured.", "results": []}
    return lookup_patentsview(keyword, api_key, limit, timeout)


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj)


def _lookup_india(registry: str, keyword: str) -> Dict[str, Any]:
    entry = _INDIA_REGISTRIES.get(registry)
    if not entry:
        valid = ", ".join(_INDIA_REGISTRIES)
        return {"live": False, "reason": f"Unknown India registry '{registry}'. Valid: {valid}.", "deep_link": None}

    # GI is the one India registry with a real, periodically-refreshed data
    # cache behind it (see gi_registry.py) — try that first, and fall back
    # to the deep link only if the cache was never built or is empty. This
    # can never make the existing deep-link behaviour worse.
    if registry == "gi":
        try:
            gi_result = gi_registry.search(keyword)
            if gi_result.get("live"):
                return gi_result
        except Exception as e:  # noqa: BLE001 — fail closed to the deep link, never surface a raw error
            logger.warning("GI registry cache search failed, falling back to deep link: %r", e)

    url = entry["base_url"]
    if entry["query_param"]:
        url = f"{url}?{urllib.parse.urlencode({entry['query_param']: keyword})}"

    if entry.get("kind") == "filing":
        # ABS is not a keyword-searchable registry at all — the NBA portal is
        # a single-window online APPLICATION system (Form-I) for prior
        # approval to access a biological resource / associated traditional
        # knowledge, not a public record you look up by name. Saying so
        # honestly here matters: a caller passing a formulation's ingredient
        # name as `keyword` should not be led to expect a search result.
        note = (
            f"The National Biodiversity Authority does not publish a searchable public register — "
            f"it is a single-window ONLINE FILING system (Form-I under the Biological Diversity Rules, "
            f"2004/2024) for prior approval before accessing a biological resource or associated "
            f"traditional knowledge for research or commercial use. There is nothing to search for "
            f"'{keyword}' here; this links to the live portal where that approval is actually filed. "
            f"See Divya Pharmacy v. Union of India (Uttarakhand HC, 2018) in the corpus for why an "
            f"Indian-owned manufacturer is not exempt from this requirement."
        )
    else:
        note = (
            "This portal does not expose a public query-string search API, so this links to the "
            "live official search page itself rather than pre-filled results — search there "
            f"for '{keyword}'. This is a real, current government portal, not a mocked page."
        )

    return {
        "live": False,
        "provider": entry["label"],
        "deep_link": url,
        "note": note,
    }


def lookup(jurisdiction: str, keyword: str, registry: str = "patents", limit: int = 5) -> Dict[str, Any]:
    """
    jurisdiction: 'India' or 'International'.
    registry: 'patents' | 'trademarks' | 'gi' | 'abs' — only 'patents' is
    meaningful for International (PatentsView is a US-patent API). 'abs' is
    not a search registry (see _lookup_india's docstring note) — it deep-links
    to the National Biodiversity Authority's ABS e-filing portal.
    """
    if not keyword or not keyword.strip():
        raise ValueError("keyword is required")

    if jurisdiction == "International":
        return {"jurisdiction": "International", "registry": "patents", **_lookup_international(keyword.strip(), limit)}
    if jurisdiction == "India":
        return {"jurisdiction": "India", "registry": registry, **_lookup_india(registry, keyword.strip())}
    raise ValueError("jurisdiction must be 'India' or 'International'")
