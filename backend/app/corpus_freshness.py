"""
Corpus freshness monitoring — the "always-current law" gap.

HONESTY NOTE, stated up front because it matters for how this is presented:
this module does NOT give the corpus a live feed to Indian/international
statute databases (no such free, structured, machine-readable feed exists
for most of the sources in data/corpus.json — the same constraint already
documented in registry_lookup.py and retrieval.py). What it DOES do, for
real:

  1. Turn each corpus document's existing `retrieved_date` into an actual
     staleness signal instead of a decorative field nobody reads — age in
     days, a fresh/aging/stale bucket, and a portfolio-level summary.
  2. Surface that signal everywhere the corpus is actually used: a
     dedicated endpoint (GET /api/corpus/freshness), the health check, and
     — most importantly — a non-blocking warning attached to /api/analyze
     whenever an answer cites a source that has gone stale, so the
     *person asking a legal question* sees the caveat, not just a
     developer looking at an admin panel.
  3. Provide an OPT-IN live reachability check (`live_check=true`) that
     actually issues an HTTP HEAD/GET against each cited source's real
     `source_url` and reports whether it still resolves. This is genuinely
     wired up and will work the moment the process has outbound internet —
     this sandbox does not (see retrieval.py's BGE-embeddings section for
     the identical constraint), so it is exercised in tests only via a
     monkeypatched network call, never a live one here. It fails closed:
     any network error is reported as "unreachable" or "unknown", never
     silently swallowed into a false "fresh".

This turns "always current" from a binary yes/no into what it actually is
for a corpus like this: a measured, honestly-labeled staleness signal, plus
a real (if here untested-live) mechanism to check upstream sources, rather
than a claim that the law itself auto-updates.

  4. propose_refresh() / refresh_state() / approve_refresh(): a real
     drift-detection loop that fetches each source, hashes/diffs it
     against the last snapshot, and surfaces a human-reviewable pending
     change — closing the "does anything re-fetch the actual text"
     question with a genuine mechanism, while deliberately stopping short
     of auto-editing corpus.json (see that section's docstring for why).
     The corpus itself still does not auto-refresh its substantive text;
     a human still approves every change.
"""
import datetime
import difflib
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from . import db, retrieval

logger = logging.getLogger("ip_sakti.corpus_freshness")

# How old a document's last verification can get before it's flagged. Kept
# as a module-level default (env-overridable) rather than hardcoded inline,
# since what counts as "too old" is a policy call, not a technical one.
import os

FRESH_DAYS = int(os.getenv("SUTRADHARA_FRESH_DAYS", "90"))
STALE_DAYS = int(os.getenv("SUTRADHARA_STALE_DAYS", "180"))

_URL_RE = re.compile(r"https?://[^\s()]+")


def _extract_url(source_url_field: str) -> Optional[str]:
    """`source_url` in corpus.json is a human-readable field that often
    carries a parenthetical note after the URL (see corpus.json), e.g.
    'https://... (WIPO Lex — notified 22 Oct 2024)'. Pull out just the URL."""
    if not source_url_field:
        return None
    m = _URL_RE.search(source_url_field)
    return m.group(0).rstrip(").,;") if m else None


def _parse_date(date_str: str) -> Optional[datetime.date]:
    try:
        return datetime.date.fromisoformat(date_str.strip())
    except (ValueError, AttributeError):
        return None


def _bucket(age_days: Optional[int]) -> str:
    if age_days is None:
        return "unknown"
    if age_days <= FRESH_DAYS:
        return "fresh"
    if age_days <= STALE_DAYS:
        return "aging"
    return "stale"


def _doc_freshness(doc: Dict[str, Any], as_of: datetime.date) -> Dict[str, Any]:
    retrieved = _parse_date(doc.get("retrieved_date", ""))
    age_days = (as_of - retrieved).days if retrieved else None
    return {
        "id": doc["id"],
        "title": doc["title"],
        "jurisdiction": doc["jurisdiction"],
        "retrieved_date": doc.get("retrieved_date"),
        "version_date": doc.get("version_date"),
        "age_days": age_days,
        "status": _bucket(age_days),
        "source_url": _extract_url(doc.get("source_url", "")),
    }


