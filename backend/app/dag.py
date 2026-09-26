"""
Deterministic pipeline DAG for /api/analyze.

This module extracts the step-by-step pipeline that used to live inline in
`main.py::analyze()` into a graph of small, single-purpose nodes and wires
them together with LangGraph's `StateGraph`, wherever LangGraph is
installed:

    normalize_language -> expand_query -> classify
        --(needs_clarification)--> clarification_response -> END
        --(else)-->                route_areas -> retrieve -> score_confidence
                                    -> enrich_evidence -> use_connector
        --(abstained)-->           abstain_response -> END
        --(else)-->                build_answer -> paraphrase -> finalize_success -> END

It is a *deterministic* DAG, not an agent: every edge is a plain Python
`if`/`else` on values already present in the state (`needs_clarification`,
`abstained`) — never a decision made by an LLM. Given the same input and the
same corpus/config, the path taken through the graph and the fields produced
at each node are 100% reproducible. The one non-deterministic ingredient
that can exist anywhere in this pipeline — the optional Groq paraphrase call
inside `paraphrase_answer` (see app/llm.py) — was already present in the
pre-DAG pipeline unchanged; the DAG does not add any new source of
non-determinism, it only makes the existing control flow explicit and
inspectable as a graph instead of a 150-line function body.

Fallback: if the `langgraph` package is not installed (or fails to import
for any reason), `_run_sequential()` below calls the exact same node
functions in the exact same order with the exact same branching logic, with
zero LangGraph dependency. This mirrors the pattern already used in
app/retrieval.py for the BGE-embeddings-vs-TF-IDF split: try the richer
dependency, fall back to a dependency-light equivalent that produces
byte-identical output, and report which one actually ran via a module-level
constant (`DAG_BACKEND`) for logging/tests. Both paths execute the identical
node functions defined once in this file, so there is no separate "fallback
business logic" to drift out of sync with the LangGraph path.
"""
import logging
from typing import Any, Dict, List, Optional, TypedDict

from . import (
    answer, classifier, confidence, connectors, corpus_freshness, db, graph,
    jurisdiction, language, llm, pathway, query_expansion, retrieval,
    tkdl_similarity, translate,
)

logger = logging.getLogger("ip_sakti.dag")

_SUPPORTED_OUTPUT_LANGUAGES = ("en", "te", "hi", "ta", "ml", "sa")


class AnalyzeState(TypedDict, total=False):
    # --- inputs (set by main.py before invoking the graph) ---
    query: str
    jurisdiction: str          # raw request value, e.g. "India"
    language: str              # requested output language
    confirmed_category: Optional[str]
    use_connector_id: Optional[str]
    jur: str                   # resolved jurisdiction name (already validated by main.py)

    # --- produced along the way ---
    input_language: str
    retrieval_query: str
    query_variants: List[str]
    classification: Any        # schemas.ClassificationResult
    areas: List[str]
    retrieved: List[Dict[str, Any]]
    conf_score: float
    conf_label: str
    breakdown: Dict[str, Any]
    abstained: bool
    abs_checklist: Any         # Optional[schemas.AbsChecklist]
    tk_pointer: Optional[str]
    regulatory_pathway: List[str]
    tk_similarity: Any
    dynamic_graph: Optional[Dict[str, Any]]
    connector_source_used: Optional[Dict[str, Any]]
    generated_answer: str
    used_llm: bool
    evidence_logged: bool

    # --- terminal output ---
    response: Dict[str, Any]


# ---------------------------------------------------------------------------
# Node functions. Each takes the full state and returns only the keys it
# updates (LangGraph merges these into state with last-write-wins, which is
# also exactly what `_run_sequential` does by hand below).
# ---------------------------------------------------------------------------

def _normalize_language(state: AnalyzeState) -> Dict[str, Any]:
    """Multilingual normalization (retrieval-only; original query text is
    preserved untouched for display, logging, and escalation)."""
    input_language = language.detect_language(state["query"])
    retrieval_query = state["query"]
    if input_language != "en":
        translated, translated_ok = translate.translate_to_english(state["query"], input_language)
        if translated_ok and translated.strip():
            retrieval_query = translated
        else:
            # Offline normalization fallback — never silently fall through to
            # raw non-English text, which would zero out the English-only
            # TF-IDF tokenizer.
            retrieval_query = language.fallback_normalize(state["query"])
    return {"input_language": input_language, "retrieval_query": retrieval_query}


def _expand_query(state: AnalyzeState) -> Dict[str, Any]:
    return {"query_variants": query_expansion.expand_query(state["retrieval_query"])}


def _classify(state: AnalyzeState) -> Dict[str, Any]:
    # Classification/area-routing are keyword-based over English terms, so
    # they see the (translated) English retrieval query, not the raw
    # original-language text.
    classification = classifier.classify(state["retrieval_query"], state.get("confirmed_category"))
    return {"classification": classification}


