from typing import List, Optional
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    query: str
    jurisdiction: str = Field(..., description="'India' or 'International'")
    language: str = Field(default="en", description="'en', 'te', 'hi', 'ta', 'ml', or 'sa'")
    # Optional pre-confirmed classification (from the clarification step)
    confirmed_category: Optional[str] = None
    # Optional: use the caller's own linked paid-subscription connector for
    # this one query (see app/connectors.py). Every use is explicitly opt-in
    # per request — never silently applied to every query just because a
    # connector exists — and every use is logged.
    use_connector_id: Optional[str] = None


class ClassificationResult(BaseModel):
    category: str
    confidence: float
    reason: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


class SourceRef(BaseModel):
    id: str
    title: str
    section: str
    authority: str
    jurisdiction: str
    domain: str
    source_type: str
    version_date: str
    retrieved_date: str
    source_url: str
    precision: str
    relevance_score: float


class AbsChecklist(BaseModel):
    biological_resource_involved: bool
    provenance_identified: bool
    abs_framework_identified: bool
    supporting_source_retrieved: bool
    note: str = "Potentially relevant — verify applicability with the competent authority."


class AnalyzeResponse(BaseModel):
    classification: ClassificationResult
    jurisdiction: str
    applicable_areas: List[str]
    answer: str
    confidence: float
    confidence_label: str
    confidence_breakdown: dict
    sources: List[SourceRef]
    abs_checklist: Optional[AbsChecklist] = None
    tk_pointer: Optional[str] = None
    abstained: bool
    disclaimer: str = "Information, not legal advice."
    answer_language: str = "en"
    translation_available: bool = True
    # Multilingual-pipeline transparency fields (see main.py debug logging).
    # input_language is detected from the query TEXT, independent of the
    # requested output `language` — the two can differ in principle.
    input_language: str = "en"
    retrieval_query: Optional[str] = None
    # True only if the Groq paraphrase layer ran AND passed its
    # citation-preservation check (see app/llm.py). False means the answer
    # is exactly the template-assembled, source-grounded text.
    llm_paraphrased: bool = False
    # Deterministic, rule-based next-step sequence for this category +
    # jurisdiction (see app/pathway.py). Empty list if none is defined —
    # never fabricated.
    regulatory_pathway: List[str] = []
    # TF-IDF resemblance to a small curated reference set of well-known
    # classical formulations (see app/tkdl_similarity.py). None when not
    # applicable to this category, or when nothing cleared the similarity
    # floor — never padded with a weak match.
    tk_similarity: Optional[List[dict]] = None
    # Present only when use_connector_id was set on the request AND the
    # connector is active. Clearly tagged as a simulated/prototype hit — see
    # app/connectors.py docstring for exactly what is and isn't real here.
    connector_source_used: Optional[dict] = None
    # Live, per-query explainability graph — built from what was ACTUALLY
    # retrieved for THIS query (see app/graph.py), distinct from the static
    # schema view at GET /api/graph and the manual what-if multi-hop tool at
    # POST /api/graph/reason. None only if graph construction itself failed
    # (never fabricated as a fallback).
    dynamic_graph: Optional[dict] = None


class EscalateRequest(BaseModel):
    query: str
    product_category: Optional[str] = None
    jurisdiction: Optional[str] = None
    relevant_ip_area: Optional[List[str]] = None
    retrieved_sources: Optional[List[str]] = None
    contact_email: Optional[str] = None


class FeedbackRequest(BaseModel):
    query: str
    answer_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class PostureRequest(BaseModel):
    """Body for /api/posture-pdf. `result` is exactly the AnalyzeResponse
    JSON the frontend already received from /api/analyze — the PDF is
    rendered from that, not recomputed, so it can never drift from what the
    user actually saw on screen."""
    query: str
    result: dict


# --------------------------------------------------------------------------
# Paid-subscription connector (consent-logged, user-linked) — see connectors.py
# --------------------------------------------------------------------------
class ConnectorLinkRequest(BaseModel):
    provider: str = Field(..., description="Name of the user's own paid IP-data provider, e.g. 'PatSeer', 'Derwent Innovation'")
    api_key: str = Field(..., description="The user's own subscription API key. Never stored or logged in full — see connectors.py")
    scope: str = Field(default="patent_search", description="What this connector may be used for")
    contact_email: Optional[str] = None


class ConnectorInfo(BaseModel):
    connector_id: str
    provider: str
    scope: str
    status: str  # "active" | "revoked"
    linked_at: str
    revoked_at: Optional[str] = None
    key_fingerprint: str  # last 4 characters only — proves which key without exposing it


class ConnectorRevokeRequest(BaseModel):
    connector_id: str


# --------------------------------------------------------------------------
# Multi-hop graph reasoning — see graph_reasoning.py
# --------------------------------------------------------------------------
class GraphReasonRequest(BaseModel):
    category: str = Field(..., description="One of classifier.CATEGORIES")
    jurisdiction: str = Field(..., description="'India' or 'International' — the product's home jurisdiction")
    export_intent: bool = Field(default=False, description="If true, also chain into the OTHER jurisdiction's export-readiness requirements, kept as a separate graph branch")


# --------------------------------------------------------------------------
# Voice input (Sarvam Saaras/Bulbul) — see app/asr.py
# --------------------------------------------------------------------------
class ASRRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded audio, no data: URI prefix")
    source_language: str = Field(default="en", description="'en', 'hi', 'te', 'ta', or 'ml' — language actually spoken")
    audio_format: str = Field(default="wav", description="Audio container/codec, e.g. 'wav', 'webm'")
    sampling_rate: int = Field(default=16000, description="Audio sample rate in Hz")


class ASRResponse(BaseModel):
    text: str
    transcribed_ok: bool
    source_language: str


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=2500)
    language: str = Field(default="en")
    speaker: str = Field(default="shubh")


class TTSResponse(BaseModel):
    audio_base64: str
