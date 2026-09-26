import sqlite3
import os
import json
import datetime
from typing import Optional, List, Dict, Any

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ip_sakti.db")


def get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            query TEXT NOT NULL,
            jurisdiction TEXT,
            category TEXT,
            confidence REAL,
            abstained INTEGER,
            sources_json TEXT
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            query TEXT NOT NULL,
            answer_id TEXT,
            rating INTEGER NOT NULL,
            comment TEXT
        );

        CREATE TABLE IF NOT EXISTS escalation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            query TEXT NOT NULL,
            product_category TEXT,
            jurisdiction TEXT,
            relevant_ip_area TEXT,
            retrieved_sources TEXT,
            contact_email TEXT,
            status TEXT DEFAULT 'open'
        );

        CREATE TABLE IF NOT EXISTS connector_consent (
            connector_id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            scope TEXT NOT NULL,
            key_fingerprint TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            contact_email TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            linked_at TEXT NOT NULL,
            revoked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS connector_usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connector_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            query TEXT NOT NULL
        );

        -- DPDP Consent Manager reference implementation (privacy.py). Each
        -- row is one consent ARTIFACT in the shape the DPDP Act/Rules
        -- envisage a registered Consent Manager issuing: a purpose- and
        -- category-scoped, expirable, independently revocable grant tied to
        -- one data principal. This process is the fiduciary AND, honestly,
        -- its own local Consent Manager here — see privacy.py docstring.
        CREATE TABLE IF NOT EXISTS consent_artifacts (
            consent_id TEXT PRIMARY KEY,
            data_principal_ref TEXT NOT NULL,
            purpose TEXT NOT NULL,
            data_categories TEXT NOT NULL,
            data_fiduciary TEXT NOT NULL DEFAULT 'SUTRADHARA',
            status TEXT NOT NULL DEFAULT 'requested',
            requested_at TEXT NOT NULL,
            granted_at TEXT,
            revoked_at TEXT,
            expires_at TEXT
        );

        -- Significant Data Fiduciary-style obligations: a real, queryable
        -- DPIA (Data Protection Impact Assessment) register instead of an
        -- undocumented claim of having done one.
        CREATE TABLE IF NOT EXISTS dpia_register (
            dpia_id TEXT PRIMARY KEY,
            processing_activity TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            reviewer TEXT,
            mitigations TEXT,
            conducted_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed'
        );

        -- Breach register with a real notification-clock computation
        -- (DPDP Rules require intimating the Data Protection Board and
        -- affected data principals "without delay"; this module tracks the
        -- clock honestly rather than claiming automatic notification).
        CREATE TABLE IF NOT EXISTS breach_register (
            breach_id TEXT PRIMARY KEY,
            detected_at TEXT NOT NULL,
            description TEXT NOT NULL,
            affected_categories TEXT,
            severity TEXT NOT NULL DEFAULT 'unknown',
            board_notified_at TEXT,
            principals_notified_at TEXT,
            status TEXT NOT NULL DEFAULT 'open'
        );

        -- Records of Processing Activities (ROPA) — a real, append-only log
        -- of what personal data is processed, why, and for how long.
        CREATE TABLE IF NOT EXISTS processing_register (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            purpose TEXT NOT NULL,
            data_categories TEXT NOT NULL,
            legal_basis TEXT NOT NULL,
            retention_period_days INTEGER,
            created_at TEXT NOT NULL
        );

        -- Cross-border transfer decisions, logged whether allowed or
        -- blocked, against a configurable destination-country list.
        CREATE TABLE IF NOT EXISTS cross_border_transfer_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            destination_country TEXT NOT NULL,
            purpose TEXT,
            data_categories TEXT,
            decision TEXT NOT NULL,
            reason TEXT
        );

        -- Corpus auto-refresh state (corpus_freshness.py): the last known
        -- content hash fetched from each document's live source_url, so a
        -- later fetch can detect drift. Storing this in sqlite (rather than
        -- a second JSON side-file) keeps it inside the same
        -- purge/access/erase-aware persistence layer as everything else.
        CREATE TABLE IF NOT EXISTS corpus_refresh_state (
            doc_id TEXT PRIMARY KEY,
            last_known_hash TEXT,
            last_checked_at TEXT,
            last_changed_at TEXT,
            pending_diff TEXT,
            pending_hash TEXT,
            status TEXT NOT NULL DEFAULT 'unchecked'
        );

        -- Retention-purge (privacy.py) and freshness dashboards both filter
        -- by timestamp; index it once rather than full-scanning these
        -- tables on every purge run.
        CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp);
        CREATE INDEX IF NOT EXISTS idx_escalation_timestamp ON escalation(timestamp);
        """
    )
    conn.commit()
    conn.close()


def log_audit(query: str, jurisdiction: str, category: str, confidence: float,
              abstained: bool, sources: List[Dict[str, Any]]):
    # Lazy import (not module-level) to avoid a circular import: privacy.py
    # itself imports this module for its purge/access/erase operations. By
    # call time both modules are fully loaded, so this is safe. See
    # privacy.py's docstring for what redaction does and does not cover.
    from . import privacy
    stored_query = privacy.redact_pii(query)

    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log (timestamp, query, jurisdiction, category, confidence, abstained, sources_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.datetime.utcnow().isoformat(),
            stored_query, jurisdiction, category, confidence, int(abstained),
            json.dumps([s.get("id") for s in sources]),
        ),
    )
    conn.commit()
    conn.close()


def log_feedback(query: str, answer_id: Optional[str], rating: int, comment: Optional[str]):
    conn = get_conn()
    conn.execute(
        "INSERT INTO feedback (timestamp, query, answer_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
        (datetime.datetime.utcnow().isoformat(), query, answer_id, rating, comment),
    )
    conn.commit()
    conn.close()


def log_escalation(query: str, product_category: Optional[str], jurisdiction: Optional[str],
                    relevant_ip_area: Optional[List[str]], retrieved_sources: Optional[List[str]],
                    contact_email: Optional[str]) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO escalation (timestamp, query, product_category, jurisdiction, relevant_ip_area, "
        "retrieved_sources, contact_email) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.datetime.utcnow().isoformat(), query, product_category, jurisdiction,
            json.dumps(relevant_ip_area or []), json.dumps(retrieved_sources or []), contact_email,
        ),
    )
    conn.commit()
    escalation_id = cur.lastrowid
    conn.close()
    return escalation_id


def get_eval_summary() -> Dict[str, Any]:
    """Simple developer/admin evaluation panel data — real counts only, never fabricated."""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    abstained = conn.execute("SELECT COUNT(*) c FROM audit_log WHERE abstained=1").fetchone()["c"]
    avg_conf_row = conn.execute("SELECT AVG(confidence) a FROM audit_log").fetchone()
    avg_conf = avg_conf_row["a"]
    conn.close()

    if total == 0:
        return {
            "total_queries": 0,
            "safe_abstention_rate": None,
            "average_confidence": None,
            "note": "Evaluation pending — no queries logged yet.",
        }

    return {
        "total_queries": total,
        "safe_abstention_rate": round(abstained / total, 2) if total else None,
        "average_confidence": round(avg_conf, 2) if avg_conf is not None else None,
        "note": (
            "Figures reflect real logged interactions in this session/database only. "
            "For automatically computed classification accuracy, citation hit rate, "
            "abstention accuracy, and the jurisdiction-isolation / citation-integrity "
            "hard invariants against a labeled test set, see GET /api/eval/benchmark "
            "(app/eval_runner.py, data/eval_dataset.json)."
        ),
    }