def _needs_clarification_branch(state: AnalyzeState) -> str:
    return "clarify" if state["classification"].needs_clarification else "continue"


def _clarification_response(state: AnalyzeState) -> Dict[str, Any]:
    # Return early — the frontend should surface the clarification question
    # before calling /api/analyze again with confirmed_category set.
    abs_checklist = answer.build_abs_checklist(state["retrieval_query"], [])
    response = {
        "classification": state["classification"],
        "jurisdiction": state["jur"],
        "applicable_areas": [],
        "answer": "",
        "confidence": 0.0,
        "confidence_label": "LOW",
        "confidence_breakdown": {},
        "sources": [],
        "abs_checklist": abs_checklist,
        "abstained": True,
        "input_language": state["input_language"],
        "retrieval_query": state["retrieval_query"] if state["retrieval_query"] != state["query"] else None,
    }
    return {"response": response}


def _route_areas(state: AnalyzeState) -> Dict[str, Any]:
    return {"areas": jurisdiction.route_areas(state["retrieval_query"], state["classification"].category)}


def _retrieve(state: AnalyzeState) -> Dict[str, Any]:
    if jurisdiction.has_unsupported_foreign_country(state["query"], state["jur"]):
        retrieved: List[Dict[str, Any]] = []
    else:
        retrieved = retrieval.retrieve(state["query_variants"], state["jur"], state["areas"], top_k=5)
    return {"retrieved": retrieved}


def _score_confidence(state: AnalyzeState) -> Dict[str, Any]:
    conf_score, conf_label, breakdown = confidence.score(state["retrieved"], state["classification"].confidence)
    abstained = confidence.should_abstain(conf_score, state["retrieved"])
    return {"conf_score": conf_score, "conf_label": conf_label, "breakdown": breakdown, "abstained": abstained}


def _enrich_evidence(state: AnalyzeState) -> Dict[str, Any]:
    abs_checklist = answer.build_abs_checklist(state["retrieval_query"], state["retrieved"])
    tk_pointer = answer.build_tk_pointer(state["classification"].category, state["jur"])
    regulatory_pathway = pathway.get_pathway(state["classification"].category, state["jur"])
    tk_similarity = tkdl_similarity.maybe_score_resemblance(state["retrieval_query"], state["classification"].category)

    # Live, per-query explainability graph. Never allowed to break the main
    # analyze response if graph construction itself has a bug: falls back to
    # None rather than propagating, since this is a supplementary
    # visualization, not part of the evidence/citation guarantee.
    try:
        dynamic_graph = graph.build_dynamic_graph(
            state["query"], state["classification"].category, state["jur"], state["retrieved"], state["areas"],
        )
    except Exception:
        logger.exception("Dynamic graph construction failed; omitting from response")
        dynamic_graph = None

    return {
        "abs_checklist": abs_checklist,
        "tk_pointer": tk_pointer,
        "regulatory_pathway": regulatory_pathway,
        "tk_similarity": tk_similarity,
        "dynamic_graph": dynamic_graph,
    }


def _use_connector(state: AnalyzeState) -> Dict[str, Any]:
    # Optional paid-subscription connector use — strictly opt-in per request
    # and logged regardless of outcome. Never merged into `sources` —
    # kept as a separately-tagged field.
    connector_source_used = None
    if state.get("use_connector_id"):
        connector_source_used = connectors.use_connector(state["use_connector_id"], state["query"])
    return {"connector_source_used": connector_source_used}


def _log_evidence(state: AnalyzeState) -> Dict[str, Any]:
    retrieved = state["retrieved"]
    logger.info(
        "INPUT_LANGUAGE=%s RETRIEVAL_LANGUAGE=en ORIGINAL=%r NORMALIZED=%r "
        "CLASSIFICATION=%s JURISDICTION=%s AREAS=%s RETRIEVED_CHUNKS=%d "
        "TOP_SCORE=%s SOURCES=%s EVIDENCE_SCORE=%s ABSTAIN=%s",
        state["input_language"], state["query"], state["retrieval_query"],
        state["classification"].category, state["jur"], state["areas"], len(retrieved),
        (retrieved[0]["relevance_score"] if retrieved else None),
        [s["id"] for s in retrieved], state["conf_score"], state["abstained"],
    )
    # This node is otherwise a pure side effect (structured logging only),
    # but the installed LangGraph version requires every node to write to
    # at least one recognized state channel — an empty {} return raises
    # InvalidUpdateError ("Must write to at least one of [...]") at graph
    # compile/run time. `evidence_logged` is a genuine, minimal piece of
    # state (records that this logging step actually ran) rather than a
    # meaningless dummy field, and _run_sequential's plain dict merge below
    # treats it identically to every other node's output.
    return {"evidence_logged": True}


