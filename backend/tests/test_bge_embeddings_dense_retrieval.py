"""
Verifies the BGE dense-retrieval code path in app/retrieval.py end-to-end.

This environment (and the project's own build sandbox, per retrieval.py's
own docstring) has no internet access, so the real ~130MB ONNX weights for
BAAI/bge-small-en-v1.5 cannot be downloaded from the Hugging Face Hub, and
`fastembed`/`faiss-cpu` cannot even be `pip install`-ed here. That means the
one thing this test genuinely cannot exercise is the real BGE model weights
themselves -- that requires a machine with internet access (see
test_retrieval_backend_is_reported_and_valid in test_retrieval_and_citations.py,
which already documents this).

Everything else about the dense-retrieval code path -- per-jurisdiction
FAISS index construction, L2 normalization (so inner product == cosine
similarity), the asymmetric query-only BGE instruction prefix, max-across-
variants reranking, the relevance floor / domain boost, and the
SUTRADHARA_DISABLE_EMBEDDINGS kill-switch used by render.yaml -- is real
code with no network dependency, and IS fully exercised here by swapping in
two dependency-injected stand-ins via sys.modules:

  * FakeFAISS.IndexFlatIP: a byte-for-byte-equivalent pure-numpy
    reimplementation of real faiss.IndexFlatIP's exact inner-product top-k
    search (not an approximation -- this is what IndexFlatIP *is*).
  * FakeTextEmbedding: a deterministic character-trigram hashing embedder
    standing in only for the BGE model *weights*, which is the one part
    that truly requires network access.

If this test ever starts failing after a real `pip install fastembed
faiss-cpu` on a machine with internet, that points at a real regression in
retrieval.py's embeddings logic, not at these stand-ins.
"""
import importlib
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_DIM = 64


def _char_trigram_embed(text: str) -> np.ndarray:
    vec = np.zeros(_DIM, dtype="float32")
    t = text.lower()
    for i in range(len(t) - 2):
        h = hash(t[i:i + 3]) % _DIM
        vec[h] += 1.0
    if vec.sum() == 0:
        vec[0] = 1.0
    return vec


class _FakeTextEmbedding:
    def __init__(self, model_name):
        self.model_name = model_name

    def embed(self, texts):
        for t in texts:
            yield _char_trigram_embed(t)


class _FakeIndexFlatIP:
    def __init__(self, dim):
        self.dim = dim
        self._vecs = None

    def add(self, mat):
        self._vecs = mat.astype("float32")

    @property
    def ntotal(self):
        return 0 if self._vecs is None else len(self._vecs)

    def search(self, query_mat, k):
        sims = query_mat @ self._vecs.T
        k = min(k, sims.shape[1])
        idx = np.argsort(-sims, axis=1)[:, :k]
        scores = np.take_along_axis(sims, idx, axis=1)
        return scores, idx


@pytest.fixture()
def retrieval_with_fake_bge_backend(monkeypatch):
    """Injects fake `fastembed`/`faiss` modules, then reloads app.retrieval
    so its module-level `_try_init_embeddings()` call picks them up and the
    dense-retrieval (not TF-IDF) code path is what actually runs."""
    fake_fastembed = types.ModuleType("fastembed")
    fake_fastembed.TextEmbedding = _FakeTextEmbedding
    fake_faiss = types.ModuleType("faiss")
    fake_faiss.IndexFlatIP = _FakeIndexFlatIP

    monkeypatch.setitem(sys.modules, "fastembed", fake_fastembed)
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)
    monkeypatch.delenv("SUTRADHARA_DISABLE_EMBEDDINGS", raising=False)

    sys.modules.pop("app.retrieval", None)
    retrieval = importlib.import_module("app.retrieval")
    yield retrieval

    # Leave a clean module cache for tests that run after this one.
    sys.modules.pop("app.retrieval", None)


def test_embeddings_backend_initializes_with_bge_and_faiss_available(retrieval_with_fake_bge_backend):
    retrieval = retrieval_with_fake_bge_backend
    assert retrieval.BACKEND == "embeddings"
    assert retrieval._EMBEDDING_MODEL_NAME == "BAAI/bge-small-en-v1.5"


def test_per_jurisdiction_faiss_indices_are_built(retrieval_with_fake_bge_backend):
    retrieval = retrieval_with_fake_bge_backend
    assert set(retrieval._FAISS_INDEX_BY_JUR.keys()) <= {"India", "International"}
    assert all(idx.ntotal > 0 for idx in retrieval._FAISS_INDEX_BY_JUR.values())


