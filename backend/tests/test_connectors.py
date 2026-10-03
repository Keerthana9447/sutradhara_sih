import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import connectors, db  # noqa: E402


def _fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_connectors.db")
    monkeypatch.setattr(db, "_DB_PATH", db_path)
    db.init_db()


def test_link_connector_never_stores_raw_key(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    info = connectors.link_connector("PatSeer", "super-secret-key-12345", scope="patent_search")
    assert info["key_fingerprint"] == "2345"
    assert "super-secret-key-12345" not in json_dump_safe(info)
    assert info["status"] == "active"


def json_dump_safe(d):
    import json
    return json.dumps(d)


def test_link_connector_rejects_empty_fields(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    try:
        connectors.link_connector("", "somekey")
        assert False, "should have raised"
    except ValueError:
        pass


def test_short_connector_key_is_not_exposed_by_fingerprint(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    info = connectors.link_connector("Provider", "abc")
    assert info["key_fingerprint"] == "****"
    four_char_key = connectors.link_connector("Provider", "abcd")
    assert four_char_key["key_fingerprint"] == "****"


def test_use_connector_logs_usage(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    info = connectors.link_connector("Derwent Innovation", "abc123", scope="patent_search")
    result = connectors.use_connector(info["connector_id"], "test query about patents")
    assert result is not None
    assert result["simulated"] is True
    assert result["provider"] == "Derwent Innovation"

    log = connectors.usage_log_for(info["connector_id"])
    assert len(log) == 1
    assert log[0]["query"] == "test query about patents"


def test_patentsview_link_encrypts_key_and_uses_live_adapter(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet

    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.setenv("CONNECTOR_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))

    def fake_lookup(query, api_key):
        assert api_key == "a-private-api-key"
        return {
            "live": True,
            "results": [{"patent_id": "US-TEST", "title": query, "url": "https://example.test"}],
        }

    monkeypatch.setattr(connectors.registry_lookup, "lookup_patentsview", fake_lookup)

    info = connectors.link_connector("USPTO PatentsView", "a-private-api-key")
    conn = db.get_conn()
    stored = conn.execute(
        "SELECT key_ciphertext FROM connector_consent WHERE connector_id = ?",
        (info["connector_id"],),
    ).fetchone()
    conn.close()
    encrypted_key = stored["key_ciphertext"]
    assert encrypted_key != "a-private-api-key"
    assert "a-private-api-key" not in encrypted_key
    assert "key_ciphertext" not in connectors.get_connector(info["connector_id"])

    result = connectors.use_connector(info["connector_id"], "herbal extraction process")
    assert result["live"] is True
    assert result["simulated"] is False
    assert result["jurisdiction"] == "United States"
    assert result["results"][0]["patent_id"] == "US-TEST"


def test_analyze_returns_live_patentsview_results_separately(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from fastapi.testclient import TestClient
    from app.main import app

    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.setenv("CONNECTOR_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setattr(
        connectors.registry_lookup,
        "lookup_patentsview",
        lambda query, api_key: {
            "live": True,
            "results": [{"patent_id": "US-API-TEST", "title": "Live test patent", "url": "https://example.test"}],
        },
    )
    info = connectors.link_connector("USPTO PatentsView", "api-key-for-test")

    with TestClient(app) as client:
        response = client.post("/api/analyze", json={
            "query": "Can I patent a new herbal extraction process?",
            "jurisdiction": "International",
            "confirmed_category": "New / Non-Classical Drug",
            "use_connector_id": info["connector_id"],
        })

    assert response.status_code == 200
    body = response.json()
    assert body["connector_source_used"]["live"] is True
    assert body["connector_source_used"]["results"][0]["patent_id"] == "US-API-TEST"
    assert "US-API-TEST" not in {source["id"] for source in body["sources"]}


def test_patentsview_link_requires_encryption_configuration(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.delenv("CONNECTOR_ENCRYPTION_KEY", raising=False)
    try:
        connectors.link_connector("USPTO PatentsView", "api-key")
        assert False, "should have raised"
    except connectors.ConnectorConfigurationError:
        pass


def test_existing_connector_table_gets_encrypted_key_column(tmp_path, monkeypatch):
    import sqlite3

    db_path = str(tmp_path / "legacy_connectors.db")
    monkeypatch.setattr(db, "_DB_PATH", db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE connector_consent ("
        "connector_id TEXT PRIMARY KEY, provider TEXT NOT NULL, scope TEXT NOT NULL, "
        "key_fingerprint TEXT NOT NULL, key_hash TEXT NOT NULL, contact_email TEXT, "
        "status TEXT NOT NULL DEFAULT 'active', linked_at TEXT NOT NULL, revoked_at TEXT)"
    )
    conn.commit()
    conn.close()

    db.init_db()
    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(connector_consent)")}
    conn.close()
    assert "key_ciphertext" in columns


def test_revoked_connector_cannot_be_used(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    info = connectors.link_connector("PatSeer", "abc123")
    ok = connectors.revoke_connector(info["connector_id"])
    assert ok is True

    result = connectors.use_connector(info["connector_id"], "some query")
    assert result is None, "a revoked connector must never be usable again"


def test_revoke_unknown_connector_returns_false(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert connectors.revoke_connector("conn_doesnotexist") is False


def test_list_connectors_reflects_status(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    a = connectors.link_connector("PatSeer", "key-a")
    b = connectors.link_connector("Derwent Innovation", "key-b")
    connectors.revoke_connector(a["connector_id"])

    listed = {c["connector_id"]: c for c in connectors.list_connectors()}
    assert listed[a["connector_id"]]["status"] == "revoked"
    assert listed[b["connector_id"]]["status"] == "active"