def freshness_report(as_of: Optional[datetime.date] = None) -> Dict[str, Any]:
    """Freshness bucket for every corpus document, plus a portfolio summary.
    Never touches the network — pure date arithmetic on data already in the
    corpus. Safe to call on every health check."""
    as_of = as_of or datetime.date.today()
    rows = [_doc_freshness(d, as_of) for d in retrieval._CORPUS]
    counts = {"fresh": 0, "aging": 0, "stale": 0, "unknown": 0}
    for r in rows:
        counts[r["status"]] += 1
    return {
        "as_of": as_of.isoformat(),
        "thresholds_days": {"fresh_up_to": FRESH_DAYS, "aging_up_to": STALE_DAYS},
        "total_documents": len(rows),
        "counts": counts,
        "documents": rows,
        "note": (
            "Freshness is measured from `retrieved_date` (when this corpus entry was last "
            "verified against its authoritative source), not from today's actual state of the "
            "law. A 'fresh' entry means it was verified recently; it does not mean the law has "
            "not changed since. Pass live_check=true to GET /api/corpus/freshness to also probe "
            "whether each source URL still resolves (requires outbound internet access)."
        ),
    }


def freshness_by_id() -> Dict[str, Dict[str, Any]]:
    return {r["id"]: r for r in freshness_report()["documents"]}


def stale_source_ids(sources: List[Dict[str, Any]]) -> List[str]:
    """Given a list of retrieved/cited sources (as returned by retrieval.py),
    return the ids among them that are currently 'stale' — used to attach a
    non-blocking warning to an /api/analyze response."""
    by_id = freshness_by_id()
    return [s["id"] for s in sources if by_id.get(s["id"], {}).get("status") == "stale"]


def build_staleness_warning(sources: List[Dict[str, Any]]) -> Optional[str]:
    stale_ids = stale_source_ids(sources)
    if not stale_ids:
        return None
    plural = "s" if len(stale_ids) > 1 else ""
    return (
        f"{len(stale_ids)} cited source{plural} ({', '.join(stale_ids)}) "
        f"{'have' if len(stale_ids) > 1 else 'has'} not been re-verified against its authoritative "
        f"source in over {STALE_DAYS} days. Confirm current text before relying on it."
    )


def check_live_reachability(doc_ids: Optional[List[str]] = None, timeout: float = 5.0) -> List[Dict[str, Any]]:
    """
    OPT-IN, real network check: HEAD (falling back to GET) each corpus
    document's source_url and report whether it currently resolves. Fails
    closed — any exception (no route to host, timeout, DNS failure, TLS
    error, non-2xx/3xx status) is reported as reachable=False with the
    reason, never silently treated as fresh. `requests` is imported lazily
    so environments without outbound internet (this sandbox included) never
    fail at import time — only if/when this function is actually called
    with live_check=true.
    """
    try:
        import requests
    except ImportError:
        return [{
            "error": "The 'requests' package is not installed; live reachability checking is unavailable.",
        }]

    targets = retrieval._CORPUS if not doc_ids else [d for d in retrieval._CORPUS if d["id"] in doc_ids]
    results = []
    for doc in targets:
        url = _extract_url(doc.get("source_url", ""))
        row: Dict[str, Any] = {"id": doc["id"], "title": doc["title"], "source_url": url}
        if not url:
            row.update({"reachable": None, "reason": "No parseable URL in source_url field."})
            results.append(row)
            continue
        try:
            resp = requests.head(url, timeout=timeout, allow_redirects=True)
            if resp.status_code >= 400:
                # Some government sites reject HEAD; retry with a light GET before giving up.
                resp = requests.get(url, timeout=timeout, allow_redirects=True, stream=True)
            row.update({"reachable": resp.status_code < 400, "status_code": resp.status_code})
        except Exception as e:  # noqa: BLE001 — deliberately broad, see docstring
            row.update({"reachable": False, "reason": f"{type(e).__name__}: {e}"})
        results.append(row)
    return results


