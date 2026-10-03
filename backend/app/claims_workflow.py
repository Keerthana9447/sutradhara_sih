"""
Citizen Claims Submission Workflow — /api/v1/claims

A citizen can submit a formulated IP claim (description + supporting metadata)
into the system for tracking.  The claim lifecycle follows a three-stage
progression:

  Pending -> Verified -> Blockchain Anchored

Honesty note: the Blockchain Anchored stage is a simulated SHA-256 hash
commitment recorded in the local database.  It is NOT an actual on-chain
write to any public blockchain in this prototype.  The hash is real; the
chain write is simulated — this is stated explicitly in every response that
reaches that stage.
"""

import hashlib
import datetime
import json
import secrets
import logging
from typing import Any, Dict, List, Optional
from . import db

logger = logging.getLogger("ip_sakti.claims")

STATUS_PENDING   = "Pending"
STATUS_VERIFIED  = "Verified"
STATUS_ANCHORED  = "Blockchain Anchored"


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _conn():
    return db.get_conn()


def _ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS citizen_claims (
            claim_id     TEXT PRIMARY KEY,
            user_id      INTEGER,
            title        TEXT NOT NULL,
            description  TEXT NOT NULL,
            jurisdiction TEXT NOT NULL DEFAULT 'India',
            category     TEXT,
            status       TEXT NOT NULL DEFAULT 'Pending',
            submitted_at TEXT NOT NULL,
            verified_at  TEXT,
            anchor_hash  TEXT,
            anchor_simulated_at TEXT,
            anchor_note  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_citizen_claims_user
            ON citizen_claims(user_id);
        CREATE INDEX IF NOT EXISTS idx_citizen_claims_status
            ON citizen_claims(status);
    """)
    conn.commit()


def submit_claim(
    title: str,
    description: str,
    jurisdiction: str = "India",
    category: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a new claim in Pending state."""
    claim_id = "CLM-" + secrets.token_hex(8).upper()
    now = _now()
    conn = _conn()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO citizen_claims
           (claim_id, user_id, title, description, jurisdiction, category, status, submitted_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (claim_id, user_id, title, description, jurisdiction, category, STATUS_PENDING, now),
    )
    conn.commit()
    conn.close()
    return get_claim(claim_id)


def get_claim(claim_id: str) -> Optional[Dict[str, Any]]:
    conn = _conn()
    _ensure_tables(conn)
    row = conn.execute(
        "SELECT * FROM citizen_claims WHERE claim_id=?", (claim_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_claims(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    conn = _conn()
    _ensure_tables(conn)
    query = "SELECT * FROM citizen_claims WHERE 1=1"
    params: list = []
    if user_id is not None:
        query += " AND user_id=?"
        params.append(user_id)
    if status:
        query += " AND status=?"
        params.append(status)
    query += " ORDER BY submitted_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def verify_claim(claim_id: str) -> Dict[str, Any]:
    """Advance a Pending claim to Verified (admin/system action)."""
    conn = _conn()
    _ensure_tables(conn)
    row = conn.execute(
        "SELECT * FROM citizen_claims WHERE claim_id=?", (claim_id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Claim {claim_id} not found")
    if row["status"] != STATUS_PENDING:
        conn.close()
        raise ValueError(f"Claim must be Pending to verify; current status: {row['status']}")
    now = _now()
    conn.execute(
        "UPDATE citizen_claims SET status=?, verified_at=? WHERE claim_id=?",
        (STATUS_VERIFIED, now, claim_id),
    )
    conn.commit()
    conn.close()
    return get_claim(claim_id)


def anchor_claim(claim_id: str) -> Dict[str, Any]:
    """
    Advance a Verified claim to Blockchain Anchored.

    HONESTY NOTE: In this prototype the 'blockchain' anchor is a SHA-256
    hash of the claim content stored in the local database.  It is NOT an
    actual on-chain write.  The hash is deterministic and auditable; the
    chain write is simulated.  This is stated in the anchor_note field of
    every anchored claim.
    """
    conn = _conn()
    _ensure_tables(conn)
    row = conn.execute(
        "SELECT * FROM citizen_claims WHERE claim_id=?", (claim_id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Claim {claim_id} not found")
    if row["status"] != STATUS_VERIFIED:
        conn.close()
        raise ValueError(f"Claim must be Verified to anchor; current: {row['status']}")

    payload = json.dumps({
        "claim_id": row["claim_id"],
        "title": row["title"],
        "description": row["description"],
        "submitted_at": row["submitted_at"],
        "verified_at": row["verified_at"],
    }, sort_keys=True)
    anchor_hash = "0x" + hashlib.sha256(payload.encode()).hexdigest()
    now = _now()
    anchor_note = (
        "Simulated blockchain anchor — SHA-256 of claim content recorded locally. "
        "Not an actual on-chain transaction. Prototype / hackathon demo mode."
    )
    conn.execute(
        """UPDATE citizen_claims
           SET status=?, anchor_hash=?, anchor_simulated_at=?, anchor_note=?
           WHERE claim_id=?""",
        (STATUS_ANCHORED, anchor_hash, now, anchor_note, claim_id),
    )
    conn.commit()
    conn.close()
    return get_claim(claim_id)
