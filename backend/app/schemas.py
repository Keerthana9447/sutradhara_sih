from typing import List, Optional, Literal
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
    query_depth: Literal["quick", "guided", "deep"] = "guided"


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
    # connector is active. Live provider results are kept separate from the
    # legal corpus sources and are explicitly marked as live or simulated.
    connector_source_used: Optional[dict] = None
    # Live, per-query explainability graph — built from what was ACTUALLY
    # retrieved for THIS query (see app/graph.py), distinct from the static
    # schema view at GET /api/graph and the manual what-if multi-hop tool at
    # POST /api/graph/reason. None only if graph construction itself failed
    # (never fabricated as a fallback).
    dynamic_graph: Optional[dict] = None
    # Non-blocking "always-current law" caveat (see app/corpus_freshness.py):
    # set only when one or more of the CITED sources for this answer have
    # not been re-verified against their authoritative source in over
    # SUTRADHARA_STALE_DAYS days. None means every cited source is within
    # the freshness window — never fabricated, never suppressed.
    stale_sources_warning: Optional[str] = None
    # Retrieval planning is model-driven only when explicitly enabled by the
    # deployment; source selection and answer generation remain corpus-bound.
    orchestration_mode: str = "deterministic_fallback"
    research_plan: List[dict] = Field(default_factory=list)
    query_depth: str = "guided"
    suggested_query_depth: Optional[str] = None
    eval_score: Optional[int] = None
    eval_method: Optional[str] = None
    eval_checks: Optional[dict] = None
    regime_verdicts: List[dict] = Field(default_factory=list)


class RegistryLookupRequest(BaseModel):
    jurisdiction: str = Field(..., description="'India' or 'International'")
    keyword: str = Field(..., description="Search term, e.g. a formulation or product name")
    registry: str = Field(default="patents", description="'patents' | 'trademarks' | 'gi' | 'abs' (India only; International is patents-only)")
    limit: int = Field(default=5, ge=1, le=20)


# --------------------------------------------------------------------------
# Privacy / data-governance rights — see app/privacy.py
# --------------------------------------------------------------------------
class PrivacyLookupRequest(BaseModel):
    query_text: Optional[str] = Field(default=None, description="The exact question you previously typed")
    contact_email: Optional[str] = Field(default=None, description="The email you supplied when escalating to a human")


# --- Consent Manager reference implementation (see app/privacy.py) --------
class ConsentRequestRequest(BaseModel):
    data_principal_ref: str = Field(..., description="How you identify yourself, e.g. the email you use for escalation")
    purpose: str = Field(..., description="Plain-language purpose this consent covers")
    data_categories: List[str] = Field(..., description="Categories of data this consent covers, e.g. ['query_text']")
    expires_in_days: Optional[int] = Field(default=None, description="Optional expiry; omit for no expiry")


class ConsentIdRequest(BaseModel):
    consent_id: str


class ConsentInfo(BaseModel):
    consent_id: str
    data_principal_ref: str
    purpose: str
    data_categories: List[str]
    data_fiduciary: str
    status: str
    requested_at: str
    granted_at: Optional[str] = None
    revoked_at: Optional[str] = None
    expires_at: Optional[str] = None


# --- DPIA / breach / ROPA (see app/privacy.py) -----------------------------
class DPIARequest(BaseModel):
    processing_activity: str
    risk_level: str = Field(..., description="'low' | 'medium' | 'high'")
    reviewer: Optional[str] = None
    mitigations: Optional[str] = None


class BreachReportRequest(BaseModel):
    description: str
    affected_categories: Optional[List[str]] = None
    severity: str = Field(default="unknown", description="'low' | 'medium' | 'high' | 'unknown'")


class BreachIdRequest(BaseModel):
    breach_id: str


class ProcessingActivityRequest(BaseModel):
    purpose: str
    data_categories: List[str]
    legal_basis: str
    retention_period_days: Optional[int] = None


