"""
DPDP-aligned data governance — the "DPDP/AI security compliance" gap.

HONESTY NOTE up front: this is not a legal compliance certification (no
software module can be), and it doesn't cover every obligation in India's
Digital Personal Data Protection Act, 2023 (e.g. a Consent Manager
integration, or Significant Data Fiduciary obligations). What it DOES
implement for real, against the actual sqlite tables in db.py:

  1. Data minimization at write time — free-text queries are scanned for
     obvious PII (email addresses, phone-like digit runs, Aadhaar-like
     12-digit runs) BEFORE they are ever written to audit_log, and the PII
     is masked in the stored copy. Nothing is silently kept "just in case".
  2. Purpose/storage limitation — a configurable retention window with a
     real purge function that deletes (not just marks) rows past it.
  3. Right to access — a person who knows their own query text and/or the
     contact email they gave at escalation time can pull every record tied
     to it across audit_log / feedback / escalation / connector tables.
  4. Right to erasure — the same lookup, but delete instead of return.
     Deletion is real (SQL DELETE), not a soft "deleted" flag, because a
     soft flag is not erasure.
  5. A machine-readable compliance-posture summary (`compliance_status()`)
     stating plainly what is and is not implemented, for the same reason
     every other module in this codebase states its own honest scope.

This mirrors the connector-consent lifecycle already implemented in
connectors.py (link/use/revoke, all logged) — this module is the equivalent
lifecycle for the person's own conversational data.
"""
import datetime
import hashlib
import logging
import re
import secrets
from typing import Any, Dict, List, Optional

from . import db

logger = logging.getLogger("ip_sakti.privacy")

import os

DEFAULT_RETENTION_DAYS = int(os.getenv("SUTRADHARA_RETENTION_DAYS", "180"))

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# 10+ consecutive digits (optionally grouped by spaces/hyphens) catches
# Indian mobile numbers (10 digits), Aadhaar numbers (12 digits), and most
# other national ID / phone patterns without needing a country-specific
# rulebook for every jurisdiction a user might type.
_DIGIT_RUN_RE = re.compile(r"(?:\d[\s-]?){10,}")


def redact_pii(text: str) -> str:
    """Mask obvious PII in free text before it is persisted anywhere. Applied
    to `query` at the point of logging (db.log_audit), not to the text used
    to actually answer the question in the same request — minimization
    governs what we KEEP, not what we process to serve the person asking."""
    if not text:
        return text
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _DIGIT_RUN_RE.sub("[redacted-number]", text)
    return text


# ---------------------------------------------------------------------------
# Retention / purge
# ---------------------------------------------------------------------------
def purge_expired(retention_days: Optional[int] = None) -> Dict[str, int]:
    """Hard-delete audit_log, feedback, and escalation rows older than the
    retention window. Connector consent records are exempt: revocation
    already exists as their own deletion lifecycle (connectors.py), and an
    active connector's own consent record must persist for as long as it is
    usable — a time-based purge on that table would silently break a still-
    valid consent."""
    retention_days = retention_days if retention_days is not None else DEFAULT_RETENTION_DAYS
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)).isoformat()

    conn = db.get_conn()
    deleted = {}
    for table in ("audit_log", "feedback", "escalation"):
        cur = conn.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))
        deleted[table] = cur.rowcount
    conn.commit()
    conn.close()
    logger.info("PRIVACY_PURGE retention_days=%d cutoff=%s deleted=%s", retention_days, cutoff, deleted)
    return deleted


# ---------------------------------------------------------------------------
# Right to access
# ---------------------------------------------------------------------------
def _find_matches(query_text: Optional[str], contact_email: Optional[str], conn) -> Dict[str, List[Dict[str, Any]]]:
    results: Dict[str, List[Dict[str, Any]]] = {"audit_log": [], "feedback": [], "escalation": []}

    if query_text:
        redacted = redact_pii(query_text)
        # Match either the raw text (in case it contained no PII and was
        # stored verbatim) or its redacted form (in case it did).
        for table, cols in (
            ("audit_log", "id, timestamp, query, jurisdiction, category, confidence, abstained"),
            ("feedback", "id, timestamp, query, answer_id, rating, comment"),
            ("escalation", "id, timestamp, query, product_category, jurisdiction, status"),
        ):
            rows = conn.execute(
                f"SELECT {cols} FROM {table} WHERE query = ? OR query = ?",
                (query_text, redacted),
            ).fetchall()
            results[table].extend(dict(r) for r in rows)

    if contact_email:
        rows = conn.execute(
            "SELECT id, timestamp, query, product_category, jurisdiction, status, contact_email "
            "FROM escalation WHERE contact_email = ?",
            (contact_email,),
        ).fetchall()
        existing_ids = {r["id"] for r in results["escalation"]}
        results["escalation"].extend(dict(r) for r in rows if r["id"] not in existing_ids)

    return results


