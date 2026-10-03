"""
Optional LLM paraphrasing layer — Groq.

Per ARCHITECTURE.md's own invariant (see answer.py docstring): the grounded
answer is assembled directly from retrieved source text so that "no
hallucinated law" holds even without an LLM. This module adds an *optional*
layer on top of that assembled text, using Groq's chat-completions API
(OpenAI-compatible) purely to smooth the prose into a single readable
paragraph-style assessment for the judge-facing UI.

Hard constraints enforced here, not just requested in the prompt:
  1. The LLM is never given retrieval, corpus, or "what does the law say"
     latitude — it receives the ALREADY-GROUNDED text and is instructed only
     to paraphrase it for readability.
  2. Every `[Source: ...]` citation tag, and every legal identifier inside it
     (Act name, Section/Article/Rule number), must survive unchanged. This is
     verified programmatically after the call (see `_citations_preserved`) —
     we do not simply trust the model's instruction-following. If the check
     fails, or the call fails/times out/is unconfigured, the ORIGINAL
     template-assembled answer is returned untouched. The pipeline behaves
     identically whether or not GROQ_API_KEY is set.
  3. This module only ever runs on the English-language grounded answer,
     BEFORE Telugu translation (see main.py) — so the multilingual pipeline
     and citation-preservation guarantees are unaffected either way.

Network note: this calls api.groq.com directly. If the deployment
environment has no outbound access to that host, the call fails and the
pipeline silently falls back to the template answer — never a crash, never a
missing response.
"""
import json
import os
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ip_sakti.llm")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()
_ENABLED = os.environ.get("ENABLE_LLM_PARAPHRASE", "true").strip().lower() not in ("0", "false", "no")
_RESEARCH_PLANNER_ENABLED = os.environ.get(
    "ENABLE_LLM_RESEARCH_PLANNER", "false"
).strip().lower() in ("1", "true", "yes")
_TIMEOUT_SECONDS = float(os.environ.get("GROQ_TIMEOUT_SECONDS", "12"))

_RESEARCH_PLANNER_SYSTEM_PROMPT = (
    "You are a bounded research-planning component for an IP-law information system. "
    "Return only valid JSON with exactly the top-level keys 'done' and 'steps'. "
    "'done' must be a boolean; 'steps' must be a JSON array. "
    "Plan corpus searches, then adapt the next search to observed search results. "
    "You do not answer the legal question or state legal conclusions. Use only the "
    "supplied allowed areas. Each step must call the search_corpus tool with one "
    "allowed area and a concise search query derived from the question. On a follow-up "
    "round, set done=true and return no steps if the evidence is adequate; otherwise "
    "propose only the remaining allowed step. Do not invent sources, facts, "
    "jurisdictions, or legal propositions."
)

_SYSTEM_PROMPT = (
    "You are a formatting and readability assistant for a legal-information "
    "system. You will be given an already-grounded, already-cited answer "
    "assembled from retrieved statutory/treaty sources. Your ONLY job is to "
    "rephrase it into clearer, more natural prose for a reader. You must NOT:\n"
    "- add any new legal claim, fact, statute, section, treaty, or citation "
    "that is not already present in the input text\n"
    "- remove, renumber, translate, or alter any '[Source: ...]' tag, or any "
    "Act name, Section/Article/Rule/Treaty number inside it\n"
    "- change the substantive meaning of any sentence\n"
    "- add a preamble, apology, or any text outside the rewritten answer\n"
    "Every '[Source: ...]' tag from the input MUST appear verbatim, in the "
    "same order, in your output. If you are not confident you can do this "
    "safely, return the input text unchanged."
)

_CITATION_TAG_RE = re.compile(r"\[Source:[^\]]+\]")


def _validate_research_plan(
    payload: object, allowed_areas: List[str], max_steps: int = 3,
) -> Optional[List[Dict[str, str]]]:
    """Accept only bounded corpus-search calls within the deterministic route."""
    if not isinstance(payload, dict):
        return None
    raw_steps = payload.get("steps")
    done = payload.get("done", False)
    if not isinstance(raw_steps, list) or not isinstance(done, bool):
        return None
    if done:
        return [] if not raw_steps else None
    if not 1 <= len(raw_steps) <= max_steps:
        return None

    validated: List[Dict[str, str]] = []
    seen = set()
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict) or raw_step.get("tool") != "search_corpus":
            return None
        area = raw_step.get("area")
        query = raw_step.get("query")
        if not isinstance(area, str) or area not in allowed_areas:
            return None
        if not isinstance(query, str):
            return None
        query = " ".join(query.split())
        if not query or len(query) > 240:
            return None
        key = (area, query.casefold())
        if key not in seen:
            validated.append({"tool": "search_corpus", "area": area, "query": query})
            seen.add(key)
    return validated


