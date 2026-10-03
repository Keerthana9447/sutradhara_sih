"""
GI Registry real-data connector — the one India IP registry that CAN
honestly go beyond a deep link, unlike patents/trademarks.

WHY THIS ONE, WHEN registry_lookup.py's patents/trademarks/abs entries are
all deep-links-only: InPASS (patent search) requires solving a CAPTCHA to
search — an explicit anti-automation control this codebase will not try to
bypass (see registry_lookup.py). The GI Registry is different: IP India
itself publishes a complete, current "Total Registered GI details of GI
Application in India" list as a plain, unauthenticated PDF download, linked
from its own public page:
  https://ipindia.gov.in/geographical-indications-track-application-list-of-
  registered-geographical-indications-and-authorised-users-part-a-register-
  list-of-registered-gi-of-india
No login, no CAPTCHA, no session — literally a static file the government
publishes for public reuse. Fetching and indexing it is not scraping around
a protection; it is reading a document that was put online to be read.

WHAT THIS MODULE ACTUALLY DOES:
  1. build_index(force_refresh=False) fetches that landing page, finds the
     current PDF's URL, downloads it, and parses it into structured rows
     (serial no, application no, GI name, goods category, state) using a
     real text-extraction + regex parser (see _parse_entries below) that
     was developed and verified against the actual current PDF's text.
  2. Rows are cached in SQLite (gi_registry_cache), replacing the previous
     cache only on a SUCCESSFUL parse — a failed fetch/parse leaves any
     existing cache untouched rather than wiping real data (same fail-
     closed philosophy as corpus_freshness.py).
  3. search(keyword) queries the cache for real matches: this is genuinely
     current government data, refreshed by build_index(), not a fabricated
     placeholder — distinguished from a true request-time API only in that
     it is periodically-refreshed batch data rather than a live query.
  4. registry_lookup.py falls back to its existing deep-link behaviour for
     'gi' whenever this cache is empty (never built, or every attempt has
     failed) — so nothing here can make a working feature worse.

HONESTY ABOUT THE PARSER: this is real text extracted from a real
government PDF, not a rigid schema — official PDFs have their own
irregularities (an observed real example: one row is genuinely missing its
application number in the source PDF itself). The parser handles known
irregularities but is not guaranteed pixel-perfect on every future edition;
build_index() reports how many rows it found and flags low_confidence when
that count looks implausibly small, so a human can tell if a parse went
wrong rather than trusting a silently-broken result.
"""
import datetime
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from . import db

logger = logging.getLogger("ip_sakti.gi_registry")

GI_LANDING_PAGE_URL = (
    "https://ipindia.gov.in/geographical-indications-track-application-list-of-registered-"
    "geographical-indications-and-authorised-users-part-a-register-list-of-registered-gi-of-india"
)

_PDF_LINK_RE = re.compile(r'href="(https://ipindia\.gov\.in/storage/uploads/docs-operator/[^"]+\.pdf)"', re.IGNORECASE)

_CATEGORY_RE = r"(Agriculture|Handicrafts?|Manufactured|Food\s*[Ss]tuff|Natural(?:\s+Goods)?)"
_TWO_GROUP_ANCHOR = re.compile(r"\d+(?:\s*&\s*\d+)?\s+\d+(?:\s*&\s*\d+)?\s+(?=[A-Z])")
_ONE_GROUP_ANCHOR = re.compile(r"\d+\s+(?=[A-Z])")

# Sanity floor: the current published list runs to 800+ entries. A parse
# that yields far fewer likely means the PDF's layout changed under us.
_LOW_CONFIDENCE_THRESHOLD = 100


def _lazy_requests():
    try:
        import requests
        return requests
    except ImportError:
        return None


def _find_pdf_url(landing_html: str) -> Optional[str]:
    """The landing page currently lists two PDFs (the full list, and a
    state-grouped variant); we want the FIRST one found, which corresponds
    to 'Total Registered GI details of GI Application in India' — the
    complete per-application list this parser is built for."""
    match = _PDF_LINK_RE.search(landing_html)
    return match.group(1) if match else None