def access_report(query_text: Optional[str] = None, contact_email: Optional[str] = None) -> Dict[str, Any]:
    """Right to access: everything stored that is tied to a query the person
    typed and/or the contact email they gave at escalation time. At least
    one of the two must be supplied — this deliberately does not support
    'give me everything', which would be a data leak, not a privacy right."""
    if not query_text and not contact_email:
        raise ValueError("Provide query_text and/or contact_email to look up your own records.")

    conn = db.get_conn()
    matches = _find_matches(query_text, contact_email, conn)
    conn.close()

    total = sum(len(v) for v in matches.values())
    return {
        "matched_records": total,
        "records": matches,
        "note": (
            "Records are matched by exact query text (as typed, or as stored after PII "
            "redaction) and/or the contact email supplied at escalation time. This searches "
            "audit, feedback, and escalation logs only — it does not include connector "
            "consent/usage records, which are managed separately via /api/connectors."
        ),
    }


# ---------------------------------------------------------------------------
# Right to erasure
# ---------------------------------------------------------------------------
def erase(query_text: Optional[str] = None, contact_email: Optional[str] = None) -> Dict[str, int]:
    """Right to erasure: hard-deletes every row matched by access_report's
    same lookup. Deliberately requires the same non-empty input — no
    wildcard erasure endpoint."""
    if not query_text and not contact_email:
        raise ValueError("Provide query_text and/or contact_email to erase your own records.")

    conn = db.get_conn()
    matches = _find_matches(query_text, contact_email, conn)

    deleted = {"audit_log": 0, "feedback": 0, "escalation": 0}
    for table, rows in matches.items():
        for row in rows:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (row["id"],))
            deleted[table] += 1
    conn.commit()
    conn.close()
    logger.info("PRIVACY_ERASE deleted=%s", deleted)
    return deleted


# ---------------------------------------------------------------------------
# Consent Manager — DPDP Act, 2023 / DPDP Rules, 2025 envisage an
# independent, Data-Protection-Board-registered Consent Manager issuing
# standardised, revocable, purpose- and category-scoped consent artifacts.
#
# HONESTY NOTE up front: there is no public, integrable Consent Manager to
# call — Consent Managers must themselves be registered with the Data
# Protection Board, and as of this codebase there is no free sandbox for
# one. What this implements is a LOCAL REFERENCE IMPLEMENTATION of the
# consent-artifact lifecycle in the shape the framework specifies (scoped
# purpose + data categories, independent grant/revoke, optional expiry,
# a durable per-artifact id) — functioning as this app's own consent
# ledger rather than as a plug-in to a third-party registered Consent
# Manager. If/when a real registered Consent Manager exposes a public API,
# swapping this module's storage for a call to that API is a drop-in
# change; the request/grant/revoke/list surface below is written to match.
# ---------------------------------------------------------------------------
def request_consent(data_principal_ref: str, purpose: str, data_categories: List[str],
                     expires_in_days: Optional[int] = None) -> Dict[str, Any]:
    """Create a consent artifact in 'requested' state. `data_principal_ref`
    is whatever the caller uses to identify themselves (e.g. the contact
    email already used for escalation) — never a government ID, and never
    validated/looked-up here beyond being a non-empty string."""
    if not data_principal_ref or not data_principal_ref.strip():
        raise ValueError("data_principal_ref is required.")
    if not purpose or not purpose.strip():
        raise ValueError("purpose is required.")
    if not data_categories:
        raise ValueError("data_categories must list at least one category.")

    consent_id = f"consent_{secrets.token_hex(8)}"
    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO consent_artifacts (consent_id, data_principal_ref, purpose, data_categories, "
        "data_fiduciary, status, requested_at, granted_at, revoked_at, expires_at) "
        "VALUES (?, ?, ?, ?, 'SUTRADHARA', 'requested', ?, NULL, NULL, ?)",
        (consent_id, data_principal_ref.strip(), purpose.strip(), ",".join(data_categories), now,
         (datetime.datetime.utcnow() + datetime.timedelta(days=expires_in_days)).isoformat()
         if expires_in_days else None),
    )
    conn.commit()
    conn.close()
    return get_consent(consent_id)


