import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import graph_reasoning, graph_store, retrieval  # noqa: E402


def test_backend_is_in_memory_without_neo4j_configured():
    # No NEO4J_URI/USER/PASSWORD set in this environment (and no `neo4j`
    # package installed) — must fall back cleanly, never raise at import.
    assert graph_store.GRAPH_BACKEND == "in_memory"


def test_docs_for_area_matches_direct_corpus_lookup():
    expected = [d for d in retrieval._CORPUS if d["domain"] == "Patents" and d["jurisdiction"] == "India"][:2]
    got = graph_store.docs_for_area("Patents", "India", 2)
    assert [d["id"] for d in got] == [d["id"] for d in expected]


def test_reason_reports_active_backend():
    result = graph_reasoning.reason("Classical / Generic Medicine", "India", export_intent=False)
    assert result["graph_backend"] == graph_store.GRAPH_BACKEND
    assert len(result["nodes"]) > 2
    assert len(result["edges"]) > 1
    assert len(result["steps"]) >= 1


def test_reason_export_intent_adds_export_branch():
    result = graph_reasoning.reason("Classical / Generic Medicine", "India", export_intent=True)
    assert any(n["type"] == "ExportIntent" for n in result["nodes"])


def test_reason_rejects_unknown_category():
    try:
        graph_reasoning.reason("Not A Real Category", "India")
        assert False, "should have raised"
    except ValueError:
        pass


def test_reason_rejects_unknown_jurisdiction():
    try:
        graph_reasoning.reason("Classical / Generic Medicine", "Mars")
        assert False, "should have raised"
    except ValueError:
        pass


def test_docs_for_area_live_falls_back_on_query_failure(monkeypatch):
    # Simulate a live Neo4j backend whose query blows up mid-request — must
    # fall back to the in-memory lookup for that call, never raise up to
    # the caller.
    class BoomDriver:
        def session(self):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(graph_store, "GRAPH_BACKEND", "neo4j")
    monkeypatch.setattr(graph_store, "_DRIVER", BoomDriver())
    got = graph_store.docs_for_area("Patents", "India", 2)
    expected = [d for d in retrieval._CORPUS if d["domain"] == "Patents" and d["jurisdiction"] == "India"][:2]
    assert [d["id"] for d in got] == [d["id"] for d in expected]
