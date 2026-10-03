import json
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import corpus_freshness as cf  # noqa: E402
from app import db, retrieval  # noqa: E402


def _fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_corpus_refresh.db")
    monkeypatch.setattr(db, "_DB_PATH", db_path)
    db.init_db()


def _isolated_corpus_file(tmp_path, monkeypatch):
    """Point retrieval._CORPUS_PATH at a throwaway copy so approve_refresh's
    disk write never touches the real data/corpus.json during tests."""
    copy_path = tmp_path / "corpus_copy.json"
    with open(retrieval._CORPUS_PATH, "r", encoding="utf-8") as f:
        original = json.load(f)
    with open(copy_path, "w", encoding="utf-8") as f:
        json.dump(original, f)
    monkeypatch.setattr(retrieval, "_CORPUS_PATH", str(copy_path))
    return original


class _FakeRequests(types.ModuleType):
    """Returns a scripted sequence of page bodies, one per call, so a test
    can simulate 'first fetch' vs 'source changed since last fetch'."""

    def __init__(self, bodies, statuses=None):
        super().__init__("requests")
        self._bodies = list(bodies)
        self._statuses = list(statuses) if statuses else [200] * len(bodies)
        self._n = 0

    def get(self, url, timeout=None, allow_redirects=None):
        i = min(self._n, len(self._bodies) - 1)
        self._n += 1
        return types.SimpleNamespace(text=self._bodies[i], status_code=self._statuses[i])


def test_propose_refresh_skips_documents_without_a_parseable_url(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]
    original_url = retrieval._CORPUS_BY_ID[doc_id]["source_url"]
    retrieval._CORPUS_BY_ID[doc_id]["source_url"] = ""
    try:
        results = cf.propose_refresh(doc_ids=[doc_id])
        assert results[0]["status"] == "skipped"
    finally:
        retrieval._CORPUS_BY_ID[doc_id]["source_url"] = original_url


def test_propose_refresh_records_baseline_on_first_check(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]
    monkeypatch.setitem(sys.modules, "requests", _FakeRequests(["<html>Section text v1</html>"]))
    results = cf.propose_refresh(doc_ids=[doc_id])
    assert results[0]["status"] == "baseline_recorded"


def test_propose_refresh_unchanged_when_content_identical(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]
    monkeypatch.setitem(sys.modules, "requests", _FakeRequests(["<html>Same text</html>", "<html>Same text</html>"]))
    cf.propose_refresh(doc_ids=[doc_id])
    second = cf.propose_refresh(doc_ids=[doc_id])
    assert second[0]["status"] == "unchanged"


def test_propose_refresh_flags_pending_review_on_drift(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]
    monkeypatch.setitem(sys.modules, "requests", _FakeRequests([
        "<html>Section 3(p) original wording</html>",
        "<html>Section 3(p) AMENDED wording</html>",
    ]))
    cf.propose_refresh(doc_ids=[doc_id])
    second = cf.propose_refresh(doc_ids=[doc_id])
    assert second[0]["status"] == "pending_review"
    assert "diff_preview" in second[0]
    assert "AMENDED" in second[0]["diff_preview"]


def test_propose_refresh_fetch_failure_reported_not_swallowed(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]

    class Boom(types.ModuleType):
        def get(self, *a, **k):
            raise ConnectionError("no route to host")

    monkeypatch.setitem(sys.modules, "requests", Boom("requests"))
    results = cf.propose_refresh(doc_ids=[doc_id])
    assert results[0]["status"] == "fetch_failed"
    assert "ConnectionError" in results[0]["reason"]


def test_refresh_state_reports_never_checked_for_untouched_docs(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]
    state = cf.refresh_state(doc_ids=[doc_id])
    assert state[0]["status"] == "never_checked"


def test_approve_refresh_requires_a_pending_review(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    _isolated_corpus_file(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]
    try:
        cf.approve_refresh(doc_id, "alice")
        assert False, "should have raised — nothing pending yet"
    except ValueError:
        pass


def test_approve_refresh_requires_a_reviewer_name(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]
    try:
        cf.approve_refresh(doc_id, "")
        assert False, "should have raised — approval must be attributable"
    except ValueError:
        pass


def test_approve_refresh_promotes_pending_hash_and_persists_retrieved_date(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    _isolated_corpus_file(tmp_path, monkeypatch)
    doc_id = retrieval._CORPUS[0]["id"]
    original_retrieved_date = retrieval._CORPUS_BY_ID[doc_id]["retrieved_date"]
    monkeypatch.setitem(sys.modules, "requests", _FakeRequests([
        "<html>original wording</html>",
        "<html>changed wording</html>",
    ]))
    try:
        cf.propose_refresh(doc_ids=[doc_id])
        cf.propose_refresh(doc_ids=[doc_id])  # -> pending_review

        result = cf.approve_refresh(doc_id, "bob")
        assert result["status"] == "verified"
        assert result["reviewer"] == "bob"

        state = cf.refresh_state(doc_ids=[doc_id])
        assert state[0]["status"] == "verified"

        # in-memory corpus AND the (isolated, tmp-path) corpus.json on disk
        # both reflect the human-attributed re-verification date
        import datetime
        today = datetime.date.today().isoformat()
        assert retrieval._CORPUS_BY_ID[doc_id]["retrieved_date"] == today
        with open(retrieval._CORPUS_PATH, "r", encoding="utf-8") as f:
            on_disk = json.load(f)
        match = [d for d in on_disk if d["id"] == doc_id][0]
        assert match["retrieved_date"] == today
    finally:
        retrieval._CORPUS_BY_ID[doc_id]["retrieved_date"] = original_retrieved_date


def test_html_to_text_strips_tags_and_scripts():
    html = "<html><head><script>var x=1;</script></head><body><p>Hello <b>world</b></p></body></html>"
    text = cf._html_to_text(html)
    assert "script" not in text.lower() or "var x" not in text
    assert "Hello" in text and "world" in text
    assert "<" not in text