def grant_consent(consent_id: str) -> Dict[str, Any]:
    """The data principal actually grants a previously-requested artifact.
    Kept as a separate step from request_consent so a request can be shown
    to the person (purpose + categories, in plain language) before they
    grant it — never auto-granted at request time."""
    existing = get_consent(consent_id)
    if existing is None:
        raise ValueError(f"No consent artifact '{consent_id}'.")
    if existing["status"] != "requested":
        raise ValueError(f"Consent '{consent_id}' is '{existing['status']}', not 'requested'.")

    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    conn.execute(
        "UPDATE consent_artifacts SET status = 'granted', granted_at = ? WHERE consent_id = ?",
        (now, consent_id),
    )
    conn.commit()
    conn.close()
    return get_consent(consent_id)


def revoke_consent(consent_id: str) -> Dict[str, Any]:
    """Revocation is always allowed regardless of current status (short of
    already revoked), mirroring connectors.py's revoke lifecycle — a right
    to withdraw consent must not itself be gate-kept."""
    existing = get_consent(consent_id)
    if existing is None:
        raise ValueError(f"No consent artifact '{consent_id}'.")
    if existing["status"] == "revoked":
        return existing

    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    conn.execute(
        "UPDATE consent_artifacts SET status = 'revoked', revoked_at = ? WHERE consent_id = ?",
        (now, consent_id),
    )
    conn.commit()
    conn.close()
    logger.info("CONSENT_REVOKE consent_id=%s", consent_id)
    return get_consent(consent_id)


def get_consent(consent_id: str) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT * FROM consent_artifacts WHERE consent_id = ?", (consent_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    result = dict(row)
    result["data_categories"] = result["data_categories"].split(",") if result["data_categories"] else []
    return result


