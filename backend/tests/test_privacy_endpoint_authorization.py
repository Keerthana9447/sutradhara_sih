import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import db, privacy  # noqa: E402
from app.main import app  # noqa: E402


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", str(tmp_path / "privacy_routes.db"))
    db.init_db()
    first = db.create_user("first@example.com", "First", "correct horse battery staple")
    second = db.create_user("second@example.com", "Second", "correct horse battery staple")
    first_token = db.create_auth_session(first["id"])
    second_token = db.create_auth_session(second["id"])
    first_session = db.create_chat_session(first["id"], "First user's private chat")
    db.add_chat_message(first_session["id"], "user", "Confidential question")
    return first, second, first_token, second_token, first_session


def test_chat_routes_reject_anonymous_and_cross_account_access(tmp_path, monkeypatch):
    first, second, first_token, second_token, session = _setup(tmp_path, monkeypatch)
    with TestClient(app) as client:
        assert client.get(f"/api/chat/sessions/{first['id']}").status_code == 401
        assert client.get(
            f"/api/chat/sessions/{first['id']}",
            headers={"Authorization": f"Bearer {second_token}"},
        ).status_code == 403
        assert client.get(
            f"/api/chat/sessions/{session['id']}/messages?user_id={first['id']}",
            headers={"Authorization": f"Bearer {second_token}"},
        ).status_code == 403
        assert client.delete(
            f"/api/chat/sessions/{session['id']}?user_id={first['id']}",
            headers={"Authorization": f"Bearer {second_token}"},
        ).status_code == 403
        own = client.get(
            f"/api/chat/sessions/{first['id']}",
            headers={"Authorization": f"Bearer {first_token}"},
        )
        assert own.status_code == 200
        assert own.json()[0]["title"] == "First user's private chat"


def test_privacy_access_and_erasure_are_authenticated_and_email_scoped(tmp_path, monkeypatch):
    first, second, first_token, second_token, _ = _setup(tmp_path, monkeypatch)
    db.log_escalation("private escalation", "category", "India", [], [], "first@example.com")
    db.log_escalation("other escalation", "category", "India", [], [], "second@example.com")

    with TestClient(app) as client:
        assert client.post("/api/privacy/access", json={"contact_email": first["email"]}).status_code == 401
        assert client.post("/api/privacy/erase", json={"contact_email": first["email"]}).status_code == 401

        cross_account_access = client.post(
            "/api/privacy/access",
            json={"contact_email": second["email"]},
            headers={"Authorization": f"Bearer {first_token}"},
        )
        assert cross_account_access.status_code == 403
        cross_account_erase = client.post(
            "/api/privacy/erase",
            json={"contact_email": second["email"]},
            headers={"Authorization": f"Bearer {first_token}"},
        )
        assert cross_account_erase.status_code == 403

        arbitrary_query = client.post(
            "/api/privacy/access",
            json={"query_text": "Confidential question"},
            headers={"Authorization": f"Bearer {first_token}"},
        )
        assert arbitrary_query.status_code == 400

        own = client.post(
            "/api/privacy/access",
            json={},
            headers={"Authorization": f"Bearer {first_token}"},
        )
        assert own.status_code == 200
        assert len(own.json()["account_data"]["chat_sessions"]) == 1
        assert own.json()["matching_logs"]["matched_records"] == 1

        erased = client.post(
            "/api/privacy/erase",
            json={"contact_email": first["email"]},
            headers={"Authorization": f"Bearer {first_token}"},
        )
        assert erased.status_code == 200
        assert erased.json()["deleted"]["escalation"] == 1

    conn = db.get_conn()
    escalation_emails = {
        row[0] for row in conn.execute("SELECT contact_email FROM escalation").fetchall()
    }
    conn.close()
    assert escalation_emails == {second["email"]}


def test_privacy_purge_requires_admin_secret_and_fixed_retention(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("SUTRADHARA_PRIVACY_PURGE_TOKEN", "test-purge-secret")
    calls = []
    monkeypatch.setattr(privacy, "purge_expired", lambda: calls.append("default-retention") or {})

    with TestClient(app) as client:
        assert client.post("/api/privacy/purge-expired").status_code == 401
        assert client.post(
            "/api/privacy/purge-expired",
            headers={"X-Privacy-Purge-Token": "wrong"},
        ).status_code == 401
        assert client.post(
            "/api/privacy/purge-expired",
            headers={"X-Privacy-Purge-Token": "test-purge-secret"},
            json={"retention_days": 0},
        ).status_code == 200

    assert calls == ["default-retention"]


def test_privacy_purge_fails_closed_when_not_configured(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.delenv("SUTRADHARA_PRIVACY_PURGE_TOKEN", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/api/privacy/purge-expired",
            headers={"X-Privacy-Purge-Token": "any-token"},
        )
    assert response.status_code == 503
