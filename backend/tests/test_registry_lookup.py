import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import registry_lookup as rl  # noqa: E402


def test_lookup_requires_keyword():
    try:
        rl.lookup("India", "")
        assert False, "should have raised"
    except ValueError:
        pass


def test_lookup_rejects_unknown_jurisdiction():
    try:
        rl.lookup("Mars", "triphala")
        assert False, "should have raised"
    except ValueError:
        pass


def test_india_patents_deep_link():
    res = rl.lookup("India", "Triphala churna", registry="patents")
    assert res["live"] is False
    assert res["deep_link"].startswith("https://ipindiaonline.gov.in")


def test_india_gi_deep_link():
    res = rl.lookup("India", "Darjeeling tea", registry="gi")
    assert "GIRPublic" in res["deep_link"]


def test_india_unknown_registry_reported_honestly():
    res = rl.lookup("India", "something", registry="not-a-real-registry")
    assert res["live"] is False
    assert "Unknown India registry" in res["reason"]


def test_international_fails_closed_without_api_key(monkeypatch):
    import os as _os
    had = "PATENTSVIEW_API_KEY" in _os.environ
    old = _os.environ.pop("PATENTSVIEW_API_KEY", None)
    try:
        res = rl.lookup("International", "ashwagandha extract")
        assert res["live"] is False
        assert "PATENTSVIEW_API_KEY" in res["reason"]
        assert res["results"] == []
    finally:
        if had:
            _os.environ["PATENTSVIEW_API_KEY"] = old


def test_patentsview_status_reports_unconfigured(monkeypatch):
    import os as _os
    had = "PATENTSVIEW_API_KEY" in _os.environ
    old = _os.environ.pop("PATENTSVIEW_API_KEY", None)
    try:
        status = rl.patentsview_status()
        assert status["configured"] is False
    finally:
        if had:
            _os.environ["PATENTSVIEW_API_KEY"] = old


def test_international_success_path_parses_patentsview_response(monkeypatch):
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "fake-test-key")

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"patents": [{"patent_id": "11000000", "patent_title": "Ashwagandha extract composition", "patent_date": "2023-05-01"}]}

    import requests

    def fake_get(url, params=None, timeout=None, headers=None):
        assert headers.get("X-Api-Key") == "fake-test-key"
        return FakeResp()

    monkeypatch.setattr(requests, "get", fake_get)
    res = rl.lookup("International", "ashwagandha extract")
    assert res["live"] is True
    assert res["results"][0]["patent_id"] == "11000000"
    assert res["results"][0]["url"] == "https://patents.google.com/patent/US11000000"


def test_international_network_error_fails_closed(monkeypatch):
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "fake-test-key")

    import requests

    def raising_get(*a, **k):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(requests, "get", raising_get)
    res = rl.lookup("International", "ashwagandha extract")
    assert res["live"] is False
    assert "ConnectionError" in res["reason"]