def list_consents(data_principal_ref: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = db.get_conn()
    if data_principal_ref:
        rows = conn.execute(
            "SELECT * FROM consent_artifacts WHERE data_principal_ref = ? ORDER BY requested_at DESC",
            (data_principal_ref,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM consent_artifacts ORDER BY requested_at DESC").fetchall()
    conn.close()
    out = []
    for row in rows:
        r = dict(row)
        r["data_categories"] = r["data_categories"].split(",") if r["data_categories"] else []
        out.append(r)
    return out


def is_consent_valid(consent_id: str) -> bool:
    """Checks status AND expiry, auto-expiring a stale-but-still-'granted'
    row rather than trusting a status field that could be out of date."""
    consent = get_consent(consent_id)
    if consent is None or consent["status"] != "granted":
        return False
    if consent["expires_at"]:
        expires = datetime.datetime.fromisoformat(consent["expires_at"])
        if datetime.datetime.utcnow() > expires:
            conn = db.get_conn()
            conn.execute("UPDATE consent_artifacts SET status = 'expired' WHERE consent_id = ?", (consent_id,))
            conn.commit()
            conn.close()
            return False
    return True


# ---------------------------------------------------------------------------
# Significant Data Fiduciary-style obligations: DPIA register + breach
# register + Records of Processing Activities (ROPA). HONESTY NOTE: the
# DPDP Act reserves formal "Significant Data Fiduciary" status and its
# mandatory-DPIA/DPO obligations for entities the government specifically
# notifies as such — this prototype is not one. What follows is the same
# record-keeping DISCIPLINE those obligations require, offered voluntarily
# and openly rather than claimed as a certification this app doesn't hold.
# ---------------------------------------------------------------------------
def record_dpia(processing_activity: str, risk_level: str, reviewer: Optional[str] = None,
                 mitigations: Optional[str] = None) -> Dict[str, Any]:
    if risk_level not in ("low", "medium", "high"):
        raise ValueError("risk_level must be one of: low, medium, high")
    dpia_id = f"dpia_{secrets.token_hex(6)}"
    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO dpia_register (dpia_id, processing_activity, risk_level, reviewer, mitigations, "
        "conducted_at, status) VALUES (?, ?, ?, ?, ?, ?, 'completed')",
        (dpia_id, processing_activity, risk_level, reviewer, mitigations, now),
    )
    conn.commit()
    conn.close()
    return {"dpia_id": dpia_id, "processing_activity": processing_activity, "risk_level": risk_level,
            "reviewer": reviewer, "mitigations": mitigations, "conducted_at": now, "status": "completed"}


def list_dpias() -> List[Dict[str, Any]]:
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM dpia_register ORDER BY conducted_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


BREACH_NOTIFY_HOURS = int(os.getenv("SUTRADHARA_BREACH_NOTIFY_HOURS", "72"))


def report_breach(description: str, affected_categories: Optional[List[str]] = None,
                   severity: str = "unknown") -> Dict[str, Any]:
    if not description or not description.strip():
        raise ValueError("description is required.")
    breach_id = f"breach_{secrets.token_hex(6)}"
    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO breach_register (breach_id, detected_at, description, affected_categories, "
        "severity, status) VALUES (?, ?, ?, ?, ?, 'open')",
        (breach_id, now, description.strip(), ",".join(affected_categories or []), severity),
    )
    conn.commit()
    conn.close()
    logger.warning("BREACH_REPORTED breach_id=%s severity=%s", breach_id, severity)
    return get_breach(breach_id)


def _notify(breach_id: str, column: str) -> Dict[str, Any]:
    existing = get_breach(breach_id)
    if existing is None:
        raise ValueError(f"No breach '{breach_id}'.")
    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    conn.execute(f"UPDATE breach_register SET {column} = ? WHERE breach_id = ?", (now, breach_id))
    conn.commit()
    conn.close()
    return get_breach(breach_id)


def notify_board(breach_id: str) -> Dict[str, Any]:
    return _notify(breach_id, "board_notified_at")


def notify_principals(breach_id: str) -> Dict[str, Any]:
    return _notify(breach_id, "principals_notified_at")


def get_breach(breach_id: str) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM breach_register WHERE breach_id = ?", (breach_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    b = dict(row)
    b["affected_categories"] = b["affected_categories"].split(",") if b["affected_categories"] else []
    b["notification_clock"] = _notification_clock(b)
    return b


def _notification_clock(breach: Dict[str, Any]) -> Dict[str, Any]:
    detected = datetime.datetime.fromisoformat(breach["detected_at"])
    hours_elapsed = (datetime.datetime.utcnow() - detected).total_seconds() / 3600
    return {
        "hours_since_detection": round(hours_elapsed, 2),
        "threshold_hours": BREACH_NOTIFY_HOURS,
        "board_notification_overdue": breach.get("board_notified_at") is None and hours_elapsed > BREACH_NOTIFY_HOURS,
        "principal_notification_overdue": breach.get("principals_notified_at") is None and hours_elapsed > BREACH_NOTIFY_HOURS,
        "note": (
            f"Threshold ({BREACH_NOTIFY_HOURS}h, SUTRADHARA_BREACH_NOTIFY_HOURS) is this deployment's "
            "own policy clock, not a verified restatement of the DPDP Rules' exact notification "
            "deadline — confirm the current notified deadline for a real incident."
        ),
    }


def list_breaches() -> List[Dict[str, Any]]:
    conn = db.get_conn()
    rows = conn.execute("SELECT breach_id FROM breach_register ORDER BY detected_at DESC").fetchall()
    conn.close()
    return [get_breach(r["breach_id"]) for r in rows]


def log_processing_activity(purpose: str, data_categories: List[str], legal_basis: str,
                             retention_period_days: Optional[int] = None) -> Dict[str, Any]:
    """Append-only Records of Processing Activities entry."""
    if not purpose or not data_categories or not legal_basis:
        raise ValueError("purpose, data_categories, and legal_basis are all required.")
    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO processing_register (purpose, data_categories, legal_basis, retention_period_days, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (purpose, ",".join(data_categories), legal_basis, retention_period_days, now),
    )
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return {"entry_id": entry_id, "purpose": purpose, "data_categories": data_categories,
            "legal_basis": legal_basis, "retention_period_days": retention_period_days, "created_at": now}


def list_processing_activities() -> List[Dict[str, Any]]:
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM processing_register ORDER BY created_at DESC").fetchall()
    conn.close()
    out = []
    for row in rows:
        r = dict(row)
        r["data_categories"] = r["data_categories"].split(",") if r["data_categories"] else []
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Cross-border data transfer restrictions (DPDP Act, 2023, s.16) — the Act
# uses a NEGATIVE list model: transfers are allowed to any country EXCEPT
# ones the Central Government specifically notifies as restricted.
#
# HONESTY NOTE: as of this codebase, the Government of India has not
# published that notified restricted-country list, so the correct DEFAULT
# behaviour is "nothing blocked" — not a fabricated list of countries this
# app guesses might be restricted. What's real here: a configurable
# blocklist (SUTRADHARA_CROSS_BORDER_BLOCKLIST, comma-separated country
# names/codes) that a deployer can populate the moment such a list IS
# notified, and a real, logged decision + audit trail for every transfer
# check made against whatever list is configured.
# ---------------------------------------------------------------------------
def _blocklist() -> List[str]:
    raw = os.getenv("SUTRADHARA_CROSS_BORDER_BLOCKLIST", "")
    return [c.strip().lower() for c in raw.split(",") if c.strip()]


def check_transfer(destination_country: str, purpose: Optional[str] = None,
                    data_categories: Optional[List[str]] = None) -> Dict[str, Any]:
    if not destination_country or not destination_country.strip():
        raise ValueError("destination_country is required.")

    blocklist = _blocklist()
    blocked = destination_country.strip().lower() in blocklist
    decision = "blocked" if blocked else "allowed"
    reason = (
        f"'{destination_country}' is on the configured restricted-destination list."
        if blocked else
        "No restriction configured for this destination (DPDP s.16 negative list — "
        "see SUTRADHARA_CROSS_BORDER_BLOCKLIST if a country should be restricted)."
    )

    conn = db.get_conn()
    conn.execute(
        "INSERT INTO cross_border_transfer_log (timestamp, destination_country, purpose, data_categories, "
        "decision, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.datetime.utcnow().isoformat(), destination_country.strip(), purpose,
         ",".join(data_categories or []), decision, reason),
    )
    conn.commit()
    conn.close()
    return {"destination_country": destination_country.strip(), "decision": decision, "reason": reason}


def list_transfer_log() -> List[Dict[str, Any]]:
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM cross_border_transfer_log ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Compliance posture summary
# ---------------------------------------------------------------------------
def compliance_status() -> Dict[str, Any]:
    return {
        "data_minimization": {
            "implemented": True,
            "detail": "Free-text queries are scanned for emails/long digit runs and masked before being written to audit_log.",
        },
        "purpose_limitation": {
            "implemented": True,
            "detail": "Stored data is used only for audit, feedback, escalation, and evaluation-benchmark purposes — never sold or repurposed.",
        },
        "storage_limitation": {
            "implemented": True,
            "detail": f"Retention window is {DEFAULT_RETENTION_DAYS} days (SUTRADHARA_RETENTION_DAYS); POST /api/privacy/purge-expired hard-deletes anything older.",
        },
        "right_to_access": {"implemented": True, "endpoint": "POST /api/privacy/access"},
        "right_to_erasure": {"implemented": True, "endpoint": "POST /api/privacy/erase"},
        "consent_logging": {
            "implemented": True,
            "detail": "Paid-connector linking is explicit, timestamped, and revocable (see connectors.py). Escalation contact_email is supplied voluntarily by the user for callback purposes only.",
        },
        "consent_manager": {
            "implemented": "partial",
            "detail": (
                "A local reference implementation of the DPDP consent-artifact lifecycle "
                "(request/grant/revoke, purpose + category scoping, optional expiry) — see "
                "POST /api/privacy/consent/*. NOT integrated with a Data-Protection-Board-"
                "registered third-party Consent Manager; none is publicly integrable yet."
            ),
        },
        "significant_data_fiduciary_obligations": {
            "implemented": "partial",
            "detail": (
                "Real DPIA register (POST /api/privacy/dpia), breach register with a "
                "notification-clock (POST /api/privacy/breach), and a Records-of-Processing-"
                "Activities log (POST /api/privacy/ropa) exist and are queryable. This app has "
                "not been notified as a Significant Data Fiduciary and makes no claim to that "
                "formal status; a dedicated Data Protection Officer role is not modeled."
            ),
        },
        "cross_border_transfer_restrictions": {
            "implemented": "partial",
            "detail": (
                "POST /api/privacy/cross-border/check enforces and logs every transfer decision "
                "against a configurable blocklist (SUTRADHARA_CROSS_BORDER_BLOCKLIST). Default is "
                "empty because the Government of India has not yet notified a restricted-country "
                "list under DPDP s.16 — populate it the moment one is notified."
            ),
        },
        "not_implemented": [
            "Registered, government-recognised Consent Manager integration (no public API exists to integrate with).",
            "Formal Significant Data Fiduciary / Data Protection Officer designation (this app has not been notified as one).",
            "A government-notified cross-border restricted-country list (none published yet — the mechanism to enforce one exists).",
            "This is a prototype's data-governance scaffolding, not a legal compliance certification.",
        ],
    }