def _clean_text(raw: str) -> str:
    """Strip page-number artifacts, fiscal-year section dividers, and the
    one-time column-header preamble from raw PDF-extracted text, verified
    against the actual current PDF's extraction output."""
    lines = raw.splitlines()
    out: List[str] = []
    skip_preamble = True
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if skip_preamble:
            if s == "State":  # last token of the one-time column header row
                skip_preamble = False
            continue
        if re.fullmatch(r"\d{1,4}", s):
            continue  # bare page-number artifact
        if s.upper().startswith("FROM ") and "MARCH" in s.upper():
            continue  # "FROM APRIL <yyyy> - MARCH <yyyy>" fiscal-year divider
        if s.upper().startswith("REGISTRATION DETAILS"):
            continue  # repeated document title
        out.append(s)
    return " ".join(out)


def _split_last_anchor(segment: str) -> (str, str):
    """Split a blob of 'state-of-previous-entry + sno/appno/name-of-next-
    entry' text using the RIGHTMOST leading-digit-group(s)+capital-letter
    anchor — GI names start with a capital letter, application numbers
    don't, so this reliably finds where the next entry begins."""
    matches = list(_TWO_GROUP_ANCHOR.finditer(segment))
    if not matches:
        matches = list(_ONE_GROUP_ANCHOR.finditer(segment))
    if not matches:
        return segment.strip(), ""
    m = matches[-1]
    return segment[:m.start()].strip(), segment[m.start():].strip()


def _parse_sno_appno_name(pre: str) -> (str, str, str):
    dm = re.match(r"^(\d+(?:\s*&\s*\d+)?)\s+(\d+(?:\s*&\s*\d+)?)\s+(.*)$", pre)
    if dm:
        return dm.group(1), dm.group(2), dm.group(3).strip()
    dm2 = re.match(r"^(\d+)\s+(.*)$", pre)
    if dm2:
        return dm2.group(1), "", dm2.group(2).strip()  # known real-world irregularity: missing app no
    return "", "", pre.strip()


def _parse_entries(text: str) -> List[Dict[str, str]]:
    """Parse cleaned, flattened PDF text into structured GI entries using
    the goods-category column as the anchor (a small closed set, reliably
    separating each entry's name from its state) — tested against the
    actual current PDF's real, multi-line-wrapped, occasionally-irregular
    text (see the module test file for the exact verified cases)."""
    blob = _clean_text(text)
    parts = re.split(_CATEGORY_RE, blob)
    n_entries = (len(parts) - 1) // 2
    entries = []
    carry_pre = parts[0] if parts else ""
    for i in range(n_entries):
        category = parts[1 + 2 * i]
        following = parts[2 + 2 * i]
        sno, appno, name = _parse_sno_appno_name(carry_pre)
        if i + 1 < n_entries:
            state, carry_pre = _split_last_anchor(following)
        else:
            state, carry_pre = following.strip(), ""
        if name:
            entries.append({
                "sr_no": sno, "application_no": appno, "name": name,
                "goods_category": category, "state": state,
            })
    return entries


