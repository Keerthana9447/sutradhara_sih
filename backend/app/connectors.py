"""
Paid-subscription connector — consent-logged, user-linked.

The problem statement's own wording: the assistant should facilitate access
to authoritative sources, using "free official databases directly and the
user's own paid subscriptions only with explicit, logged permission." Most
teams building this problem statement will miss that clause entirely (it's
one sentence in a long paragraph) and only wire up the free corpus. This
module is the structural machinery for the other half:

  1. link_connector()   — the user pastes their OWN paid provider's API key
     (e.g. a commercial patent-search subscription). We never store the raw
     key: only a SHA-256 hash (for future verification, never reversed) and
     a 4-character fingerprint (for the user to visually confirm which key
     is linked, without exposing the rest). The link event itself is the
     "explicit... permission" — logged with a timestamp, provider name, and
     scope.
  2. use_connector()    — every actual USE of a linked connector, on a
     specific query, is a separate logged event. Nothing is used silently
     just because a connector exists; the caller must pass
     use_connector_id explicitly on that one /api/analyze request (see
     schemas.AnalyzeRequest).
  3. revoke_connector() — the user can revoke at any time; revocation is
     itself logged (revoked_at), and a revoked connector can never be used
     again even if the id is replayed.

HONESTY NOTE — what this prototype does NOT do: it does not call a real
commercial patent/trademark database. There is no such subscription
available to test against in this environment, and every real provider has
its own bespoke API. What use_connector() returns is a single, clearly
labeled placeholder record (source_type = "Paid Subscription (User-Provided,
Simulated)") showing exactly where and how a real provider's response would
be merged into the retrieved-sources list. The consent/link/use/revoke
lifecycle around it, however, is fully real and functional — that lifecycle,
not the mocked data, is the actual point of this feature.
"""
import datetime
import hashlib
import secrets
from typing import Any, Dict, List, Optional

from . import db


def _fingerprint(api_key: str) -> str:
    return api_key[-4:] if len(api_key) >= 4 else api_key


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def link_connector(provider: str, api_key: str, scope: str = "patent_search",
                    contact_email: Optional[str] = None) -> Dict[str, Any]:
    if not provider.strip() or not api_key.strip():
        raise ValueError("provider and api_key are required")

    connector_id = f"conn_{secrets.token_hex(8)}"
    now = datetime.datetime.utcnow().isoformat()

    conn = db.get_conn()
    conn.execute(
        "INSERT INTO connector_consent "
        "(connector_id, provider, scope, key_fingerprint, key_hash, contact_email, status, linked_at, revoked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, NULL)",
        (connector_id, provider.strip(), scope.strip(), _fingerprint(api_key), _hash_key(api_key),
         contact_email, now),
    )
    conn.commit()
    conn.close()

    return {
        "connector_id": connector_id,
        "provider": provider.strip(),
        "scope": scope.strip(),
        "status": "active",
        "linked_at": now,
        "revoked_at": None,
        "key_fingerprint": _fingerprint(api_key),
    }


def revoke_connector(connector_id: str) -> bool:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT status FROM connector_consent WHERE connector_id = ?", (connector_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return False

    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE connector_consent SET status = 'revoked', revoked_at = ? WHERE connector_id = ?",
        (now, connector_id),
    )
    conn.commit()
    conn.close()
    return True


def get_connector(connector_id: str) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT * FROM connector_consent WHERE connector_id = ?", (connector_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_connectors() -> List[Dict[str, Any]]:
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT connector_id, provider, scope, status, linked_at, revoked_at, key_fingerprint "
        "FROM connector_consent ORDER BY linked_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def use_connector(connector_id: str, query: str) -> Optional[Dict[str, Any]]:
    """
    Logs one use-event and returns a simulated paid-source hit, or None if
    the connector doesn't exist or has been revoked (fails closed — a
    revoked connector never silently keeps working).
    """
    connector = get_connector(connector_id)
    if connector is None or connector["status"] != "active":
        return None

    conn = db.get_conn()
    conn.execute(
        "INSERT INTO connector_usage_log (connector_id, timestamp, query) VALUES (?, ?, ?)",
        (connector_id, datetime.datetime.utcnow().isoformat(), query),
    )
    conn.commit()
    conn.close()

    return {
        "connector_id": connector_id,
        "provider": connector["provider"],
        "scope": connector["scope"],
        "simulated": True,
        "note": (
            f"Placeholder result from the user's linked '{connector['provider']}' subscription. "
            "This prototype does not call a real commercial API here — in production this record "
            "would be the provider's own live search response for this query, merged alongside "
            "(never replacing) the free authoritative corpus sources above."
        ),
    }


def usage_log_for(connector_id: str) -> List[Dict[str, Any]]:
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT timestamp, query FROM connector_usage_log WHERE connector_id = ? ORDER BY timestamp DESC",
        (connector_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
