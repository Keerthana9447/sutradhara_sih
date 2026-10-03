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
    """Hard-delete audit_log, feedback, escalation, idle chat-history rows and
    expired login tokens older than the retention window. Connector consent records are exempt: revocation
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

    # Chat history: whole conversations that have been idle past the window
    # (messages first, then their sessions). Accounts themselves are NOT
    # purged by age — an account exists until its owner deletes it.
    stale = [r["id"] for r in conn.execute(
        "SELECT id FROM chat_sessions WHERE updated_at < ?", (cutoff,)).fetchall()]
    msgs = 0
    for sid in stale:
        msgs += conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (sid,)).rowcount
        conn.execute("DELETE FROM chat_sessions WHERE id = ?", (sid,))
    deleted["chat_messages"] = msgs
    deleted["chat_sessions"] = len(stale)
    deleted["auth_sessions"] = conn.execute(
        "DELETE FROM auth_sessions WHERE expires_at < ?",
        (datetime.datetime.utcnow().isoformat(),)).rowcount
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
    """Look up legacy log records by exact query and/or escalation email.

    This helper is for trusted internal use only. An unauthenticated API
    caller must never choose either value as proof of ownership.
    """
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
            "consent/usage records (managed via /api/connectors) or signed-in account data such as chat "
            "history (use GET /api/privacy/account/export while signed in)."
        ),
    }


# ---------------------------------------------------------------------------
# Right to erasure
# ---------------------------------------------------------------------------
def erase(query_text: Optional[str] = None, contact_email: Optional[str] = None) -> Dict[str, int]:
    """Delete log records matched by access_report's lookup.

    This helper is for trusted internal use only. API routes must scope it to
    an authenticated account and must not treat caller-supplied query text as
    proof that the matched records belong to that caller.
    """
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
# Account-level rights — the logged-in user's own users / chat_sessions /
# chat_messages / auth_sessions rows, which access_report()/erase() above
# (keyed on query text or escalation email) never reached. The caller's
# identity comes from a verified token (app/auth.py), never from a
# client-supplied id.
# ---------------------------------------------------------------------------
def export_account(user_id: int) -> Dict[str, Any]:
    conn = db.get_conn()
    user = conn.execute("SELECT id, email, name, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        raise ValueError("No such account.")
    sessions = []
    for sess in conn.execute(
        "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall():
        msgs = conn.execute(
            "SELECT id, role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY id", (sess["id"],)
        ).fetchall()
        sessions.append({**dict(sess), "messages": [dict(m) for m in msgs]})
    escalations = conn.execute(
        "SELECT id, timestamp, query, product_category, jurisdiction, status FROM escalation WHERE contact_email = ?",
        (user["email"],),
    ).fetchall()
    dossiers = []
    for dossier in conn.execute(
        "SELECT * FROM formulation_dossiers WHERE user_id = ? ORDER BY created_at", (user_id,)
    ).fetchall():
        item = dict(dossier)
        item["history"] = [
            dict(event) for event in conn.execute(
                "SELECT event_type, payload_json, created_at FROM dossier_history WHERE dossier_id = ? ORDER BY id",
                (dossier["dossier_id"],),
            ).fetchall()
        ]
        dossiers.append(item)
    alerts = [
        dict(row) for row in conn.execute(
            "SELECT * FROM prahari_alerts WHERE user_id = ? ORDER BY created_at", (user_id,)
        ).fetchall()
    ]
    form7a_drafts = [
        dict(row) for row in conn.execute(
            "SELECT * FROM form7a_drafts WHERE user_id = ? ORDER BY created_at", (user_id,)
        ).fetchall()
    ]
    citizen_claims = [
        dict(row) for row in conn.execute(
            "SELECT claim_id, title, description, jurisdiction, category, status, submitted_at, verified_at, anchor_hash, anchor_simulated_at, anchor_note FROM citizen_claims WHERE user_id = ? ORDER BY submitted_at",
            (user_id,),
        ).fetchall()
    ] if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='citizen_claims'").fetchone() else []
    consent_accesses = [
        dict(row) for row in conn.execute(
            "SELECT consent_id, actor, accessed_at FROM consent_access_log WHERE actor = ? ORDER BY id",
            (f"user:{user_id}",),
        ).fetchall()
    ]
    consent_artifacts = []
    for consent in conn.execute(
        "SELECT consent_id, purpose, data_categories, status, requested_at, granted_at, revoked_at, expires_at "
        "FROM consent_artifacts WHERE data_principal_ref = ? ORDER BY requested_at",
        (user["email"],),
    ).fetchall():
        artifact = dict(consent)
        artifact["access_log"] = [
            dict(access) for access in conn.execute(
                "SELECT actor, accessed_at FROM consent_access_log WHERE consent_id = ? ORDER BY id",
                (consent["consent_id"],),
            ).fetchall()
        ]
        consent_artifacts.append(artifact)
    conn.close()
    return {
        "account": dict(user),
        "chat_sessions": sessions,
        "escalations": [dict(e) for e in escalations],
        "formulation_dossiers": dossiers,
        "prahari_alerts": alerts,
        "form7a_drafts": form7a_drafts,
        "citizen_claims": citizen_claims,
        "consent_accesses": consent_accesses,
        "consent_artifacts": consent_artifacts,
        "note": (
            "Password hashes and login tokens are deliberately not exported. Stored chat content is "
            "your own text as typed plus the generated answers; unlike audit_log it is not PII-redacted, "
            "because it exists to show you your own history."
        ),
    }


def delete_account(user_id: int) -> Dict[str, int]:
    """Hard-delete the account and everything tied to it. Real SQL DELETEs,
    children before parents (SQLite FKs are not cascading here)."""
    conn = db.get_conn()
    user = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        raise ValueError("No such account.")
    sids = [r["id"] for r in conn.execute("SELECT id FROM chat_sessions WHERE user_id = ?", (user_id,)).fetchall()]
    deleted = {"chat_messages": 0, "chat_sessions": len(sids)}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='citizen_claims'").fetchone():
        deleted["citizen_claims"] = conn.execute("DELETE FROM citizen_claims WHERE user_id = ?", (user_id,)).rowcount
    else:
        deleted["citizen_claims"] = 0
    for sid in sids:
        deleted["chat_messages"] += conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (sid,)).rowcount
    conn.execute("DELETE FROM chat_sessions WHERE user_id = ?", (user_id,))
    deleted["auth_sessions"] = conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,)).rowcount
    deleted["escalation"] = conn.execute("DELETE FROM escalation WHERE contact_email = ?", (user["email"],)).rowcount
    dossier_ids = [
        row["dossier_id"] for row in conn.execute(
            "SELECT dossier_id FROM formulation_dossiers WHERE user_id = ?", (user_id,)
        ).fetchall()
    ]
    deleted["dossier_history"] = 0
    for dossier_id in dossier_ids:
        deleted["dossier_history"] += conn.execute(
            "DELETE FROM dossier_history WHERE dossier_id = ?", (dossier_id,)
        ).rowcount
    deleted["formulation_dossiers"] = conn.execute(
        "DELETE FROM formulation_dossiers WHERE user_id = ?", (user_id,)
    ).rowcount
    deleted["form7a_drafts"] = conn.execute(
        "DELETE FROM form7a_drafts WHERE user_id = ?", (user_id,)
    ).rowcount
    deleted["prahari_alerts"] = conn.execute(
        "DELETE FROM prahari_alerts WHERE user_id = ?", (user_id,)
    ).rowcount
    deleted["consent_access_log"] = conn.execute(
        "DELETE FROM consent_access_log WHERE actor = ?", (f"user:{user_id}",)
    ).rowcount
    consent_ids = [
        row["consent_id"] for row in conn.execute(
            "SELECT consent_id FROM consent_artifacts WHERE data_principal_ref = ?", (user["email"],)
        ).fetchall()
    ]
    for consent_id in consent_ids:
        deleted["consent_access_log"] += conn.execute(
            "DELETE FROM consent_access_log WHERE consent_id = ?", (consent_id,)
        ).rowcount
    deleted["consent_artifacts"] = conn.execute(
        "DELETE FROM consent_artifacts WHERE data_principal_ref = ?", (user["email"],)
    ).rowcount
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    deleted["users"] = 1
    conn.commit()
    conn.close()
    logger.info("PRIVACY_ACCOUNT_DELETE user_id=%s deleted=%s", user_id, deleted)
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
    if row is None:
        conn.close()
        return None
    result = dict(row)
    result["data_categories"] = result["data_categories"].split(",") if result["data_categories"] else []
    result["access_log"] = [
        dict(access) for access in conn.execute(
            "SELECT actor, accessed_at FROM consent_access_log WHERE consent_id = ? ORDER BY id",
            (consent_id,),
        ).fetchall()
    ]
    conn.close()
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
    out = []
    for row in rows:
        r = dict(row)
        r["data_categories"] = r["data_categories"].split(",") if r["data_categories"] else []
        r["access_log"] = [
            dict(access) for access in conn.execute(
                "SELECT actor, accessed_at FROM consent_access_log WHERE consent_id = ? ORDER BY id",
                (r["consent_id"],),
            ).fetchall()
        ]
        out.append(r)
    conn.close()
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
            "detail": (
                f"Retention window is {DEFAULT_RETENTION_DAYS} days (SUTRADHARA_RETENTION_DAYS); "
                "POST /api/privacy/purge-expired hard-deletes anything older and requires the "
                "configured X-Privacy-Purge-Token scheduler secret."
            ),
        },
        "right_to_access": {
            "implemented": True,
            "endpoint": (
                "POST /api/privacy/access (authenticated account; only own escalation logs and account data); "
                "GET /api/privacy/account/export (own signed-in account and chat history)"
            ),
        },
        "right_to_erasure": {
            "implemented": True,
            "endpoint": (
                "POST /api/privacy/erase (authenticated account; own escalation logs); "
                "DELETE /api/privacy/account (own account, chat history, login tokens, and escalations)"
            ),
        },
        "account_security": {
            "implemented": "partial",
            "detail": (
                "Passwords: salted PBKDF2-HMAC-SHA256 (stdlib); legacy single-round SHA-256 hashes are rejected "
                "and require a trusted password reset. Login tokens are stored hashed, expiring, and revocable "
                "on sign-out. Every chat/account route derives identity from the token server-side. Sign-in/up "
                "are rate-limited in-process (single-instance only). NOT implemented: email verification, "
                "self-service password reset, MFA, or a shared rate-limit store for multi-instance deployments."
            ),
        },
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
        "recognised_ai_application_standards": {
            "implemented": "partial",
            "detail": (
                "See ai_standards_alignment() / GET /api/privacy/ai-standards-alignment for a real, "
                "honest self-assessment against the NIST AI Risk Management Framework 1.0 — this is a "
                "correspondence review, not a certification (the NIST AI RMF has no certification scheme)."
            ),
        },
    }


# ---------------------------------------------------------------------------
# "Recognised AI-application standards" alignment — the PS's other named
# requirement alongside DPDP, which nothing in this codebase had previously
# attempted at all.
#
# HONESTY NOTE: the NIST AI Risk Management Framework 1.0 (NIST AI 100-1,
# Jan 2023) is voluntary guidance, not a certifiable standard — "the NIST AI
# RMF is voluntary guidance and is not a certifiable standard, so there is
# no NIST AI RMF certificate" is true of the framework itself, not a
# limitation of this project. What follows is a genuine, function-by-
# function correspondence review: for each of the framework's four real
# functions (Govern/Map/Measure/Manage) and its seven named trustworthiness
# characteristics, it names the SPECIFIC module/endpoint that addresses it,
# or says plainly that nothing here addresses it yet. It is not a score,
# not a badge, and not a claim of compliance — a self-assessment against a
# named public framework, which is what "aligned to ... recognised
# AI-application standards" can honestly mean for a project at this stage.
# ---------------------------------------------------------------------------
def ai_standards_alignment() -> Dict[str, Any]:
    return {
        "framework": "NIST AI Risk Management Framework 1.0 (NIST AI 100-1, January 2023)",
        "framework_note": (
            "Voluntary guidance published by the US National Institute of Standards and Technology; "
            "there is no certification scheme for it, so nothing below is a compliance claim — it is "
            "this project's own correspondence review against the framework's public functions and "
            "trustworthiness characteristics."
        ),
        "functions": {
            "govern": {
                "nist_description": "Policies, accountability structures, and organizational culture for AI risk management.",
                "addressed_by": [
                    "privacy.compliance_status() — a single, queryable statement of what data-governance obligations are met, partial, or open",
                    "app/db.py's dpia_register, breach_register, and processing_register (ROPA) tables — real, append-only accountability records, not just a policy document",
                    "schemas.py's default disclaimer field ('Information, not legal advice.') — a standing accountability statement attached to every response",
                ],
            },
            "map": {
                "nist_description": "Establishing the context, purpose, and risk tolerance of a specific AI system.",
                "addressed_by": [
                    "classifier.py's explicit formulation-category taxonomy — the system's scope and decision context are named, not implicit",
                    "The jurisdiction toggle (README §3.4) — a declared boundary on what context an answer is valid in",
                    "The deliberate 'abstain and cite rather than guess' design (README §1) — an explicit, documented risk-tolerance decision, not a default left unstated",
                ],
            },
            "measure": {
                "nist_description": "Analyzing and tracking identified risks using qualitative and quantitative methods.",
                "addressed_by": [
                    "GET /api/eval/benchmark (app/eval_runner.py) — a live-run accuracy/citation-correctness/abstention benchmark, not a claimed number",
                    "The jurisdiction-isolation invariant test — a concrete, checked measurement, not an aspiration",
                    "ConfidenceMeter — a per-answer measurement surfaced to the end user, not just logged internally",
                ],
            },
            "manage": {
                "nist_description": "Prioritizing, treating, monitoring, and responding to identified risks.",
                "addressed_by": [
                    "EscalationModal / the escalation table — the concrete treatment path when the system's own confidence is low",
                    "purge_expired() — active treatment of a data-retention risk, not passive logging",
                    "report_breach()/notify_board()/notify_principals() with a real notification clock — incident response, not just an incident log",
                ],
            },
        },
        "trustworthiness_characteristics": {
            "validity_and_reliability": {"addressed": True, "detail": "GET /api/eval/benchmark measures this directly and repeatably."},
            "safety": {"addressed": True, "detail": "Abstain-rather-than-guess design + standing disclaimer; never presents an unsourced answer as authoritative."},
            "security_and_resilience": {"addressed": "partial", "detail": "PII redaction, retention purge, DPDP data-governance layer; no independent security audit or penetration test has been performed."},
            "accountability_and_transparency": {"addressed": True, "detail": "audit_log, ROPA, mandatory citations, and compliance_status() itself being queryable rather than asserted in prose."},
            "explainability_and_interpretability": {"addressed": True, "detail": "The DAG orchestration (app/dag.py) is an explicit, inspectable graph of nodes rather than an opaque agent loop — every answer's path through classify/route/retrieve/cite is reconstructable."},
            "privacy_enhanced": {"addressed": True, "detail": "The whole of privacy.py — minimization, purge, consent, DPIA, breach register, ROPA, cross-border checks."},
            "fair_with_harmful_bias_managed": {
                "addressed": "partial",
                "detail": (
                    "See app/bias_audit.py / GET /api/privacy/bias-audit for two real, narrow checks: a static "
                    "scan of this app's own templates for gendered pronouns (currently clean), and a dynamic "
                    "persona-invariance check that runs the real classify/route/retrieve pipeline on matched "
                    "query sets varying only a stated persona (gender-coded name, individual-vs-corporation, "
                    "region-coded name). This is NOT a full fairness audit — no protected-characteristic outcome "
                    "study exists or can exist here, since this app collects no demographic data about who is "
                    "asking. The audit HONESTLY REPORTS a real finding rather than hiding it: the "
                    "individual-vs-corporation axis shows the retrieved document SET drifting (not just "
                    "re-ranking) between 'a small rural farmer' and 'an R&D head at a pharmaceutical corporation' "
                    "asking the identical underlying legal question, because incidental vocabulary in each framing "
                    "('family'/'passed down' vs. 'pharmaceutical'/'R&D') overlaps with unrelated corpus documents "
                    "(Plant Variety Protection vs. the Pharmacopoeia entry). The other two axes tested showed no "
                    "drift. This is disclosed as a known limitation of the TF-IDF retrieval layer, not fixed by "
                    "reweighting retrieval broadly, since that is a larger change than this audit's scope."
                ),
            },
        },
    }