def _abstained_branch(state: AnalyzeState) -> str:
    return "abstain" if state["abstained"] else "continue"


def _resolve_output_language(state: AnalyzeState) -> str:
    return state["language"] if state["language"] in _SUPPORTED_OUTPUT_LANGUAGES else "en"


def _abstain_response(state: AnalyzeState) -> Dict[str, Any]:
    db.log_audit(state["query"], state["jur"], state["classification"].category, state["conf_score"], True, state["retrieved"])
    lang = _resolve_output_language(state)
    abstain_text, ok = translate.translate_text(
        "Insufficient authoritative evidence to provide a reliable answer from the available corpus.",
        lang,
    )
    response = {
        "classification": state["classification"],
        "jurisdiction": state["jur"],
        "applicable_areas": state["areas"],
        "answer": abstain_text,
        "confidence": state["conf_score"],
        "confidence_label": state["conf_label"],
        "confidence_breakdown": state["breakdown"],
        "sources": state["retrieved"],
        "abs_checklist": state["abs_checklist"],
        "tk_pointer": state["tk_pointer"],
        "abstained": True,
        "answer_language": lang,
        "translation_available": ok,
        "input_language": state["input_language"],
        "retrieval_query": state["retrieval_query"] if state["retrieval_query"] != state["query"] else None,
        "regulatory_pathway": state["regulatory_pathway"],
        "tk_similarity": state["tk_similarity"],
        "connector_source_used": state["connector_source_used"],
        "dynamic_graph": state["dynamic_graph"],
        "stale_sources_warning": corpus_freshness.build_staleness_warning(state["retrieved"]),
    }
    return {"response": response}


def _build_answer(state: AnalyzeState) -> Dict[str, Any]:
    generated_answer = answer.build_answer(state["query"], state["classification"].category, state["jur"], state["retrieved"])
    return {"generated_answer": generated_answer}


def _paraphrase(state: AnalyzeState) -> Dict[str, Any]:
    # Groq paraphrase layer: smooths the template-assembled answer into more
    # natural prose. Fail-safe (see llm.py) — every [Source: ...] tag must
    # survive unchanged or the original grounded text is used instead, so
    # this can never introduce an uncited or fabricated claim. This is the
    # one step in the whole graph that can call an external LLM; it never
    # influences *which* node runs next, only the text of `generated_answer`.
    generated_answer, used_llm = llm.paraphrase_answer(state["generated_answer"])
    logger.info("LLM_PARAPHRASE_APPLIED=%s", used_llm)
    return {"generated_answer": generated_answer, "used_llm": used_llm}


def _finalize_success(state: AnalyzeState) -> Dict[str, Any]:
    db.log_audit(state["query"], state["jur"], state["classification"].category, state["conf_score"], False, state["retrieved"])

    lang = _resolve_output_language(state)
    generated_answer = state["generated_answer"]
    classification = state["classification"]
    tk_pointer = state["tk_pointer"]
    abs_checklist = state["abs_checklist"]
    regulatory_pathway = state["regulatory_pathway"]

    # Translate the natural-language pieces only. Source titles, section
    # numbers, authority names, category labels, and area names are official
    # identifiers and are deliberately left untranslated.
    translation_ok = True
    if lang != "en":
        generated_answer, ok1 = translate.translate_text(generated_answer, lang)
        classification.reason, ok2 = translate.translate_text(classification.reason, lang)
        translation_ok = ok1 and ok2
        if tk_pointer:
            tk_pointer, ok3 = translate.translate_text(tk_pointer, lang)
            translation_ok = translation_ok and ok3
        if abs_checklist:
            abs_checklist.note, ok4 = translate.translate_text(abs_checklist.note, lang)
            translation_ok = translation_ok and ok4
        if regulatory_pathway:
            translated_steps = []
            for step in regulatory_pathway:
                t_step, ok5 = translate.translate_text(step, lang)
                translated_steps.append(t_step)
                translation_ok = translation_ok and ok5
            regulatory_pathway = translated_steps

    response = {
        "classification": classification,
        "jurisdiction": state["jur"],
        "applicable_areas": state["areas"],
        "answer": generated_answer,
        "confidence": state["conf_score"],
        "confidence_label": state["conf_label"],
        "confidence_breakdown": state["breakdown"],
        "sources": state["retrieved"],
        "abs_checklist": abs_checklist,
        "tk_pointer": tk_pointer,
        "abstained": False,
        "answer_language": lang,
        "translation_available": translation_ok,
        "input_language": state["input_language"],
        "retrieval_query": state["retrieval_query"] if state["retrieval_query"] != state["query"] else None,
        "llm_paraphrased": state["used_llm"],
        "regulatory_pathway": regulatory_pathway,
        "tk_similarity": state["tk_similarity"],
        "connector_source_used": state["connector_source_used"],
        "dynamic_graph": state["dynamic_graph"],
        "stale_sources_warning": corpus_freshness.build_staleness_warning(state["retrieved"]),
    }
    return {"response": response}


