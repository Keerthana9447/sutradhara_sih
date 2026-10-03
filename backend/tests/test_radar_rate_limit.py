from fastapi import HTTPException, Request
import pytest

from app import admin_auth, auth, radar
from app.main import radar_endpoint
from app.schemas import RadarRequest


def test_radar_endpoint_rate_limits_admin_requests(monkeypatch):
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/radar",
                       "headers": [], "client": ("203.0.113.7", 1234), "server": ("test", 80),
                       "scheme": "http", "query_string": b""})
    monkeypatch.setattr("app.main._current_user", lambda _authorization: {"id": 7, "role": "admin"})
    monkeypatch.setattr(admin_auth, "require_admin", lambda _user: None)
    monkeypatch.setattr(auth.login_limiter, "allow", lambda key: key == "radar|203.0.113.7|")
    monkeypatch.setattr(radar, "run_radar", lambda *args: {"status": "ok"})
    req = RadarRequest(patent_title="Title", patent_abstract="Abstract", patent_claims="Claim")

    assert radar_endpoint(req, request, "Bearer admin-token") == {"status": "ok"}

    monkeypatch.setattr(auth.login_limiter, "allow", lambda _key: False)
    with pytest.raises(HTTPException) as exc:
        radar_endpoint(req, request, "Bearer admin-token")
    assert exc.value.status_code == 429