# --- Cross-border transfer check (see app/privacy.py) ----------------------
class CrossBorderCheckRequest(BaseModel):
    destination_country: str
    purpose: Optional[str] = None
    data_categories: Optional[List[str]] = None


# --- Corpus auto-refresh (see app/corpus_freshness.py) ----------------------
class CorpusRefreshRequest(BaseModel):
    doc_ids: Optional[List[str]] = Field(default=None, description="Restrict to these corpus document ids; omit for all")


class CorpusRefreshApproveRequest(BaseModel):
    doc_id: str
    reviewer: str = Field(..., description="Name/identifier of the human approving this refresh")


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
    provider: str = Field(..., description="Provider name; 'USPTO PatentsView' enables the live US-patent adapter")
    api_key: str = Field(..., description="Provider API key; PatentsView keys are encrypted at rest and never returned")
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
    text: str = Field(..., min_length=1, max_length=2500)
    language: str = Field(default="en")
    speaker: str = Field(default="shubh")


class TTSResponse(BaseModel):
    audio_base64: str


class TranslateBatchRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1, max_length=100)
    target_language: str = Field(..., pattern="^(en|hi|te|ta|ml|sa)$")


# --------------------------------------------------------------------------
# Auth — Sign Up / Sign In
# --------------------------------------------------------------------------
class SignUpRequest(BaseModel):
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="Display name")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")


class SignInRequest(BaseModel):
    email: str
    password: str


class UserInfo(BaseModel):
    id: int
    email: str
    name: str


class AuthResponse(BaseModel):
    user: UserInfo
    token: str  # opaque session token stored client-side


# --------------------------------------------------------------------------
# Chat history
# --------------------------------------------------------------------------
class ChatSessionCreate(BaseModel):
    user_id: int
    title: Optional[str] = "New conversation"


class ChatSessionRename(BaseModel):
    user_id: int
    title: str


class ChatMessageAdd(BaseModel):
    session_id: int
    user_id: int
    role: str = Field(..., description="'user' | 'assistant'")
    content: str


class SessionAnalyzeRequest(AnalyzeRequest):
    """Extends the standard analyze request with session tracking."""
    session_id: Optional[int] = None
    user_id: Optional[int] = None


# --------------------------------------------------------------------------
# Citizen Claims Submission Workflow — /api/v1/claims
# --------------------------------------------------------------------------
class ClaimSubmitRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300, description="Short title for the claim")
    description: str = Field(..., min_length=1, max_length=12000, description="Detailed description of the formulation or TK")
    jurisdiction: str = Field(default="India")
    category: Optional[str] = Field(default=None, description="Product category if known")


class ClaimIdRequest(BaseModel):
    claim_id: str


# --------------------------------------------------------------------------
# Deep Patent Collision Radar — /api/v1/radar
# --------------------------------------------------------------------------
class RadarRequest(BaseModel):
    patent_title: str
    patent_abstract: str
    patent_claims: Optional[str] = None
    filing_office: str = Field(default="USPTO", description="e.g. 'USPTO', 'EPO', 'IPO'")
    filing_date: Optional[str] = None


# --------------------------------------------------------------------------
# Manuscript OCR / Digitisation — /api/v1/ocr
# --------------------------------------------------------------------------
class OCRRequest(BaseModel):
    image_base64: str = Field(..., min_length=1, max_length=7_000_000, description="Base64-encoded image, no data: URI prefix; maximum decoded size is 5 MiB")
    mime_type: Literal["image/jpeg", "image/png", "image/webp"] = Field(default="image/jpeg", description="Supported image MIME type")
    filename: Optional[str] = Field(default=None, max_length=255)


# --------------------------------------------------------------------------
# Admin / Ministry sign-up — /api/v1/auth/admin-signup
# --------------------------------------------------------------------------
class AdminSignUpRequest(BaseModel):
    email: str
    name: str
    password: str = Field(..., min_length=6)
    invite_code: str = Field(..., description="Ministry admin invite code")

