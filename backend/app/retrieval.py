"""Jurisdiction-isolated TF-IDF retrieval implemented with the Python stdlib."""
import json
import logging
import math
import os
import re
from collections import Counter
from typing import Any, Dict, List, Union

logger = logging.getLogger("ip_sakti.retrieval")
_CORPUS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "corpus.json")
with open(_CORPUS_PATH, "r", encoding="utf-8") as f:
    _CORPUS: List[Dict[str, Any]] = json.load(f)
_CORPUS_BY_ID = {doc["id"]: doc for doc in _CORPUS}
# Give the source title and section more weight than explanatory prose so a
# focused query for a named instrument ranks its governing source first.
_DOC_TEXTS = [
    f"{d['title']} {d['title']} {d['title']} {d['section']} {d['section']} {d['summary']} {d['domain']}"
    for d in _CORPUS
]
BACKEND = "tfidf-stdlib"
_TOKEN = re.compile(r"[a-z]+")
_STOP_WORDS = set("a an and are as at be by for from has have in into is it of on or that the this to was were will with".split())


def _light_stem(token: str) -> str:
    for suffix in ("abilities", "ability", "ization", "ations", "ation", "ing", "ies", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[:-len(suffix)]
    return token


def _tokenizer(text: str) -> List[str]:
    return [_light_stem(word) for word in _TOKEN.findall((text or "").lower()) if word not in _STOP_WORDS]


def _fit_idf(documents: List[str]) -> Dict[str, float]:
    df = Counter(term for text in documents for term in set(_tokenizer(text)))
    count = max(1, len(documents))
    return {term: math.log((1 + count) / (1 + freq)) + 1.0 for term, freq in df.items()}


_IDF = _fit_idf(_DOC_TEXTS)


def get_document(doc_id: str):
    return _CORPUS_BY_ID.get(doc_id)


def _tfidf(text: str) -> Dict[str, float]:
    # Ignore query terms absent from the corpus. Besides reducing noise, this
    # prevents names and other persona-only words from lowering all scores
    # enough to change which evidence clears the retrieval threshold.
    counts = Counter(term for term in _tokenizer(text) if term in _IDF)
    weights = {term: (1.0 + math.log(freq)) * _IDF.get(term, 1.0) for term, freq in counts.items()}
    norm = math.sqrt(sum(value * value for value in weights.values()))
    return {term: value / norm for term, value in weights.items()} if norm else {}


_DOC_VECTORS = [_tfidf(text) for text in _DOC_TEXTS]


def _cosine(left: Dict[str, float], right: Dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(term, 0.0) for term, value in left.items())


def _retrieve_tfidf(variants: List[str], jurisdiction: str, areas: List[str], top_k: int) -> List[Dict[str, Any]]:
    candidate_idx = [i for i, doc in enumerate(_CORPUS) if doc["jurisdiction"] == jurisdiction]
    if not candidate_idx:
        return []
    query_vectors = [_tfidf(text) for text in variants]
    primary_source_types = {"statute", "regulation", "directive", "treaty"}
    seeks_binding_rule = any(
        {"requirement", "requirements", "regulation", "regulations", "legislation", "statute", "directive"}
        & set(_tokenizer(text))
        for text in variants
    )
    scored = []
    for index in candidate_idx:
        doc = _CORPUS[index]
        raw = max((_cosine(query, _DOC_VECTORS[index]) for query in query_vectors), default=0.0)
        score = raw + (0.15 if doc["domain"] in areas and raw > 0.02 else 0.0)
        if seeks_binding_rule and doc.get("source_type", "").lower() in primary_source_types:
            score += 0.12
        scored.append((score, doc))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for score, doc in scored[:max(0, top_k)]:
        if score > 0.05:
            result = dict(doc)
            result["relevance_score"] = round(min(score, 0.99), 3)
            results.append(result)
    return results


def retrieve(query: Union[str, List[str]], jurisdiction: str, areas: List[str], top_k: int = 5) -> List[Dict[str, Any]]:
    """Return lexical TF-IDF matches, always filtered to the requested jurisdiction."""
    variants = query if isinstance(query, (list, tuple)) else [query]
    variants = [value for value in variants if isinstance(value, str) and value.strip()]
    return _retrieve_tfidf(variants, jurisdiction, areas, top_k) if variants else []