def plan_research(
    query: str,
    jurisdiction: str,
    allowed_areas: List[str],
    observations: Optional[List[Dict[str, Any]]] = None,
    prior_steps: Optional[List[Dict[str, str]]] = None,
    max_steps: int = 2,
) -> Tuple[List[Dict[str, str]], str]:
    """Plan/adapt bounded corpus searches, or report deterministic fallback mode.

    Sending a query to Groq is an explicit deployment opt-in through
    ENABLE_LLM_RESEARCH_PLANNER and GROQ_API_KEY. The LLM can only propose
    search queries for already-routed areas; it cannot add sources or author
    answer content. When observations are provided, this is the one allowed
    follow-up planning round after corpus-search results have been reviewed.
    """
    if (
        not _RESEARCH_PLANNER_ENABLED
        or not GROQ_API_KEY
        or not allowed_areas
        or not 1 <= max_steps <= 3
    ):
        return [], "deterministic_fallback"

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed; using deterministic retrieval planning.")
        return [], "deterministic_fallback"

    try:
        response = httpx.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"******",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "temperature": 0,
                "max_tokens": 500,
                "messages": [
                    {"role": "system", "content": _RESEARCH_PLANNER_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "query": query,
                                "jurisdiction": jurisdiction,
                                "allowed_areas": allowed_areas,
                                "observations": observations or [],
                                "prior_steps": prior_steps or [],
                                "max_steps": max_steps,
                                "required_shape": {
                                    "done": False,
                                    "steps": [
                                        {
                                            "tool": "search_corpus",
                                            "area": "one allowed area",
                                            "query": "concise search query",
                                        }
                                    ]
                                },
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            },
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        plan = _validate_research_plan(
            json.loads(content), allowed_areas, max_steps=max_steps,
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        logger.warning("Groq research planner failed validation or request: %r; using deterministic planning.", e)
        return [], "deterministic_fallback"

    if plan is None:
        logger.warning("Groq research planner returned no valid steps; using deterministic planning.")
        return [], "deterministic_fallback"
    if observations is None and not plan:
        logger.warning("Groq research planner proposed no initial search; using deterministic planning.")
        return [], "deterministic_fallback"
    return plan, "agentic_groq"


def _extract_citation_tags(text: str) -> List[str]:
    return _CITATION_TAG_RE.findall(text)


def _citations_preserved(original: str, candidate: str) -> bool:
    """
    The single non-negotiable safety check: every citation tag from the
    original grounded text must appear, verbatim, in the candidate — same
    set, same multiset (a tag dropped or duplicated is also a failure).
    Order is not required (a paraphrase may reasonably reorder sentences),
    but content must be exact, since these tags are the traceability
    guarantee back to a specific retrieved source.
    """
    original_tags = sorted(_extract_citation_tags(original))
    candidate_tags = sorted(_extract_citation_tags(candidate))
    return bool(original_tags) and original_tags == candidate_tags


def paraphrase_answer(grounded_text: str) -> Tuple[str, bool]:
    """
    Returns (text, used_llm). On any failure, disablement, or missing
    config, returns (grounded_text, False) unchanged — this function must
    never be able to make the answer less grounded than its input.
    """
    if not _ENABLED or not GROQ_API_KEY or not grounded_text.strip():
        return grounded_text, False

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed; skipping Groq paraphrase layer.")
        return grounded_text, False

    try:
        response = httpx.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "temperature": 0.2,
                "max_tokens": 1200,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": grounded_text},
                ],
            },
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        candidate = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # Broad on purpose: covers no network route to api.groq.com, DNS
        # failure, timeout, rate limiting, malformed response, missing/
        # revoked key, model-not-found, etc. All of these mean "fall back
        # to the grounded template answer", none of them a request failure.
        logger.info("Groq paraphrase call failed or unavailable: %r. Using grounded template answer.", e)
        return grounded_text, False

    if not candidate or not _citations_preserved(grounded_text, candidate):
        logger.warning(
            "Groq paraphrase output failed citation-preservation check; "
            "discarding and using the grounded template answer instead."
        )
        return grounded_text, False

    return candidate, True
