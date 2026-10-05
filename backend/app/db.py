import sqlite3
import os
import json
import datetime
import hashlib
import secrets
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
            sources_json TEXT,
            corpus_snapshot_json TEXT NOT NULL DEFAULT '{}'
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
            key_ciphertext TEXT,
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

        CREATE TABLE IF NOT EXISTS consent_access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consent_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            accessed_at TEXT NOT NULL,
            FOREIGN KEY (consent_id) REFERENCES consent_artifacts(consent_id)
        );

        CREATE TABLE IF NOT EXISTS formulation_dossiers (
            dossier_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            ingredients_json TEXT NOT NULL,
            sourcing_type TEXT NOT NULL,
            indication TEXT NOT NULL,
            target_market TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            classification_json TEXT,
            mapping_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS dossier_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dossier_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (dossier_id) REFERENCES formulation_dossiers(dossier_id)
        );

        CREATE TABLE IF NOT EXISTS prahari_alerts (
            alert_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            filing_number TEXT NOT NULL,
            title TEXT NOT NULL,
            abstract TEXT NOT NULL,
            publication_date TEXT NOT NULL,
            stream TEXT NOT NULL,
            source_url TEXT,
            risk_score INTEGER NOT NULL,
            risk_matches_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS form7a_drafts (
            form_id TEXT PRIMARY KEY,
            alert_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            form_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (alert_id) REFERENCES prahari_alerts(alert_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
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

        -- GI Registry real-data cache (app/gi_registry.py). Populated by
        -- fetching and parsing the officially published, no-CAPTCHA
        -- "Total Registered GI details of GI Application in India" PDF from
        -- ipindia.gov.in — see that module's docstring for exactly why this
        -- one India registry can honestly go beyond a deep link while
        -- patents/trademarks (InPASS, CAPTCHA-gated) cannot.
        CREATE TABLE IF NOT EXISTS gi_registry_cache (
            sr_no TEXT,
            application_no TEXT,
            name TEXT NOT NULL,
            goods_category TEXT,
            state TEXT,
            source_pdf_url TEXT,
            fetched_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_gi_registry_name ON gi_registry_cache(name);

        -- One-row status record for the GI cache above: when it was last
        -- successfully rebuilt, from which PDF, and how many rows resulted
        -- — so a failed refresh never silently wipes a working cache and
        -- the freshness of what's being searched is always inspectable.
        CREATE TABLE IF NOT EXISTS gi_registry_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            source_pdf_url TEXT,
            entry_count INTEGER,
            built_at TEXT,
            parse_method TEXT,
            low_confidence INTEGER DEFAULT 0
        );

        -- Retention-purge (privacy.py) and freshness dashboards both filter
        -- by timestamp; index it once rather than full-scanning these
        -- tables on every purge run.
        CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp);
        CREATE INDEX IF NOT EXISTS idx_escalation_timestamp ON escalation(timestamp);

        -- ---------------------------------------------------------------
        -- Auth (Sign Up / Sign In)
        -- ---------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        -- ---------------------------------------------------------------
        -- Chat history — one session groups many Q-and-A turns
        -- ---------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT 'New conversation',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,           -- 'user' | 'assistant'
            content TEXT NOT NULL,        -- query text or JSON-encoded result
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        );

        -- Login tokens. Only a SHA-256 of the token is stored, so a copy of
        -- this database cannot be replayed as live sessions; rows expire.
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
        """
    )
    connector_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(connector_consent)").fetchall()
    }
    if "key_ciphertext" not in connector_columns:
        conn.execute("ALTER TABLE connector_consent ADD COLUMN key_ciphertext TEXT")
    audit_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(audit_log)").fetchall()
    }
    if "corpus_snapshot_json" not in audit_columns:
        conn.execute("ALTER TABLE audit_log ADD COLUMN corpus_snapshot_json TEXT NOT NULL DEFAULT '{}'")
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
        "INSERT INTO audit_log (timestamp, query, jurisdiction, category, confidence, abstained, sources_json, corpus_snapshot_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.datetime.utcnow().isoformat(),
            stored_query, jurisdiction, category, confidence, int(abstained),
            json.dumps([s.get("id") for s in sources]),
            json.dumps({
                str(s.get("id")): str(s.get("version_date", "unknown"))
                for s in sources if s.get("id")
            }, sort_keys=True),
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


# ==========================================================================
# Auth helpers
# ==========================================================================

_PBKDF2_ITERATIONS = 240_000
_PBKDF2_PREFIX = "pbkdf2_sha256$"


def _hash_password(password: str, salt: str, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Salted PBKDF2-HMAC-SHA256 (stdlib only, no new dependency). Stored as
    'pbkdf2_sha256$<iterations>$<hex>' so the cost can be raised later
    without invalidating existing rows."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"{_PBKDF2_PREFIX}{iterations}${dk.hex()}"


def _verify_password(password: str, salt: str, stored: str) -> bool:
    if stored.startswith(_PBKDF2_PREFIX):
        try:
            iterations = int(stored.split("$")[1])
        except (IndexError, ValueError):
            return False
        return secrets.compare_digest(_hash_password(password, salt, iterations), stored)
    # Legacy single-round hashes are deliberately no longer accepted. They
    # must be reset through a trusted administrative process; accepting one
    # and upgrading it at sign-in still leaves dormant rows cheap to crack.
    _hash_password(password, "0" * 32)
    return False


def create_user(email: str, name: str, password: str) -> Dict[str, Any]:
    """Create a new user. Returns the user dict or raises ValueError on duplicate email."""
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    now = datetime.datetime.utcnow().isoformat()
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, name, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)",
            (email.lower().strip(), name.strip(), pw_hash, salt, now),
        )
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("An account with that email already exists.")
    conn.close()
    return {"id": user_id, "email": email.lower().strip(), "name": name.strip()}


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Return a user only when a PBKDF2 password hash verifies."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, email, name, password_hash, salt FROM users WHERE email = ?",
        (email.lower().strip(),),
    ).fetchone()
    if row is None:
        conn.close()
        _hash_password(password, "0" * 32)  # comparable latency for unknown accounts
        return None
    if not _verify_password(password, row["salt"], row["password_hash"]):
        conn.close()
        return None
    conn.close()
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


# ==========================================================================
# Login tokens (persisted, hashed, expiring)
# ==========================================================================
SESSION_TTL_DAYS = int(os.getenv("SUTRADHARA_SESSION_TTL_DAYS", "7"))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_auth_session(user_id: int) -> str:
    """Issue an opaque token and persist only its hash."""
    token = secrets.token_urlsafe(32)
    now = datetime.datetime.utcnow()
    expires = now + datetime.timedelta(days=SESSION_TTL_DAYS)
    conn = get_conn()
    conn.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_token_hash(token), user_id, now.isoformat(), expires.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Resolve a token to its user, or None if unknown/expired (expired rows
    are deleted on sight)."""
    if not token:
        return None
    conn = get_conn()
    row = conn.execute("SELECT user_id, expires_at FROM auth_sessions WHERE token_hash = ?",
                       (_token_hash(token),)).fetchone()
    if row is None:
        conn.close()
        return None
    if row["expires_at"] < datetime.datetime.utcnow().isoformat():
        conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_token_hash(token),))
        conn.commit()
        conn.close()
        return None
    conn.close()
    return get_user_by_id(row["user_id"])