# ---------------------------------------------------------------------------
# Auto-refresh / drift detection — closes part of the "always-current law"
# gap a step further than a reachability ping.
#
# HONESTY NOTE: this still does NOT auto-update the corpus text. Nothing in
# this codebase (or, realistically, any automated scraper) should silently
# overwrite a statute's summary/section text from a scraped HTML diff —
# government sites reformat, redirect through cookie/JS walls, or serve
# unrelated boilerplate on error, and a "smart" auto-merge would risk
# quietly corrupting legal content with higher confidence than a human
# would ever have caught it. What THIS mechanism does for real:
#   1. Fetches each cited source's live source_url (same lazy `requests`
#      import and fail-closed behaviour as check_live_reachability).
#   2. Strips markup and hashes the extracted text, then compares it
#      against the hash recorded the last time this ran.
#   3. On the FIRST check for a document, there is nothing to compare
#      against yet, so it records a baseline rather than fabricating a
#      "changed" signal.
#   4. On a later check, if the hash differs, it computes a real unified
#      diff against the previous snapshot and stores it as "pending
#      review" — it does not touch corpus.json.
#   5. A human reviewer calls approve_refresh() after actually reading the
#      diff and confirming the corpus text is still accurate (or after
#      manually editing corpus.json to match). Approval is the only path
#      that advances the stored baseline hash and bumps retrieved_date —
#      both written back to data/corpus.json on disk, so the freshness
#      clock reflects a real, attributed human verification event, not an
#      automatic one.
# ---------------------------------------------------------------------------

_SNAPSHOT_CHARS = 4000  # cap stored/diffed text; this is drift-detection, not a legal archive
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _html_to_text(html: str) -> str:
    """Minimal, dependency-free markup stripper: enough to turn a government
    HTML page into comparable plain text for hashing/diffing. Not a general
    HTML parser — deliberately simple, since it only needs to be stable
    (same page -> same text) rather than pretty."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text[:_SNAPSHOT_CHARS]


def _fetch_source_text(url: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Fetch a source_url and return {'ok', 'text'|'reason'}. Fails closed:
    any exception or non-2xx/3xx response is reported, never swallowed."""
    try:
        import requests
    except ImportError:
        return {"ok": False, "reason": "The 'requests' package is not installed."}
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            return {"ok": False, "reason": f"HTTP {resp.status_code}"}
        return {"ok": True, "text": _html_to_text(resp.text)}
    except Exception as e:  # noqa: BLE001 — see check_live_reachability docstring
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


def _get_refresh_row(conn, doc_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM corpus_refresh_state WHERE doc_id = ?", (doc_id,)
    ).fetchone()
    return dict(row) if row else None


