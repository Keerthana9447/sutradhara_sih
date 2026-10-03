"""
Tests for the optional Groq paraphrase layer (app/llm.py).

These tests never make a real network call to api.groq.com — they verify
the fail-safe contract: with no API key configured (the default in this
repo's checked-in .env), paraphrase_answer() must return the input
unchanged, and the citation-preservation checker must correctly accept/
reject candidate outputs.
"""
import importlib

from app import llm


def test_research_plan_accepts_only_bounded_allowed_area_searches():
    valid = {
        "steps": [
            {
                "tool": "search_corpus",
                "area": "Trade Secrets",
                "query": "TRIPS Article 39 undisclosed information",
            }
        ]
    }
    assert llm._validate_research_plan(valid, ["Trade Secrets"]) == valid["steps"]
    assert llm._validate_research_plan(
        {"done": True, "steps": []}, ["Trade Secrets"],
    ) == []

    invalid = {
        "steps": [
            {"tool": "search_corpus", "area": "Patents", "query": "TRIPS Article 39"}
        ]
    }
    assert llm._validate_research_plan(invalid, ["Trade Secrets"]) is None
    assert llm._validate_research_plan(
        {"steps": valid["steps"] * 4}, ["Trade Secrets"],
    ) is None
    assert llm._validate_research_plan(
        {"done": True, "steps": valid["steps"]}, ["Trade Secrets"],
    ) is None


def test_research_planner_is_opt_in_without_leaking_queries(monkeypatch):
    monkeypatch.setattr(llm, "_RESEARCH_PLANNER_ENABLED", True)
    monkeypatch.setattr(llm, "GROQ_API_KEY", "")
    plan, mode = llm.plan_research(
        "confidential question", "India", ["Trade Secrets"],
    )
    assert plan == []
    assert mode == "deterministic_fallback"


def test_research_planner_executes_validated_model_plan(monkeypatch):
    import json
    import httpx

    plan = {
        "steps": [
            {
                "tool": "search_corpus",
                "area": "Trade Secrets",
                "query": "TRIPS Article 39 undisclosed information",
            }
        ]
    }

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(plan)}}]}

    monkeypatch.setattr(llm, "_RESEARCH_PLANNER_ENABLED", True)
    monkeypatch.setattr(llm, "GROQ_API_KEY", "test-key")
    request_kwargs = {}

    def fake_post(*args, **kwargs):
        request_kwargs.update(kwargs)
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)

    result, mode = llm.plan_research(
        "What protects trade secrets under TRIPS?", "International", ["Trade Secrets"],
    )
    assert result == plan["steps"]
    assert mode == "agentic_groq"
    assert "response_format" not in request_kwargs["json"]


def test_paraphrase_is_noop_without_api_key(monkeypatch):
    monkeypatch.setattr(llm, "GROQ_API_KEY", "")
    text = "(1) Some grounded sentence. [Source: The Patents Act, 1970, Section 3(p)]"
    result, used_llm = llm.paraphrase_answer(text)
    assert result == text
    assert used_llm is False


def test_paraphrase_disabled_flag_is_noop(monkeypatch):
    monkeypatch.setattr(llm, "GROQ_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(llm, "_ENABLED", False)
    text = "(1) Some grounded sentence. [Source: The Patents Act, 1970, Section 3(p)]"
    result, used_llm = llm.paraphrase_answer(text)
    assert result == text
    assert used_llm is False


def test_citations_preserved_accepts_reordered_identical_tags():
    original = (
        "(1) First point. [Source: A Act, 1970, Section 3(p)]\n\n"
        "(2) Second point. [Source: B Act, 2002, Section 5]"
    )
    candidate = (
        "Second point restated first. [Source: B Act, 2002, Section 5] "
        "Then the first point. [Source: A Act, 1970, Section 3(p)]"
    )
    assert llm._citations_preserved(original, candidate) is True


def test_citations_preserved_rejects_altered_citation():
    original = "Point one. [Source: A Act, 1970, Section 3(p)]"
    candidate = "Point one, reworded. [Source: A Act, 1970, Section 3(z)]"
    assert llm._citations_preserved(original, candidate) is False


def test_citations_preserved_rejects_dropped_citation():
    original = (
        "Point one. [Source: A Act, 1970, Section 3(p)]\n\n"
        "Point two. [Source: B Act, 2002, Section 5]"
    )
    candidate = "Both points combined into one sentence. [Source: A Act, 1970, Section 3(p)]"
    assert llm._citations_preserved(original, candidate) is False


def test_citations_preserved_rejects_when_original_has_no_citations():
    # An empty original citation set should never "trivially pass" —
    # guards against a future caller passing already-abstained/empty text.
    original = "No citations here at all."
    candidate = "No citations here at all, rephrased."
    assert llm._citations_preserved(original, candidate) is False
