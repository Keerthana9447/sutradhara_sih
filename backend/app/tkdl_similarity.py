"""
Prior-art / TKDL-style resemblance scoring.

This is NOT a connection to the real, access-restricted TKDL database (see
answer.build_tk_pointer, which already says so explicitly). It is a small,
honestly-scoped enhancement: TF-IDF cosine similarity between the user's
described formulation and a short reference list of well-known, publicly
documented classical Ayurvedic formulations, giving a *quantified*
"resemblance to known traditional knowledge" signal instead of only a
pointer link.

Scope and limits, stated up front because they matter for how this is
presented in the UI:
  - The reference set below has {n} entries. It is illustrative, not
    exhaustive — a low score means "not similar to this small reference
    set", never "not traditional knowledge" or "safe to patent".
  - This must never be presented as a substitute for an actual TKDL search.
  - Reuses the same TfidfVectorizer already a project dependency
    (scikit-learn) rather than adding a new one.
"""
from typing import List, Dict, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Small, real, publicly documented reference set of classical Ayurvedic
# formulations (names and one-line compositions are well-known / textbook
# facts, not derived from any single proprietary source). Kept short and
# clearly labelled as illustrative rather than exhaustive.
REFERENCE_FORMULATIONS = [
    {"name": "Triphala Churna", "description": "Classical powder formulation of amalaki, bibhitaki, and haritaki fruits, used as a digestive and rasayana."},
    {"name": "Chyawanprash", "description": "Classical herbal jam formulation based on amla (Indian gooseberry) with a large group of supporting herbs and spices, used as a general rasayana tonic."},
    {"name": "Ashwagandharishta", "description": "Classical fermented liquid formulation based on ashwagandha root, used as a rejuvenative and strength-promoting tonic."},
    {"name": "Dashamularishta", "description": "Classical fermented liquid formulation based on ten root drugs (dashamula), used post-partum and for general debility."},
    {"name": "Brahmi Ghrita", "description": "Classical medicated ghee formulation based on brahmi (Bacopa monnieri), used for memory and nervous system support."},
    {"name": "Sitopaladi Churna", "description": "Classical powder formulation based on sugar candy, bamboo manna, pepper, and cardamom, used for cough and respiratory conditions."},
    {"name": "Trikatu Churna", "description": "Classical powder formulation of three pungent herbs — black pepper, long pepper, and ginger — used to stimulate digestion."},
    {"name": "Yograj Guggulu", "description": "Classical tablet formulation based on purified guggulu resin with numerous supporting herbs, used for joint and musculoskeletal conditions."},
    {"name": "Arjunarishta", "description": "Classical fermented liquid formulation based on arjuna bark, used for cardiovascular support."},
    {"name": "Saraswatarishta", "description": "Classical fermented liquid formulation based on brahmi and supporting herbs, used for cognitive and nervous system support."},
]


def score_resemblance(description: str, top_k: int = 3, min_score: float = 0.12) -> List[Dict]:
    """
    Return up to top_k reference formulations whose description is most
    textually similar to the given formulation description, each with a
    0-1 cosine-similarity score. Entries below min_score are dropped rather
    than padded in — an empty list is a valid, honest result.
    """
    text = (description or "").strip()
    if not text:
        return []

    corpus = [r["description"] for r in REFERENCE_FORMULATIONS] + [text]
    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        # Empty vocabulary after stop-word removal (e.g. text was only
        # stop-words/punctuation) — no similarity signal, not an error.
        return []

    query_vec = matrix[-1]
    ref_vecs = matrix[:-1]
    sims = cosine_similarity(query_vec, ref_vecs)[0]

    ranked = sorted(
        (
            {"name": r["name"], "description": r["description"], "similarity": round(float(s), 3)}
            for r, s in zip(REFERENCE_FORMULATIONS, sims)
        ),
        key=lambda x: x["similarity"],
        reverse=True,
    )
    return [r for r in ranked if r["similarity"] >= min_score][:top_k]


# Only worth surfacing for categories where "is this already known TK?" is
# an actual live question — a cosmetic or nutraceutical query gets no
# resemblance panel at all, never a padded/irrelevant one.
_RELEVANT_CATEGORIES = {
    "Classical / Generic Medicine",
    "Patent / Proprietary Medicine",
    "New / Non-Classical Drug",
}


def maybe_score_resemblance(query: str, category: str) -> Optional[List[Dict]]:
    if category not in _RELEVANT_CATEGORIES:
        return None
    result = score_resemblance(query)
    return result if result else None