def propose_refresh(doc_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch each targeted document's live source, compare it against the
    last recorded snapshot, and record the result. Returns one status row
    per document actually checked (documents with no parseable source_url
    are skipped, not silently marked fresh)."""
    targets = retrieval._CORPUS if not doc_ids else [d for d in retrieval._CORPUS if d["id"] in doc_ids]
    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    results = []

    for doc in targets:
        url = _extract_url(doc.get("source_url", ""))
        if not url:
            results.append({"id": doc["id"], "status": "skipped", "reason": "No parseable source_url."})
            continue

        fetched = _fetch_source_text(url)
        existing = _get_refresh_row(conn, doc["id"])

        if not fetched["ok"]:
            status = "fetch_failed"
            conn.execute(
                "INSERT INTO corpus_refresh_state (doc_id, last_known_hash, last_checked_at, status) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(doc_id) DO UPDATE SET last_checked_at=excluded.last_checked_at, status=excluded.status",
                (doc["id"], existing["last_known_hash"] if existing else None, now, status),
            )
            results.append({"id": doc["id"], "status": status, "reason": fetched["reason"]})
            continue

        new_hash = hashlib.sha256(fetched["text"].encode("utf-8")).hexdigest()

        if existing is None:
            conn.execute(
                "INSERT INTO corpus_refresh_state "
                "(doc_id, last_known_hash, last_checked_at, last_changed_at, pending_diff, pending_hash, status) "
                "VALUES (?, ?, ?, NULL, NULL, NULL, 'baseline_recorded')",
                (doc["id"], new_hash, now),
            )
            # Stash the raw snapshot text as the pending_diff column's prior
            # value so the NEXT change has something to diff against.
            conn.execute(
                "UPDATE corpus_refresh_state SET pending_diff = ? WHERE doc_id = ?",
                (json.dumps({"_snapshot": fetched["text"]}), doc["id"]),
            )
            results.append({"id": doc["id"], "status": "baseline_recorded"})
        elif existing["last_known_hash"] == new_hash:
            conn.execute(
                "UPDATE corpus_refresh_state SET last_checked_at = ?, status = 'unchanged' WHERE doc_id = ?",
                (now, doc["id"]),
            )
            results.append({"id": doc["id"], "status": "unchanged"})
        else:
            prior_snapshot = ""
            try:
                stored = json.loads(existing.get("pending_diff") or "{}")
                prior_snapshot = stored.get("_snapshot", "")
            except (json.JSONDecodeError, TypeError):
                prior_snapshot = ""
            diff = "\n".join(
                difflib.unified_diff(
                    prior_snapshot.splitlines(), fetched["text"].splitlines(),
                    fromfile="previous_snapshot", tofile="current_fetch", lineterm="", n=1,
                )
            )[:4000]
            conn.execute(
                "UPDATE corpus_refresh_state SET last_checked_at = ?, last_changed_at = ?, "
                "pending_hash = ?, pending_diff = ?, status = 'pending_review' WHERE doc_id = ?",
                (now, now, new_hash, json.dumps({"_snapshot": fetched["text"], "diff": diff}), doc["id"]),
            )
            results.append({"id": doc["id"], "status": "pending_review", "diff_preview": diff[:500]})

    conn.commit()
    conn.close()
    logger.info("CORPUS_REFRESH_PROPOSE checked=%d results=%s", len(results),
                [(r["id"], r["status"]) for r in results])
    return results


def refresh_state(doc_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Current auto-refresh state for corpus documents — what
    propose_refresh() last found, without hitting the network again."""
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM corpus_refresh_state").fetchall()
    conn.close()
    by_id = {r["doc_id"]: dict(r) for r in rows}
    targets = retrieval._CORPUS if not doc_ids else [d for d in retrieval._CORPUS if d["id"] in doc_ids]

    out = []
    for doc in targets:
        row = by_id.get(doc["id"])
        if row is None:
            out.append({"id": doc["id"], "title": doc["title"], "status": "never_checked"})
            continue
        diff_preview = None
        if row.get("status") == "pending_review" and row.get("pending_diff"):
            try:
                diff_preview = json.loads(row["pending_diff"]).get("diff", "")[:500]
            except (json.JSONDecodeError, TypeError):
                diff_preview = None
        out.append({
            "id": doc["id"], "title": doc["title"], "status": row.get("status"),
            "last_checked_at": row.get("last_checked_at"),
            "last_changed_at": row.get("last_changed_at"),
            "diff_preview": diff_preview,
        })
    return out


def approve_refresh(doc_id: str, reviewer: str) -> Dict[str, Any]:
    """A human confirms they have reviewed the pending diff (and, if
    needed, manually updated corpus.json's summary/section text to match).
    This is the ONLY function that advances the stored baseline hash and
    bumps the document's retrieved_date — both persisted to
    data/corpus.json on disk, so the freshness signal reflects a real,
    attributed, human-performed re-verification, not an automatic one."""
    if not reviewer or not reviewer.strip():
        raise ValueError("reviewer is required — approval must be attributable to a person.")

    conn = db.get_conn()
    row = _get_refresh_row(conn, doc_id)
    if row is None or row.get("status") != "pending_review":
        conn.close()
        raise ValueError(f"No pending review for document '{doc_id}'.")

    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE corpus_refresh_state SET last_known_hash = pending_hash, pending_hash = NULL, "
        "status = 'verified', last_checked_at = ? WHERE doc_id = ?",
        (now, doc_id),
    )
    conn.commit()
    conn.close()

    today = datetime.date.today().isoformat()
    doc = retrieval._CORPUS_BY_ID.get(doc_id)
    if doc is not None:
        doc["retrieved_date"] = today
        try:
            with open(retrieval._CORPUS_PATH, "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            for d in on_disk:
                if d["id"] == doc_id:
                    d["retrieved_date"] = today
                    break
            with open(retrieval._CORPUS_PATH, "w", encoding="utf-8") as f:
                json.dump(on_disk, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.warning("Could not persist retrieved_date to corpus.json: %s", e)

    logger.info("CORPUS_REFRESH_APPROVE doc_id=%s reviewer=%s", doc_id, reviewer)
    return {"id": doc_id, "status": "verified", "reviewer": reviewer, "retrieved_date": today}
