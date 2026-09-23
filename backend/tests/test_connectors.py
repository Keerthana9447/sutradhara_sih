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