def delete_auth_session(token: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_token_hash(token),))
    conn.commit()
    conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, email, name FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


# ==========================================================================
# Chat-history helpers
# ==========================================================================

def create_chat_session(user_id: int, title: str = "New conversation") -> Dict[str, Any]:
    now = datetime.datetime.utcnow().isoformat()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO chat_sessions (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (user_id, title, now, now),
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return {"id": session_id, "user_id": user_id, "title": title, "created_at": now, "updated_at": now}


def get_chat_sessions(user_id: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_chat_session(session_id: int, user_id: int) -> bool:
    conn = get_conn()
    # Verify ownership before deleting
    row = conn.execute(
        "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)
    ).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return True


def rename_chat_session(session_id: int, user_id: int, title: str) -> bool:
    now = datetime.datetime.utcnow().isoformat()
    conn = get_conn()
    cur = conn.execute(
        "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (title, now, session_id, user_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def add_chat_message(session_id: int, role: str, content: str) -> Dict[str, Any]:
    """role must be 'user' or 'assistant'. content is plain text or JSON string."""
    now = datetime.datetime.utcnow().isoformat()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, now),
    )
    # Also bump updated_at on the parent session
    conn.execute(
        "UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id)
    )
    conn.commit()
    msg_id = cur.lastrowid
    conn.close()
    return {"id": msg_id, "session_id": session_id, "role": role, "content": content, "created_at": now}


def get_chat_messages(session_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
    """Returns messages for the session, or None if session doesn't belong to user_id."""
    conn = get_conn()
    session = conn.execute(
        "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)
    ).fetchone()
    if session is None:
        conn.close()
        return None
    rows = conn.execute(
        "SELECT id, role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def session_belongs_to(session_id: int, user_id: int) -> bool:
    """Ownership check used before writing to a chat session."""
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM chat_sessions WHERE id = ? AND user_id = ?",
                       (session_id, user_id)).fetchone()
    conn.close()
    return row is not None