# ---------------------------------------------------------------------------
# Graph assembly: LangGraph if available, else a hand-rolled sequential
# executor that calls the exact same nodes in the exact same order.
# ---------------------------------------------------------------------------
DAG_BACKEND = "sequential"  # flipped to "langgraph" below iff the package imports and compiles
_COMPILED_GRAPH = None


def _build_langgraph():
    from langgraph.graph import StateGraph, END

    builder = StateGraph(AnalyzeState)
    builder.add_node("normalize_language", _normalize_language)
    builder.add_node("expand_query", _expand_query)
    builder.add_node("classify", _classify)
    builder.add_node("clarification_response", _clarification_response)
    builder.add_node("route_areas", _route_areas)
    builder.add_node("retrieve", _retrieve)
    builder.add_node("score_confidence", _score_confidence)
    builder.add_node("enrich_evidence", _enrich_evidence)
    builder.add_node("use_connector", _use_connector)
    builder.add_node("log_evidence", _log_evidence)
    builder.add_node("abstain_response", _abstain_response)
    builder.add_node("build_answer", _build_answer)
    builder.add_node("paraphrase", _paraphrase)
    builder.add_node("finalize_success", _finalize_success)

    builder.set_entry_point("normalize_language")
    builder.add_edge("normalize_language", "expand_query")
    builder.add_edge("expand_query", "classify")
    builder.add_conditional_edges(
        "classify", _needs_clarification_branch,
        {"clarify": "clarification_response", "continue": "route_areas"},
    )
    builder.add_edge("clarification_response", END)
    builder.add_edge("route_areas", "retrieve")
    builder.add_edge("retrieve", "score_confidence")
    builder.add_edge("score_confidence", "enrich_evidence")
    builder.add_edge("enrich_evidence", "use_connector")
    builder.add_edge("use_connector", "log_evidence")
    builder.add_conditional_edges(
        "log_evidence", _abstained_branch,
        {"abstain": "abstain_response", "continue": "build_answer"},
    )
    builder.add_edge("abstain_response", END)
    builder.add_edge("build_answer", "paraphrase")
    builder.add_edge("paraphrase", "finalize_success")
    builder.add_edge("finalize_success", END)

    return builder.compile()


try:
    _COMPILED_GRAPH = _build_langgraph()
    DAG_BACKEND = "langgraph"
    logger.info("Deterministic pipeline DAG backend: langgraph")
except Exception as e:  # ImportError if the package is absent, or any compile-time error
    logger.info("langgraph unavailable (%r); using the equivalent sequential executor.", e)
    _COMPILED_GRAPH = None
    DAG_BACKEND = "sequential"


def _run_sequential(state: AnalyzeState) -> AnalyzeState:
    """Executes the identical node functions/branches as the LangGraph graph
    above, without requiring the langgraph package. Node order and
    conditional logic are kept in lockstep with `_build_langgraph()` by
    inspection — both call the same node functions, so there is only one
    place business logic can drift: inside a node itself."""
    state.update(_normalize_language(state))
    state.update(_expand_query(state))
    state.update(_classify(state))

    if _needs_clarification_branch(state) == "clarify":
        state.update(_clarification_response(state))
        return state

    state.update(_route_areas(state))
    state.update(_retrieve(state))
    state.update(_score_confidence(state))
    state.update(_enrich_evidence(state))
    state.update(_use_connector(state))
    state.update(_log_evidence(state))

    if _abstained_branch(state) == "abstain":
        state.update(_abstain_response(state))
        return state

    state.update(_build_answer(state))
    state.update(_paraphrase(state))
    state.update(_finalize_success(state))
    return state


def run_analyze_pipeline(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry point used by main.py. `initial_state` must already contain
    `query`, `jurisdiction`, `language`, `confirmed_category`,
    `use_connector_id`, and `jur` (the already-resolved/validated
    jurisdiction name — jurisdiction.resolve_jurisdiction's ValueError is
    handled by the FastAPI layer before this is ever called).

    Returns a plain dict with exactly the fields of schemas.AnalyzeResponse
    (minus defaulted ones), regardless of which backend executed the graph.
    """
    if DAG_BACKEND == "langgraph" and _COMPILED_GRAPH is not None:
        final_state = _COMPILED_GRAPH.invoke(dict(initial_state))
    else:
        final_state = _run_sequential(dict(initial_state))
    return final_state["response"]