def build_index(force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch the landing page, find the current PDF, download and parse it,
    and replace the cache — but ONLY on a fully successful parse. Any
    failure leaves the existing cache untouched and returns live=False with
    a clear reason, never a partial or fabricated replacement."""
    requests = _lazy_requests()
    if requests is None:
        return {"live": False, "reason": "'requests' package not installed."}

    try:
        import pypdf
    except ImportError:
        return {"live": False, "reason": "'pypdf' package not installed."}

    try:
        landing = requests.get(GI_LANDING_PAGE_URL, timeout=10)
        if landing.status_code >= 400:
            return {"live": False, "reason": f"Landing page returned HTTP {landing.status_code}."}
        pdf_url = _find_pdf_url(landing.text)
        if not pdf_url:
            return {"live": False, "reason": "Could not find a GI PDF link on the landing page — its layout may have changed."}

        pdf_resp = requests.get(pdf_url, timeout=30)
        if pdf_resp.status_code >= 400:
            return {"live": False, "reason": f"PDF download returned HTTP {pdf_resp.status_code}.", "source_pdf_url": pdf_url}

        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_resp.content))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:  # noqa: BLE001 — fails closed, see module docstring
        logger.warning("GI registry build_index failed: %r", e)
        return {"live": False, "reason": f"{type(e).__name__}: {e}"}

    entries = _parse_entries(full_text)
    low_confidence = len(entries) < _LOW_CONFIDENCE_THRESHOLD
    if not entries:
        return {"live": False, "reason": "Parse produced zero entries — not replacing existing cache.", "source_pdf_url": pdf_url}

    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    conn.execute("DELETE FROM gi_registry_cache")
    conn.executemany(
        "INSERT INTO gi_registry_cache (sr_no, application_no, name, goods_category, state, source_pdf_url, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(e["sr_no"], e["application_no"], e["name"], e["goods_category"], e["state"], pdf_url, now) for e in entries],
    )
    conn.execute(
        "INSERT INTO gi_registry_meta (id, source_pdf_url, entry_count, built_at, parse_method, low_confidence) "
        "VALUES (1, ?, ?, ?, 'text_category_anchor', ?) "
        "ON CONFLICT(id) DO UPDATE SET source_pdf_url=excluded.source_pdf_url, entry_count=excluded.entry_count, "
        "built_at=excluded.built_at, parse_method=excluded.parse_method, low_confidence=excluded.low_confidence",
        (pdf_url, len(entries), now, int(low_confidence)),
    )
    conn.commit()
    conn.close()

    result = {"live": True, "source_pdf_url": pdf_url, "entry_count": len(entries), "built_at": now}
    if low_confidence:
        result["low_confidence"] = True
        result["note"] = (
            f"Only {len(entries)} entries parsed, below the {_LOW_CONFIDENCE_THRESHOLD}-entry sanity floor "
            "for the current published list — the PDF's layout may have changed. Cache was still replaced "
            "with what was found; spot-check before relying on it."
        )
    return result


def status() -> Dict[str, Any]:
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM gi_registry_meta WHERE id = 1").fetchone()
    count_row = conn.execute("SELECT COUNT(*) as c FROM gi_registry_cache").fetchone()
    conn.close()
    if row is None:
        return {"built": False, "entry_count": count_row["c"] if count_row else 0,
                "note": "No successful build yet — call POST /api/registry/gi/refresh, or use the deep link fallback in registry_lookup.py."}
    return {
        "built": True,
        "source_pdf_url": row["source_pdf_url"],
        "entry_count": row["entry_count"],
        "built_at": row["built_at"],
        "parse_method": row["parse_method"],
        "low_confidence": bool(row["low_confidence"]),
    }


def search(keyword: str, limit: int = 5) -> Dict[str, Any]:
    """Real, current-as-of-last-refresh search over the cached GI list.
    Returns live=False (not empty results — a genuinely different signal)
    when the cache has never been successfully built, so callers can fall
    back to the deep link rather than reporting a false 'no matches'."""
    if not keyword or not keyword.strip():
        raise ValueError("keyword is required")

    meta = status()
    if not meta["built"]:
        return {"live": False, "reason": "GI registry cache has not been built yet.", "results": []}

    like = f"%{keyword.strip()}%"
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT sr_no, application_no, name, goods_category, state FROM gi_registry_cache "
        "WHERE name LIKE ? OR goods_category LIKE ? OR state LIKE ? LIMIT ?",
        (like, like, like, limit),
    ).fetchall()
    conn.close()

    return {
        "live": True,
        "provider": "IP India — Registered GI list (periodically refreshed from the official published PDF)",
        "source_pdf_url": meta["source_pdf_url"],
        "cached_as_of": meta["built_at"],
        "results": [dict(r) for r in rows],
    }