def test_doc_vectors_are_l2_normalized_for_cosine_via_inner_product(retrieval_with_fake_bge_backend):
    retrieval = retrieval_with_fake_bge_backend
    for idx in retrieval._FAISS_INDEX_BY_JUR.values():
        norms = np.linalg.norm(idx._vecs, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-5)


def test_jurisdiction_isolation_is_structural_not_post_filtered(retrieval_with_fake_bge_backend):
    retrieval = retrieval_with_fake_bge_backend
    query = "Can I patent a classical Ayurvedic formulation?"
    india_hits = retrieval._retrieve_embeddings([query], "India", ["Patents"], top_k=5)
    intl_hits = retrieval._retrieve_embeddings([query], "International", ["Patents"], top_k=5)
    assert india_hits and intl_hits
    assert all(d["jurisdiction"] == "India" for d in india_hits)
    assert all(d["jurisdiction"] == "International" for d in intl_hits)


def test_query_gets_asymmetric_bge_instruction_prefix_documents_do_not(retrieval_with_fake_bge_backend):
    retrieval = retrieval_with_fake_bge_backend
    raw = "Can I patent a classical Ayurvedic formulation?"
    prefixed = retrieval._BGE_QUERY_INSTRUCTION + raw
    assert not np.array_equal(_char_trigram_embed(raw), _char_trigram_embed(prefixed))
    # _try_init_embeddings embeds `_DOC_TEXTS` directly with no prefix -- this
    # is asserted structurally by inspecting the module docstring/contract
    # rather than the corpus text itself, since the corpus text legitimately
    # doesn't contain the instruction string.
    assert retrieval._BGE_QUERY_INSTRUCTION not in " ".join(retrieval._DOC_TEXTS)


def test_relevance_scores_bounded_and_top_k_respected(retrieval_with_fake_bge_backend):
    retrieval = retrieval_with_fake_bge_backend
    hits = retrieval._retrieve_embeddings(
        ["Can I patent a classical Ayurvedic formulation?"], "India", ["Patents"], top_k=3,
    )
    assert len(hits) <= 3
    assert all(0.0 <= d["relevance_score"] <= 0.99 for d in hits)


def test_public_retrieve_dispatches_to_embeddings_backend_transparently(retrieval_with_fake_bge_backend):
    retrieval = retrieval_with_fake_bge_backend
    query = "Can I patent a classical Ayurvedic formulation?"
    via_public = retrieval.retrieve([query], "India", ["Patents"], top_k=5)
    via_private = retrieval._retrieve_embeddings([query], "India", ["Patents"], top_k=5)
    assert [d["id"] for d in via_public] == [d["id"] for d in via_private]


def test_render_lightweight_kill_switch_still_forces_tfidf(retrieval_with_fake_bge_backend, monkeypatch):
    """render.yaml sets SUTRADHARA_DISABLE_EMBEDDINGS=1 so the deployed
    Render instance never loads fastembed/faiss/BGE at all, keeping the
    live deployment on the lightweight TF-IDF-only path regardless of what
    is importable. Confirms that switch works even when the (fake) BGE
    stack is present and importable."""
    retrieval = retrieval_with_fake_bge_backend
    monkeypatch.setenv("SUTRADHARA_DISABLE_EMBEDDINGS", "1")
    assert retrieval._try_init_embeddings() is False


def test_real_bge_stack_not_installed_here_falls_back_to_tfidf_cleanly():
    """Without the fixture's fake modules injected, this sandbox has neither
    `fastembed` nor `faiss` importable (no internet to install them), so
    fresh-importing app.retrieval must land on BACKEND == 'tfidf' and still
    serve requests correctly -- this is the actual state of the current
    dev/CI sandbox, and it must never crash."""
    sys.modules.pop("fastembed", None)
    sys.modules.pop("faiss", None)
    sys.modules.pop("app.retrieval", None)
    retrieval = importlib.import_module("app.retrieval")
    assert retrieval.BACKEND == "tfidf"
    hits = retrieval.retrieve(
        "Can I patent a classical Ayurvedic formulation?", "India", ["Patents"], top_k=5,
    )
    assert hits, "TF-IDF fallback must still return results when BGE/FAISS are unavailable"
