import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import graph, graph_reasoning, graph_store, retrieval  # noqa: E402


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


def test_docs_for_area_live_filters_before_applying_limit(monkeypatch):
    expected = next(
        d for d in retrieval._CORPUS
        if d["domain"] == "Patents" and d["jurisdiction"] == "India"
    )

    class FakeSession:
        query = None
        parameters = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def run(self, query, **parameters):
            self.query = query
            self.parameters = parameters
            return [{"id": expected["id"]}]

    class FakeDriver:
        def __init__(self):
            self.current_session = FakeSession()

        def session(self):
            return self.current_session

    driver = FakeDriver()
    monkeypatch.setattr(graph_store, "GRAPH_BACKEND", "neo4j")
    monkeypatch.setattr(graph_store, "_DRIVER", driver)

    assert graph_store.docs_for_area("Patents", "India", 1) == [expected]
    assert "jurisdiction: $jur" in driver.current_session.query
    assert "domain: $area" in driver.current_session.query
    assert driver.current_session.parameters == {"area": "Patents", "jur": "India", "limit": 1}


def test_dynamic_graph_honors_neo4j_disable_switch(monkeypatch):
    class UnexpectedGraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            raise AssertionError("Neo4j should not be contacted while disabled")

    monkeypatch.setenv("SUTRADHARA_DISABLE_NEO4J", "1")
    monkeypatch.setattr(graph, "_NEO4J_AVAILABLE", True)
    monkeypatch.setattr(graph, "GraphDatabase", UnexpectedGraphDatabase)

    assert graph._query_neo4j_graph("query", "category", "India") is None


def test_dynamic_graph_edges_carry_retrieval_confidence_and_source_provenance():
    source = {
        "id": "CORPUS-123",
        "domain": "Patents",
        "title": "Patent Act",
        "section": "Section 3",
        "relevance_score": 0.73,
    }
    result = graph.build_dynamic_graph(
        "patent query", "Cosmetic", "India", [source], applicable_areas=["Patents"],
    )
    source_edges = [
        edge for edge in result["edges"]
        if edge["provenance"].get("source_ids") == ["CORPUS-123"]
    ]

    assert source_edges
    assert all(edge["confidence"] == 0.73 for edge in source_edges)
    assert all(isinstance(edge["confidence"], (int, float)) for edge in result["edges"])
    assert all(edge["provenance"].get("basis") for edge in result["edges"])
    assert any(
        edge["label"] == "relevant_to"
        and edge["provenance"].get("source_ids") == ["CORPUS-123"]
        and edge["confidence"] == 0.73
        for edge in result["edges"]
    )


def test_dynamic_graph_does_not_invent_source_ids_or_confidence_without_evidence():
    result = graph.build_dynamic_graph(
        "unmatched query", "Cosmetic", "India",
        [{"domain": "Patents", "title": "Unidentified law", "section": "Section 1"}],
        applicable_areas=[],
    )

    assert not [node for node in result["nodes"] if node["type"] == "Source"]
    assert not [node for node in result["nodes"] if node.get("id", "").startswith("law_")]
    assert all(isinstance(edge["confidence"], (int, float)) for edge in result["edges"])
    unsupported = [edge for edge in result["edges"] if edge["confidence"] == 0.0]
    assert unsupported
    assert all(edge["provenance"].get("source_ids") == [] for edge in unsupported)
