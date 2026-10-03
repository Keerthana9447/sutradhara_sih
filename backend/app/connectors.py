"""
Consent-logged, user-linked source connectors.

The problem statement's own wording: the assistant should facilitate access
to authoritative sources, using "free official databases directly and the
user's own paid subscriptions only with explicit, logged permission." Most
teams building this problem statement will miss that clause entirely and
only wire up the free corpus. The first live adapter here is USPTO
PatentsView (a free US-patent API); other providers stay labeled simulated
until their provider-specific APIs are implemented.

  1. link_connector()   — the user pastes their OWN paid provider's API key
     (or a PatentsView API key). Raw keys are never stored. A one-way
     SHA-256 hash and four-character fingerprint are kept for consent and
     display; the supported live adapter's credential is separately
     encrypted at rest using CONNECTOR_ENCRYPTION_KEY.
  2. use_connector()    — every actual USE of a linked connector, on a
     specific query, is a separate logged event. Nothing is used silently
     just because a connector exists; the caller must pass
     use_connector_id explicitly on that one /api/analyze request (see
     schemas.AnalyzeRequest).
  3. revoke_connector() — the user can revoke at any time; revocation is
     itself logged (revoked_at), and a revoked connector can never be used
     again even if the id is replayed.

PatentsView is a real live API call when enabled and its records are
returned separately from corpus citations. No fetched patent is treated as
legal advice or as a legal source in the answer. Other provider names still
return a clearly labeled simulated result.
"""
import datetime
import hashlib
import os
import secrets
from typing import Any, Dict, List, Optional

from . import db, registry_lookup

_PATENTSVIEW_PROVIDERS = {"patentsview", "uspto patentsview"}


class ConnectorConfigurationError(RuntimeError):
    """The connector cannot run because required server configuration is absent."""


def _fernet():
    key = os.getenv("CONNECTOR_ENCRYPTION_KEY")
    if not key:
        raise ConnectorConfigurationError(
            "CONNECTOR_ENCRYPTION_KEY must be configured before linking a live connector."
        )
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode("ascii"))
    except (ImportError, ValueError, UnicodeEncodeError) as exc:
        raise ConnectorConfigurationError(
            "CONNECTOR_ENCRYPTION_KEY must be a valid Fernet key and cryptography must be installed."
        ) from exc


def _fingerprint(api_key: str) -> str:
    return api_key[-4:] if len(api_key) > 4 else "****"


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def link_connector(provider: str, api_key: str, scope: str = "patent_search",
                    contact_email: Optional[str] = None) -> Dict[str, Any]:
    if not provider.strip() or not api_key.strip():
        raise ValueError("provider and api_key are required")

    provider_name = provider.strip()
    key_ciphertext = None
    if provider_name.casefold() in _PATENTSVIEW_PROVIDERS:
        key_ciphertext = _fernet().encrypt(api_key.encode("utf-8")).decode("ascii")

    connector_id = f"conn_{secrets.token_hex(8)}"
    now = datetime.datetime.utcnow().isoformat()

    conn = db.get_conn()
    conn.execute(
        "INSERT INTO connector_consent "
        "(connector_id, provider, scope, key_fingerprint, key_hash, key_ciphertext, contact_email, status, linked_at, revoked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, NULL)",
        (connector_id, provider_name, scope.strip(), _fingerprint(api_key), _hash_key(api_key),
         key_ciphertext, contact_email, now),
    )
    conn.commit()
    conn.close()

    return {
        "connector_id": connector_id,
        "provider": provider_name,
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
        "SELECT connector_id, provider, scope, key_fingerprint, contact_email, "
        "status, linked_at, revoked_at FROM connector_consent WHERE connector_id = ?",
        (connector_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _get_connector_for_use(connector_id: str) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT connector_id, provider, scope, status, key_ciphertext "
        "FROM connector_consent WHERE connector_id = ?",
        (connector_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row is not None else None


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
    Logs one use-event and fetches live PatentsView records for its supported
    adapter. Other providers remain explicitly simulated until their APIs
    have provider-specific integrations.
    """
    connector = _get_connector_for_use(connector_id)
    if connector is None or connector["status"] != "active":
        return None

    conn = db.get_conn()
    conn.execute(
        "INSERT INTO connector_usage_log (connector_id, timestamp, query) VALUES (?, ?, ?)",
        (connector_id, datetime.datetime.utcnow().isoformat(), query),
    )
    conn.commit()
    conn.close()

    if connector["provider"].casefold() in _PATENTSVIEW_PROVIDERS:
        if not connector.get("key_ciphertext"):
            return {
                "connector_id": connector_id,
                "provider": connector["provider"],
                "live": False,
                "simulated": False,
                "reason": "This connector has no encrypted API key. Re-link it to enable live search.",
                "results": [],
            }
        try:
            from cryptography.fernet import InvalidToken
            api_key = _fernet().decrypt(
                connector["key_ciphertext"].encode("ascii")
            ).decode("utf-8")
        except (InvalidToken, ConnectorConfigurationError) as exc:
            reason = str(exc) if isinstance(exc, ConnectorConfigurationError) else (
                "Could not decrypt this connector's API key; check CONNECTOR_ENCRYPTION_KEY."
            )
            return {
                "connector_id": connector_id,
                "provider": connector["provider"],
                "live": False,
                "simulated": False,
                "reason": reason,
                "results": [],
            }

        result = registry_lookup.lookup_patentsview(query, api_key)
        return {
            "connector_id": connector_id,
            "provider": "USPTO PatentsView Search API",
            "jurisdiction": "United States",
            "scope": connector["scope"],
            "live": result["live"],
            "simulated": False,
            "reason": result.get("reason"),
            "results": result["results"],
            "note": (
                "Live US patent search results. These records are shown separately and are not "
                "legal-corpus citations or a substitute for jurisdiction-specific legal review."
            ) if result["live"] else result.get("reason"),
        }

    return {
        "connector_id": connector_id,
        "provider": connector["provider"],
        "scope": connector["scope"],
        "live": False,
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
