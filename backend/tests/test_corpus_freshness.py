import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import corpus_freshness as cf  # noqa: E402
from app import retrieval  # noqa: E402


def test_freshness_report_covers_every_corpus_document():
    report = cf.freshness_report()
    assert report["total_documents"] == len(retrieval._CORPUS)
    assert sum(report["counts"].values()) == len(retrieval._CORPUS)
    ids_in_report = {d["id"] for d in report["documents"]}
    assert ids_in_report == {d["id"] for d in retrieval._CORPUS}


def test_bucketing_thresholds():
    as_of = datetime.date(2026, 9, 26)
    fresh_doc = {"id": "X1", "title": "t", "jurisdiction": "India", "retrieved_date": "2026-09-01", "version_date": "n/a", "source_url": ""}
    aging_doc = {"id": "X2", "title": "t", "jurisdiction": "India", "retrieved_date": "2026-04-01", "version_date": "n/a", "source_url": ""}
    stale_doc = {"id": "X3", "title": "t", "jurisdiction": "India", "retrieved_date": "2025-01-01", "version_date": "n/a", "source_url": ""}
    unknown_doc = {"id": "X4", "title": "t", "jurisdiction": "India", "retrieved_date": "not-a-date", "version_date": "n/a", "source_url": ""}

    assert cf._doc_freshness(fresh_doc, as_of)["status"] == "fresh"
    assert cf._doc_freshness(aging_doc, as_of)["status"] == "aging"
    assert cf._doc_freshness(stale_doc, as_of)["status"] == "stale"
    row = cf._doc_freshness(unknown_doc, as_of)
    assert row["status"] == "unknown" and row["age_days"] is None


def test_extract_url_strips_parenthetical_note():
    field = "https://www.indiacode.nic.in/handle/123456789/1392 (India Code — Patents Act, 1970)"
    assert cf._extract_url(field) == "https://www.indiacode.nic.in/handle/123456789/1392"
    assert cf._extract_url("") is None
    assert cf._extract_url("no url here at all") is None


def test_build_staleness_warning_none_when_nothing_stale():
    assert cf.build_staleness_warning([]) is None
    # every real corpus doc is freshly retrieved as of this build
    a_real_id = retrieval._CORPUS[0]["id"]
    assert cf.build_staleness_warning([{"id": a_real_id}]) is None


def test_build_staleness_warning_flags_stale_sources(monkeypatch):
    def fake_freshness_by_id():
        return {"STALE-1": {"status": "stale"}, "FRESH-1": {"status": "fresh"}}

    monkeypatch.setattr(cf, "freshness_by_id", fake_freshness_by_id)
    warning = cf.build_staleness_warning([{"id": "STALE-1"}, {"id": "FRESH-1"}])
    assert warning is not None
    assert "STALE-1" in warning
    assert "FRESH-1" not in warning


def test_check_live_reachability_fails_closed_on_network_error(monkeypatch):
    class Boom:
        def head(self, *a, **k):
            raise ConnectionError("no route to host")

    import sys as _sys
    monkeypatch.setitem(_sys.modules, "requests", Boom())
    results = cf.check_live_reachability(doc_ids=[retrieval._CORPUS[0]["id"]])
    assert results[0]["reachable"] is False
    assert "ConnectionError" in results[0]["reason"]


def test_check_live_reachability_missing_url_reported_honestly():
    doc_id = retrieval._CORPUS[0]["id"]
    original = retrieval._CORPUS_BY_ID[doc_id]["source_url"]
    retrieval._CORPUS_BY_ID[doc_id]["source_url"] = ""
    try:
        results = cf.check_live_reachability(doc_ids=[doc_id])
        assert results[0]["reachable"] is None
    finally:
        retrieval._CORPUS_BY_ID[doc_id]["source_url"] = original
