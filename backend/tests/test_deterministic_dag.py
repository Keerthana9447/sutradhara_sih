"""
Verifies app/dag.py: the deterministic LangGraph DAG that now implements the
/api/analyze pipeline (see app/dag.py's module docstring for the graph
shape).

Two things are checked:
  1. The graph reaches the right terminal node (clarification / abstain /
     success) for each of the three control-flow branches, via the exact
     same node functions main.py now delegates to.
  2. Whichever backend actually executed -- `langgraph` if the package is
     installed, `sequential` if not (see dag.DAG_BACKEND) -- produces the
     same result, since `_run_sequential` calls the identical node
     functions in the identical order/branches as the compiled LangGraph
     graph. This sandbox has no internet access to `pip install langgraph`,
     so only the `sequential` backend actually runs here; on a machine with
     internet, DAG_BACKEND flips to "langgraph" automatically with zero
     code changes, exercising the graph-executed path instead.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import dag, db  # noqa: E402

CLASSICAL_QUERY = "Can I patent a classical Ayurvedic formulation?"
UNSUPPORTED_FOREIGN_QUERY = "What export documentation does Vietnam require for herbal cosmetics?"
AMBIGUOUS_QUERY = "tell me about my product"


def setup_module(module):
    db.init_db()


def _run(query: str, jurisdiction: str, language: str = "en", confirmed_category=None, use_connector_id=None):
    state = {
        "query": query,
        "jurisdiction": jurisdiction,
        "language": language,
        "confirmed_category": confirmed_category,
        "use_connector_id": use_connector_id,
        "jur": jurisdiction,
    }
    return dag.run_analyze_pipeline(state)


def test_dag_backend_is_reported_and_valid():
    assert dag.DAG_BACKEND in ("langgraph", "sequential")


def test_clarification_branch_short_circuits_to_response():
    result = _run(AMBIGUOUS_QUERY, "India")
    assert result["classification"].needs_clarification is True
    assert result["abstained"] is True
    assert result["sources"] == []
    assert result["applicable_areas"] == []


def test_abstain_branch_when_no_evidence_retrieved():
    result = _run(UNSUPPORTED_FOREIGN_QUERY, "India")
    assert result["abstained"] is True
    assert result["sources"] == []


def test_success_branch_produces_grounded_answer_and_sources():
    result = _run(CLASSICAL_QUERY, "India")
    assert result["abstained"] is False
    assert result["classification"].category == "Classical / Generic Medicine"
    assert len(result["sources"]) > 0
    ids = {s["id"] for s in result["sources"]}
    assert "IN-PAT-3P" in ids or "IN-PAT-3J" in ids
    assert result["answer"], "success branch must produce non-empty answer text"


def test_jurisdiction_isolation_holds_through_the_dag():
    india = _run(CLASSICAL_QUERY, "India")
    intl = _run(CLASSICAL_QUERY, "International")
    assert all(s["jurisdiction"] == "India" for s in india["sources"])
    assert all(s["jurisdiction"] == "International" for s in intl["sources"])
    ids_india = {s["id"] for s in india["sources"]}
    ids_intl = {s["id"] for s in intl["sources"]}
    assert ids_india.isdisjoint(ids_intl)


def test_dag_is_deterministic_across_repeated_runs():
    """With optional model features disabled, equal inputs produce equal outputs."""
    r1 = _run(CLASSICAL_QUERY, "India")
    r2 = _run(CLASSICAL_QUERY, "India")
    assert [s["id"] for s in r1["sources"]] == [s["id"] for s in r2["sources"]]
    assert r1["confidence"] == r2["confidence"]
    assert r1["abstained"] == r2["abstained"]
    assert r1["orchestration_mode"] == "deterministic_fallback"


def test_bounded_planner_executes_only_area_scoped_searches(monkeypatch):
    step = {
        "tool": "search_corpus",
        "area": "Trade Secrets",
        "query": "TRIPS Article 39 undisclosed information",
    }
    planning_calls = []

    def fake_plan_research(query, jurisdiction, areas, **kwargs):
        planning_calls.append(kwargs)
        if kwargs.get("observations") is None:
            return [step], "agentic_groq"
        assert kwargs["max_steps"] == 1
        assert kwargs["prior_steps"] == [step]
        assert any(source["id"] == "INTL-TRIPS-39" for source in kwargs["observations"])
        return [], "agentic_groq"

    monkeypatch.setattr(dag.llm, "plan_research", fake_plan_research)
    calls = []
    source = {
        "id": "INTL-TRIPS-39",
        "title": "TRIPS Article 39",
        "domain": "Trade Secrets",
        "section": "Undisclosed information",
        "relevance_score": 0.7,
    }

    def fake_retrieve(queries, jurisdiction, areas, top_k):
        calls.append((queries, jurisdiction, areas, top_k))
        return [source] if queries == [step["query"]] else []

    monkeypatch.setattr(dag.retrieval, "retrieve", fake_retrieve)
    state = {
        "query": "What does TRIPS say about trade secrets?",
        "retrieval_query": "What does TRIPS say about trade secrets?",
        "jur": "International",
        "areas": ["Trade Secrets"],
        "query_variants": ["What does TRIPS say about trade secrets?"],
    }
    planned = dag._plan_research(state)
    retrieved = dag._retrieve({**state, **planned})["retrieved"]

    assert planned["planning_mode"] == "agentic_groq"
    assert calls[1] == ([step["query"]], "International", ["Trade Secrets"], 5)
    assert [document["id"] for document in retrieved] == ["INTL-TRIPS-39"]
    assert len(planning_calls) == 2
