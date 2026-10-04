import logging
import hmac
import os
import base64
import binascii
from contextlib import asynccontextmanager
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()  # loads backend/.env (GROQ_API_KEY, GROQ_MODEL, ...) if present
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from . import jurisdiction, retrieval, db, translate, posture_pdf
from . import graph_reasoning, eval_runner, connectors, graph, asr, dag
from . import corpus_freshness, privacy, registry_lookup, graph_store, gi_registry, auth, bias_audit
from . import claims_workflow, radar, ocr_digitize, admin_auth, patents_registry, features
from . import dossiers, prahari
from .schemas import (
    AnalyzeRequest, AnalyzeResponse, SourceRef,
    EscalateRequest, FeedbackRequest, PostureRequest,
    ConnectorLinkRequest, ConnectorInfo, ConnectorRevokeRequest,
    GraphReasonRequest, ASRRequest, ASRResponse, TTSRequest, TTSResponse,
    RegistryLookupRequest, PrivacyLookupRequest,
    ConsentRequestRequest, ConsentIdRequest, DPIARequest, BreachReportRequest,
    BreachIdRequest, ProcessingActivityRequest, CrossBorderCheckRequest,
    CorpusRefreshRequest, CorpusRefreshApproveRequest,
    SignUpRequest, SignInRequest, AuthResponse, UserInfo,
    ChatSessionCreate, ChatSessionRename, ChatMessageAdd, SessionAnalyzeRequest,
    ClaimSubmitRequest, ClaimIdRequest, RadarRequest,
    OCRRequest, AdminSignUpRequest,
    TranslateBatchRequest,
    DossierCreateRequest, DossierUpdateRequest, DossierClassifyRequest,
    DossierReviewRequest, PrahariAlertCreateRequest,
)

@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    admin_auth.ensure_role_column()
    yield


app = FastAPI(title="SUTRADHARA API", version="0.1.0-prototype", lifespan=lifespan)

@app.get("/")
def root():
    return {"service": "sutradhara-backend", "status": "ok"}

logger = logging.getLogger("ip_sakti.pipeline")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    freshness = corpus_freshness.freshness_report()
    bhashini_nmt = translate.bhashini_status()
    sarvam_nmt = translate.sarvam_translate_status()
    bhashini_asr = asr.bhashini_asr_status()
    sarvam_voice = asr.asr_status()
    bhashini_tts = asr.bhashini_tts_status()
    patentsview = registry_lookup.patentsview_status()
    gi_status = gi_registry.status()
    return {
        "status": "ok",
        "corpus_documents": len(retrieval._CORPUS),
        "stale_corpus_documents": freshness["counts"]["stale"],
        "retrieval_backend": retrieval.BACKEND,
        "dag_backend": dag.DAG_BACKEND,
        "graph_backend": graph_store.GRAPH_BACKEND,
        "sarvam_translate": sarvam_nmt,
        "bhashini": bhashini_nmt,
        "sarvam_voice": sarvam_voice,
        "bhashini_voice": bhashini_asr,
        "bhashini_tts": bhashini_tts,
        "patentsview": patentsview,
        "integrations": {
            "core_analysis": {
                "mode": "LIVE",
                "detail": "Local deterministic classification, retrieval, citation assembly, and abstention.",
            },
            "retrieval": {
                "mode": "LIVE" if retrieval.BACKEND == "bge-fastembed+tfidf" else "FALLBACK",
                "backend": retrieval.BACKEND,
            },
            "translation": {
                "mode": "CONFIGURED" if (
                    bhashini_nmt.get("configured") or sarvam_nmt.get("configured")
                ) else "FALLBACK",
                "bhashini_configured": bool(bhashini_nmt.get("configured")),
                "sarvam_configured": bool(sarvam_nmt.get("configured")),
                "offline_fallback": "English display plus local query normalization; quality is limited.",
            },
            "asr": {
                "mode": "CONFIGURED" if (
                    bhashini_asr.get("configured") or sarvam_voice.get("configured")
                ) else "FALLBACK",
                "bhashini_configured": bool(bhashini_asr.get("configured")),
                "sarvam_configured": bool(sarvam_voice.get("configured")),
                "supported_languages": list(asr.SUPPORTED_ASR_LANGUAGES),
            },
            "tts": {
                "mode": "CONFIGURED" if (
                    bhashini_tts.get("configured") or sarvam_voice.get("configured")
                ) else "FALLBACK",
                "bhashini_configured": bool(bhashini_tts.get("configured")),
                "sarvam_configured": bool(sarvam_voice.get("configured")),
                "supported_languages": ["en", "hi", "te", "ta", "ml", "sa"],
                "sanskrit_note": "Provider voices may use a Hindi approximation; verify provider coverage.",
            },
            "tkdl": {
                "mode": "REFERENCE_ONLY",
                "connected": False,
                "detail": "The real TKDL is access-restricted and is not queried by this prototype.",
            },
            "india_patent_trademark_registry": {
                "mode": "FALLBACK",
                "live_search": False,
                "detail": "Public official portal deep links only; no structured search API is connected.",
            },
            "gi_registry": {
                "mode": "LIVE_CACHE" if gi_status.get("built") else "FALLBACK",
                "cache_built": bool(gi_status.get("built")),
                "entry_count": gi_status.get("entry_count", 0),
            },
            "patentsview": {
                "mode": "LIVE_CONFIGURED" if patentsview.get("configured") else "FALLBACK",
                "configured": bool(patentsview.get("configured")),
                "detail": "Configured status only; actual live queries remain explicitly opt-in.",
            },
            "graph": {
                "mode": "LIVE" if graph_store.GRAPH_BACKEND == "neo4j" else "REFERENCE",
                "backend": graph_store.GRAPH_BACKEND,
                "detail": "The /api/graph endpoint is a static schema view; query reasoning uses Neo4j only when available.",
            },
        },
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """
    Thin HTTP adapter. All pipeline logic (language normalization, query
    expansion, classification, retrieval, confidence scoring, evidence
    enrichment, bounded retrieval planning, answer generation, paraphrasing,
    translation) lives in the LangGraph DAG defined in app/dag.py — see that
    module's docstring for the explicit planner opt-in and deterministic
    fallback behavior.
    Jurisdiction resolution stays here because it can raise a client-facing
    400, which belongs at the HTTP layer, not inside the pipeline graph.
    """
    try:
        jur = jurisdiction.resolve_jurisdiction(req.jurisdiction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    initial_state = {
        "query": req.query,
        "jurisdiction": req.jurisdiction,
        "language": req.language,
        "confirmed_category": req.confirmed_category,
        "use_connector_id": req.use_connector_id,
        "query_depth": req.query_depth,
        "external_processing_consent": req.external_processing_consent,
        "jur": jur,
    }
    response_fields = dag.run_analyze_pipeline(initial_state)
    features.annotate_analysis(response_fields, req.query_depth)
    return AnalyzeResponse(**response_fields)


@app.post("/api/query")
def query_alias(req: AnalyzeRequest):
    """Alias kept for architecture-spec compatibility; behaves like /api/analyze."""
    return analyze(req)


@app.get("/api/sources/{doc_id}")
def get_source(doc_id: str):
    doc = retrieval.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Source not found")
    return doc


@app.get("/api/graph")
def get_graph():
    """Static explainability graph for the prototype UI (mirrors graph/schema.cypher)."""
    return {
        "mode": "REFERENCE",
        "live_government_data": False,
        "nodes": [
            {"id": "product", "label": "Ayurvedic Product", "type": "Product"},
            {"id": "category", "label": "Product Category", "type": "ProductCategory"},
            {"id": "tk", "label": "Traditional Knowledge", "type": "TraditionalKnowledge"},
            {"id": "regime", "label": "IP/Regulatory Regime", "type": "IPRegime"},
            {"id": "law", "label": "Governing Law", "type": "Law"},
            {"id": "provision", "label": "Provision", "type": "Provision"},
            {"id": "source", "label": "Authoritative Source", "type": "Source"},
        ],
        "edges": [
            {"from": "product", "to": "category", "label": "belongs_to", "confidence": 1.0, "provenance": {"basis": "static_schema", "reference": "graph/schema.cypher"}},
            {"from": "category", "to": "regime", "label": "relevant_to", "confidence": 1.0, "provenance": {"basis": "static_schema", "reference": "graph/schema.cypher"}},
            {"from": "category", "to": "tk", "label": "may_reference", "confidence": 1.0, "provenance": {"basis": "static_schema", "reference": "graph/schema.cypher"}},
            {"from": "regime", "to": "law", "label": "governed_by", "confidence": 1.0, "provenance": {"basis": "static_schema", "reference": "graph/schema.cypher"}},
            {"from": "law", "to": "provision", "label": "contains", "confidence": 1.0, "provenance": {"basis": "static_schema", "reference": "graph/schema.cypher"}},
            {"from": "provision", "to": "source", "label": "supported_by", "confidence": 1.0, "provenance": {"basis": "static_schema", "reference": "graph/schema.cypher"}},
        ],
        "note": "Static schema/reference view, not live government data. Query reasoning uses Neo4j only when available.",
    }


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    db.log_feedback(req.query, req.answer_id, req.rating, req.comment)
    return {"status": "recorded"}


@app.post("/api/escalate")
def escalate(req: EscalateRequest):
    escalation_id = db.log_escalation(
        req.query, req.product_category, req.jurisdiction,
        req.relevant_ip_area, req.retrieved_sources, req.contact_email,
    )
    return {"status": "escalated", "escalation_id": escalation_id}


@app.get("/api/eval")
def eval_summary():
    return db.get_eval_summary()


@app.post("/api/posture-pdf")
def posture_pdf_endpoint(req: PostureRequest):
    """Render the given /api/analyze result (exactly as the frontend already
    received it) into a downloadable 'IP Posture Summary' PDF. Nothing is
    recomputed here — the PDF can never show a different answer than what
    was already on screen."""
    try:
        pdf_bytes = posture_pdf.build_posture_pdf(req.result, req.query)
    except Exception as e:
        logger.exception("Posture PDF generation failed")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=sutradhara-ip-posture-summary.pdf"},
    )


@app.get("/api/eval/benchmark")
def eval_benchmark():
    """Freshly computed accuracy/citation/abstention metrics against the
    labeled data/eval_dataset.json — see eval_runner.py docstring for what
    each number means and does not mean."""
    return eval_runner.run_benchmark(app)


# --------------------------------------------------------------------------
# Paid-subscription connector (consent-logged, user-linked) — see connectors.py
# --------------------------------------------------------------------------
@app.post("/api/connectors/link", response_model=ConnectorInfo)
def link_connector(req: ConnectorLinkRequest):
    try:
        info = connectors.link_connector(req.provider, req.api_key, req.scope, req.contact_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except connectors.ConnectorConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return ConnectorInfo(**info)


@app.post("/api/connectors/revoke")
def revoke_connector(req: ConnectorRevokeRequest):
    ok = connectors.revoke_connector(req.connector_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"status": "revoked", "connector_id": req.connector_id}


@app.get("/api/connectors", response_model=List[ConnectorInfo])
def list_connectors():
    return [ConnectorInfo(**c) for c in connectors.list_connectors()]


@app.get("/api/connectors/{connector_id}/usage")
def connector_usage(connector_id: str):
    if connectors.get_connector(connector_id) is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"connector_id": connector_id, "usage": connectors.usage_log_for(connector_id)}


# --------------------------------------------------------------------------
# Multi-hop graph reasoning — see graph_reasoning.py
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Voice input and read-aloud (Sarvam Saaras/Bulbul) — see app/asr.py
# --------------------------------------------------------------------------
@app.post("/api/asr/transcribe", response_model=ASRResponse)
def asr_transcribe(req: ASRRequest):
    if not req.external_processing_consent:
        raise HTTPException(status_code=403, detail="Explicit consent is required before sending audio to speech providers.")
    """
    Transcribes recorded audio to text using Sarvam Saaras. The
    returned text is meant to be dropped straight into the same query box a
    typed question would go in; it does not itself call /api/analyze, so
    the person can review/edit the transcript before submitting it.
    """
    text, ok = asr.transcribe(
        req.audio_base64, req.source_language, req.audio_format, req.sampling_rate,
    )
    return ASRResponse(text=text, transcribed_ok=ok, source_language=req.source_language)


@app.post("/api/tts/synthesize", response_model=TTSResponse)
def tts_synthesize(req: TTSRequest):
    if not req.external_processing_consent:
        raise HTTPException(status_code=403, detail="Explicit consent is required before sending text to speech providers.")
    if req.language not in ("en", "hi", "te", "ta", "ml", "sa"):
        raise HTTPException(status_code=400, detail="language must be one of en, hi, te, ta, ml, sa.")
    audio = asr.synthesize(req.text, req.language, req.speaker)
    if audio is None:
        raise HTTPException(status_code=503, detail=f"Text-to-speech is unavailable for language '{req.language}'.")
    return TTSResponse(audio_base64=audio)


@app.post("/api/translate")
def translate_batch(req: TranslateBatchRequest):
    if not req.external_processing_consent:
        raise HTTPException(status_code=403, detail="Explicit consent is required before sending text to translation providers.")
    results = []
    for text in req.texts:
        if len(text) > 6000:
            results.append({"text": text, "translated": text, "success": False, "reason": "Text exceeds the 6000-character translation limit."})
            continue
        translated, ok = translate.translate_text(text, req.target_language)
        results.append({
            "text": text,
            "translated": translated,
            "success": ok,
            "reason": None if ok else f"Translation providers could not translate this text to '{req.target_language}'.",
        })
    return {"target_language": req.target_language, "results": results}


@app.post("/api/graph/reason")
def graph_reason(req: GraphReasonRequest):
    try:
        return graph_reasoning.reason(req.category, req.jurisdiction, req.export_intent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --------------------------------------------------------------------------
# Corpus freshness / "always-current law" — see app/corpus_freshness.py
# --------------------------------------------------------------------------
@app.get("/api/corpus/freshness")
def corpus_freshness_endpoint(live_check: bool = False):
    """Per-document staleness report. Pass ?live_check=true to also probe
    whether each source's real URL still resolves (requires outbound
    internet on the server; see corpus_freshness.py for exactly what that
    does and does not verify)."""
    report = corpus_freshness.freshness_report()
    if live_check:
        report["live_reachability"] = corpus_freshness.check_live_reachability()
    return report


# --------------------------------------------------------------------------
# Live official registry access — see app/registry_lookup.py
# --------------------------------------------------------------------------
@app.post("/api/registry/lookup")
def registry_lookup_endpoint(req: RegistryLookupRequest):
    try:
        return registry_lookup.lookup(req.jurisdiction, req.keyword, req.registry, req.limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/registry/gi/refresh")
def gi_registry_refresh():
    """Fetch and parse IP India's officially published GI list for real —
    see app/gi_registry.py for exactly why this one India registry can
    honestly do this while patents/trademarks (CAPTCHA-gated) cannot.
    Requires outbound internet on the server; on any failure the existing
    cache (if any) is left untouched."""
    return gi_registry.build_index(force_refresh=True)


@app.get("/api/registry/gi/status")
def gi_registry_status():
    return gi_registry.status()


# --------------------------------------------------------------------------
# DPDP-aligned data governance rights — see app/privacy.py
# --------------------------------------------------------------------------
@app.get("/api/privacy/policy")
def privacy_policy():
    return privacy.compliance_status()


@app.get("/api/privacy/ai-standards-alignment")
def privacy_ai_standards_alignment():
    """Real, honest self-assessment against the NIST AI Risk Management
    Framework 1.0 — see privacy.ai_standards_alignment()'s docstring for
    why this is a correspondence review, not a certification claim."""
    return privacy.ai_standards_alignment()


@app.get("/api/privacy/bias-audit")
def privacy_bias_audit():
    """Runs the real gendered-language template scan and persona-invariance
    check live — see app/bias_audit.py's docstring for exactly what this
    does and does not cover, including a disclosed, real finding."""
    return bias_audit.run_full_audit()


@app.post("/api/privacy/access")
def privacy_access(req: PrivacyLookupRequest, authorization: Optional[str] = Header(default=None)):
    """Return only the authenticated account's records.

    Historical audit/feedback rows keyed only by query text cannot safely be
    attributed to an account, so the API does not expose query-based lookup.
    """
    user = _current_user(authorization)
    if req.query_text:
        raise HTTPException(
            status_code=400,
            detail="Query-based lookup is unavailable because historical logs are not associated with account owners.",
        )
    if req.contact_email and req.contact_email.strip().lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="You can only access records tied to your account.")
    try:
        logs = privacy.access_report(contact_email=user["email"])
        account = privacy.export_account(user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"account_data": account, "matching_logs": logs}


@app.post("/api/privacy/erase")
def privacy_erase(req: PrivacyLookupRequest, authorization: Optional[str] = Header(default=None)):
    """Erase escalation logs tied to the authenticated account email.

    Use DELETE /api/privacy/account to erase that account's chats and profile.
    """
    user = _current_user(authorization)
    if req.query_text:
        raise HTTPException(
            status_code=400,
            detail="Query-based erasure is unavailable because historical logs are not associated with account owners.",
        )
    if req.contact_email and req.contact_email.strip().lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="You can only erase records tied to your account.")
    try:
        deleted = privacy.erase(contact_email=user["email"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "erased", "deleted": deleted}


@app.post("/api/privacy/purge-expired")
def privacy_purge_expired(purge_token: Optional[str] = Header(default=None, alias="X-Privacy-Purge-Token")):
    """Trusted scheduler endpoint; retention policy is server-controlled."""
    configured_token = os.getenv("SUTRADHARA_PRIVACY_PURGE_TOKEN")
    if not configured_token:
        raise HTTPException(status_code=503, detail="Privacy purge is not configured.")
    if not purge_token or not hmac.compare_digest(purge_token, configured_token):
        raise HTTPException(status_code=401, detail="Not authorized to run privacy purge.")
    deleted = privacy.purge_expired()
    return {"status": "purged", "deleted": deleted}


# --- Consent Manager reference implementation (see app/privacy.py) --------
def _owned_consent(user: dict, consent_id: str) -> dict:
    consent = privacy.get_consent(consent_id)
    if consent is None or consent["data_principal_ref"].strip().lower() != user["email"].lower():
        raise HTTPException(status_code=404, detail="Consent artifact not found.")
    return consent


@app.post("/api/privacy/consent/request")
def consent_request(req: ConsentRequestRequest, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    if req.data_principal_ref.strip().lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="Consent artifacts can only be created for your own account.")
    try:
        return privacy.request_consent(user["email"], req.purpose, req.data_categories, req.expires_in_days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/privacy/consent/grant")
def consent_grant(req: ConsentIdRequest, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    _owned_consent(user, req.consent_id)
    try:
        return privacy.grant_consent(req.consent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/privacy/consent/revoke")
def consent_revoke(req: ConsentIdRequest, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    _owned_consent(user, req.consent_id)
    try:
        return privacy.revoke_consent(req.consent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/privacy/consent/{consent_id}")
def consent_get(consent_id: str, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    return _owned_consent(user, consent_id)


@app.post("/api/privacy/consent/{consent_id}/access")
def consent_access(consent_id: str, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    try:
        _owned_consent(user, consent_id)
        access_log = features.log_consent_access(consent_id, f"user:{user['id']}")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"consent_id": consent_id, "access_log": access_log}


@app.get("/api/privacy/consents")
def consent_list(data_principal_ref: Optional[str] = None,
                 authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    if data_principal_ref and data_principal_ref.strip().lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="You can only view your own consent artifacts.")
    return privacy.list_consents(user["email"])


# --- DPIA / breach register / ROPA (see app/privacy.py) --------------------
@app.post("/api/privacy/dpia")
def dpia_create(req: DPIARequest):
    try:
        return privacy.record_dpia(req.processing_activity, req.risk_level, req.reviewer, req.mitigations)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/privacy/dpia")
def dpia_list():
    return privacy.list_dpias()


@app.post("/api/privacy/breach")
def breach_create(req: BreachReportRequest):
    try:
        return privacy.report_breach(req.description, req.affected_categories, req.severity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/privacy/breach")
def breach_list():
    return privacy.list_breaches()


@app.post("/api/privacy/breach/notify-board")
def breach_notify_board(req: BreachIdRequest):
    try:
        return privacy.notify_board(req.breach_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/privacy/breach/notify-principals")
def breach_notify_principals(req: BreachIdRequest):
    try:
        return privacy.notify_principals(req.breach_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/privacy/ropa")
def ropa_create(req: ProcessingActivityRequest):
    try:
        return privacy.log_processing_activity(req.purpose, req.data_categories, req.legal_basis, req.retention_period_days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/privacy/ropa")
def ropa_list():
    return privacy.list_processing_activities()


# --- Cross-border transfer check (see app/privacy.py) ----------------------
@app.post("/api/privacy/cross-border/check")
def cross_border_check(req: CrossBorderCheckRequest):
    try:
        return privacy.check_transfer(req.destination_country, req.purpose, req.data_categories)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/privacy/cross-border/log")
def cross_border_log():
    return privacy.list_transfer_log()


# --------------------------------------------------------------------------
# Corpus auto-refresh / drift detection — see app/corpus_freshness.py
# --------------------------------------------------------------------------
@app.post("/api/corpus/refresh/propose")
def corpus_refresh_propose(req: CorpusRefreshRequest):
    """Fetch each targeted document's live source and detect drift since
    the last check. Requires outbound internet on the server; each result
    is fetched fresh, nothing here is fabricated. See corpus_freshness.py
    for exactly what 'pending_review' does and does not mean."""
    return {"results": corpus_freshness.propose_refresh(req.doc_ids)}


@app.get("/api/corpus/refresh/state")
def corpus_refresh_state(doc_ids: Optional[str] = None):
    ids = doc_ids.split(",") if doc_ids else None
    return {"documents": corpus_freshness.refresh_state(ids)}


@app.post("/api/corpus/refresh/approve")
def corpus_refresh_approve(req: CorpusRefreshApproveRequest):
    try:
        return corpus_freshness.approve_refresh(req.doc_id, req.reviewer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================================================
# Auth — Sign Up / Sign In   (see app/auth.py for the security model)
# ==========================================================================
def _client_key(request: Request, email: str = "") -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{ip}|{email.lower().strip()}"


def _current_user(authorization: Optional[str]) -> dict:
    user = auth.resolve_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated. Please sign in.")
    return user


def _own(user: dict, claimed_user_id: Optional[int]) -> int:
    """The acting user is always the token's user; a client-supplied id is
    only cross-checked (never trusted) and a mismatch is refused."""
    if not auth.check_claimed_user(user, claimed_user_id):
        raise HTTPException(status_code=403, detail="You can only access your own data.")
    return user["id"]


@app.post("/api/auth/signup", response_model=AuthResponse)
def auth_signup(req: SignUpRequest, request: Request):
    """Create a new account and return a session token."""
    if not auth.login_limiter.allow("signup|" + _client_key(request)):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    try:
        user = db.create_user(req.email, req.name, req.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return AuthResponse(user=UserInfo(**user), token=db.create_auth_session(user["id"]))


@app.post("/api/auth/signin", response_model=AuthResponse)
def auth_signin(req: SignInRequest, request: Request):
    """Sign in with email + password, returning a session token."""
    key = "signin|" + _client_key(request, req.email)
    if not auth.login_limiter.allow(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")
    user = db.authenticate_user(req.email, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    auth.login_limiter.reset(key)
    return AuthResponse(user=UserInfo(**user), token=db.create_auth_session(user["id"]))


@app.post("/api/auth/signout")
def auth_signout(authorization: Optional[str] = Header(default=None)):
    token = auth.parse_bearer(authorization)
    if token:
        db.delete_auth_session(token)
    return {"status": "signed_out"}


# ==========================================================================
# Chat history — every route requires a valid Bearer token and only ever
# touches the token owner's rows.
# ==========================================================================
@app.post("/api/chat/sessions")
def create_session(req: ChatSessionCreate, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    return db.create_chat_session(_own(user, req.user_id), req.title or "New conversation")


@app.get("/api/chat/sessions/{user_id}")
def list_sessions(user_id: int, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    return db.get_chat_sessions(_own(user, user_id))


@app.patch("/api/chat/sessions/{session_id}")
def rename_session(session_id: int, req: ChatSessionRename, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    if not db.rename_chat_session(session_id, _own(user, req.user_id), req.title):
        raise HTTPException(status_code=404, detail="Session not found or access denied.")
    return {"status": "renamed"}


@app.delete("/api/chat/sessions/{session_id}")
def delete_session(session_id: int, user_id: Optional[int] = None, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    if not db.delete_chat_session(session_id, _own(user, user_id)):
        raise HTTPException(status_code=404, detail="Session not found or access denied.")
    return {"status": "deleted"}


@app.get("/api/chat/sessions/{session_id}/messages")
def get_messages(session_id: int, user_id: Optional[int] = None, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    messages = db.get_chat_messages(session_id, _own(user, user_id))
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found or access denied.")
    return messages


@app.post("/api/chat/messages")
def add_message(req: ChatMessageAdd, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    uid = _own(user, req.user_id)
    if req.role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'assistant'.")
    if not db.session_belongs_to(req.session_id, uid):
        raise HTTPException(status_code=404, detail="Session not found or access denied.")
    return db.add_chat_message(req.session_id, req.role, req.content)


@app.post("/api/analyze/session", response_model=AnalyzeResponse)
def analyze_with_session(req: SessionAnalyzeRequest, authorization: Optional[str] = Header(default=None)):
    """Same pipeline as /api/analyze; if a session_id is given, the caller
    must be authenticated AND own that session, and the Q-and-A turn is
    persisted to it."""
    user = None
    if req.session_id is not None:
        user = _current_user(authorization)
        uid = _own(user, req.user_id)
        if not db.session_belongs_to(req.session_id, uid):
            raise HTTPException(status_code=404, detail="Session not found or access denied.")
    try:
        jur = jurisdiction.resolve_jurisdiction(req.jurisdiction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    initial_state = {
        "query": req.query,
        "jurisdiction": req.jurisdiction,
        "language": req.language,
        "confirmed_category": req.confirmed_category,
        "use_connector_id": req.use_connector_id,
        "query_depth": req.query_depth,
        "external_processing_consent": req.external_processing_consent,
        "jur": jur,
    }
    response_fields = dag.run_analyze_pipeline(initial_state)
    features.annotate_analysis(response_fields, req.query_depth)
    result = AnalyzeResponse(**response_fields)

    if user is not None:
        import json as _json
        db.add_chat_message(req.session_id, "user", req.query)
        db.add_chat_message(req.session_id, "assistant", _json.dumps(result.model_dump()))
        for s_ in db.get_chat_sessions(user["id"]):
            if s_["id"] == req.session_id and s_["title"] == "New conversation":
                db.rename_chat_session(req.session_id, user["id"], req.query[:60])
                break
    return result


# ==========================================================================
# DPDP rights over the logged-in account's own data (see privacy.py)
# ==========================================================================
@app.get("/api/privacy/account/export")
def account_export(authorization: Optional[str] = Header(default=None)):
    """Right to access, for the account: profile, every chat session and
    message, and escalations filed under the account email."""
    return privacy.export_account(_current_user(authorization)["id"])


@app.delete("/api/privacy/account")
def account_delete(authorization: Optional[str] = Header(default=None)):
    """Right to erasure, for the account: hard-deletes the user, their chat
    history, their login tokens, and escalations filed under their email."""
    user = _current_user(authorization)
    return {"status": "deleted", "deleted": privacy.delete_account(user["id"])}


# ==========================================================================
# Citizen Claims Submission Workflow — /api/v1/claims
# ==========================================================================
@app.post("/api/v1/claims")
def submit_claim(req: ClaimSubmitRequest, request: Request, authorization: Optional[str] = Header(default=None)):
    """Submit a formulated IP claim for tracking (Pending → Verified → Anchored)."""
    user = _current_user(authorization)
    if not auth.login_limiter.allow("claims|" + _client_key(request)):
        raise HTTPException(status_code=429, detail="Too many claim submissions. Try again later.")
    user_id = user["id"]
    return claims_workflow.submit_claim(
        req.title, req.description, req.jurisdiction, req.category, user_id
    )


@app.get("/api/v1/claims")
def list_claims_endpoint(
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    authorization: Optional[str] = Header(default=None),
):
    """List claims. Authenticated citizens see their own; admins see all."""
    user = _current_user(authorization)
    role = admin_auth.get_user_role(user["id"])
    uid = None if role == "admin" else user["id"]
    return claims_workflow.list_claims(user_id=uid, status=status, limit=limit)


@app.get("/api/v1/claims/{claim_id}")
def get_claim_endpoint(claim_id: str, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    claim = claims_workflow.get_claim(claim_id)
    if claim is None or (admin_auth.get_user_role(user["id"]) != "admin" and claim["user_id"] != user["id"]):
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@app.post("/api/v1/claims/{claim_id}/verify")
def verify_claim_endpoint(claim_id: str, authorization: Optional[str] = Header(default=None)):
    """Admin action: advance a Pending claim to Verified."""
    user = _current_user(authorization)
    try:
        admin_auth.require_admin(user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    try:
        return claims_workflow.verify_claim(claim_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/claims/{claim_id}/anchor")
def anchor_claim_endpoint(claim_id: str, authorization: Optional[str] = Header(default=None)):
    """Admin action: anchor a Verified claim (simulated blockchain hash)."""
    user = _current_user(authorization)
    try:
        admin_auth.require_admin(user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    try:
        return claims_workflow.anchor_claim(claim_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================================================
# Citizen Formulation Dossiers — /api/v1/dossiers
# ==========================================================================
@app.post("/api/v1/dossiers")
def create_dossier_endpoint(req: DossierCreateRequest, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    return dossiers.create(
        user["id"], req.name, req.ingredients, req.sourcing_type,
        req.indication, req.target_market,
    )


@app.get("/api/v1/dossiers")
def list_dossiers_endpoint(authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    return dossiers.list_for_user(user["id"])


@app.get("/api/v1/dossiers/{dossier_id}")
def get_dossier_endpoint(dossier_id: str, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    dossier = dossiers.get_for_user(dossier_id, user["id"])
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier not found.")
    return dossier


@app.patch("/api/v1/dossiers/{dossier_id}")
def update_dossier_endpoint(
    dossier_id: str,
    req: DossierUpdateRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = _current_user(authorization)
    dossier = dossiers.update_for_user(
        dossier_id, user["id"], req.model_dump(exclude_unset=True)
    )
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier not found.")
    return dossier


@app.delete("/api/v1/dossiers/{dossier_id}")
def delete_dossier_endpoint(dossier_id: str, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    if not dossiers.delete_for_user(dossier_id, user["id"]):
        raise HTTPException(status_code=404, detail="Dossier not found.")
    return {"status": "deleted"}


@app.post("/api/v1/dossiers/{dossier_id}/classify")
def classify_dossier_endpoint(
    dossier_id: str,
    req: DossierClassifyRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = _current_user(authorization)
    dossier = dossiers.classify_for_user(dossier_id, user["id"], req.confirmed_category)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier not found.")
    return dossier


@app.post("/api/v1/dossiers/{dossier_id}/map")
def map_dossier_endpoint(dossier_id: str, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    try:
        dossier = dossiers.map_for_user(dossier_id, user["id"])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier not found.")
    return dossier


@app.post("/api/v1/dossiers/{dossier_id}/review")
def review_dossier_endpoint(
    dossier_id: str,
    req: DossierReviewRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = _current_user(authorization)
    try:
        dossier = dossiers.review_for_user(dossier_id, user["id"], req.note)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier not found.")
    return dossier


# ==========================================================================
# Deep Patent Collision Radar — /api/v1/radar  (admin side)
# ==========================================================================
@app.post("/api/v1/radar")
def radar_endpoint(req: RadarRequest, request: Request, authorization: Optional[str] = Header(default=None)):
    """Cross-reference a new patent filing against TKDL to detect bio-piracy.
    Admin/ministry endpoint — requires admin role."""
    user = _current_user(authorization)
    try:
        admin_auth.require_admin(user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not auth.login_limiter.allow("radar|" + _client_key(request)):
        raise HTTPException(status_code=429, detail="Too many radar requests. Please try again later.")
    return radar.run_radar(
        req.patent_title, req.patent_abstract,
        req.patent_claims, req.filing_office, req.filing_date,
    )


# ==========================================================================
# Citizen Prahari Patent Watchlist — /api/v1/prahari
# ==========================================================================
@app.post("/api/v1/prahari")
def create_prahari_alert_endpoint(
    req: PrahariAlertCreateRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = _current_user(authorization)
    try:
        return prahari.create(
            user["id"], req.filing_number, req.title, req.abstract,
            req.publication_date, req.stream, req.source_url,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/api/v1/prahari")
def list_prahari_alerts_endpoint(authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    return prahari.list_for_user(user["id"])


@app.get("/api/v1/prahari/{alert_id}")
def get_prahari_alert_endpoint(alert_id: str, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    alert = prahari.get_for_user(alert_id, user["id"])
    if alert is None:
        raise HTTPException(status_code=404, detail="Watchlist filing not found.")
    return alert


@app.delete("/api/v1/prahari/{alert_id}")
def delete_prahari_alert_endpoint(alert_id: str, authorization: Optional[str] = Header(default=None)):
    user = _current_user(authorization)
    if not prahari.delete_for_user(alert_id, user["id"]):
        raise HTTPException(status_code=404, detail="Watchlist filing not found.")
    return {"status": "deleted"}


# ==========================================================================
# Manuscript OCR / Digitisation — /api/v1/ocr
# ==========================================================================
@app.post("/api/v1/ocr")
def ocr_endpoint(req: OCRRequest, request: Request, authorization: Optional[str] = Header(default=None)):
    """Upload a base64-encoded manuscript image; a vision-LLM extracts
    herbs, symptoms, and formulation steps into structured JSON."""
    _current_user(authorization)
    if not req.external_processing_consent:
        raise HTTPException(status_code=403, detail="Explicit consent is required before sending a manuscript image to the external vision provider.")
    if not auth.login_limiter.allow("ocr|" + _client_key(request)):
        raise HTTPException(status_code=429, detail="Too many OCR requests. Try again later.")
    try:
        decoded = base64.b64decode(req.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="image_base64 must contain valid base64 image data.")
    if not decoded or len(decoded) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be no larger than 5 MiB.")
    transfer = privacy.check_transfer("United States", "Groq manuscript OCR", ["manuscript image"])
    if transfer["decision"] != "allowed":
        raise HTTPException(status_code=403, detail="Cross-border processing is blocked by the configured transfer policy.")
    try:
        return ocr_digitize.digitise_manuscript(
            req.image_base64, req.mime_type, req.filename
        )
    except ocr_digitize.OCRProviderError as e:
        logger.warning("OCR provider unavailable: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("OCR digitisation failed")
        raise HTTPException(status_code=500, detail="OCR failed.")


# ==========================================================================
# Admin / Ministry RBAC — /api/v1/auth/admin-signup
# ==========================================================================
@app.post("/api/v1/auth/admin-signup", response_model=AuthResponse)
def admin_signup(req: AdminSignUpRequest, request: Request):
    """Create a ministry/admin account using the shared invite code."""
    if not auth.login_limiter.allow("admin-signup|" + _client_key(request)):
        raise HTTPException(status_code=429, detail="Too many attempts.")
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="Valid email required.")
    try:
        user = admin_auth.create_admin_user(req.email, req.name, req.password, req.invite_code)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Admin self-service signup is disabled.")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return AuthResponse(user=UserInfo(**{k: user[k] for k in ["id", "email", "name"]}),
                        token=db.create_auth_session(user["id"]))


@app.get("/api/v1/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None)):
    """Return current user info including their role."""
    user = _current_user(authorization)
    role = admin_auth.get_user_role(user["id"])
    return {**user, "role": role}


# ==========================================================================
# Public Patent / Claims Registry — /api/v1/patents
# ==========================================================================
@app.get("/api/v1/patents")
def browse_patents_registry(
    system: Optional[str] = Query(default=None, max_length=40),
    keyword: Optional[str] = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Browse illustrative public prior-art references; private claims are excluded."""
    return patents_registry.browse_registry(system, keyword, limit, offset)


# ==========================================================================
# Legal pages — /api/v1/legal/*
# ==========================================================================
@app.get("/api/v1/legal/rti")
def legal_rti():
    """RTI Act / Right to Information compliance information."""
    return {
        "title": "Right to Information Act 2005 — Sutradhara Compliance",
        "last_updated": "2026-01-01",
        "public_authority": "SUTRADHARA is a prototype tool developed for SIH 2026.",
        "pio_contact": "pio@sutradhara.example.in",
        "disclosure": (
            "Sutradhara does not hold any classified or restricted information. "
            "All corpus documents are sourced from publicly available statutory "
            "texts, official gazette notifications, and treaty documents. "
            "Citizens may file RTI requests regarding the system's operation via "
            "the PIO contact above."
        ),
        "proactive_disclosures": [
            "Algorithm design: rule-based retrieval with optional LLM paraphrasing (see ARCHITECTURE.md)",
            "Data sources: listed at /api/corpus/freshness",
            "Bias audit: available at /api/privacy/bias-audit",
            "AI standards alignment: available at /api/privacy/ai-standards-alignment",
        ],
        "disclaimer": "This is a prototype system. RTI obligations apply to public authorities; confirm applicability with the deploying ministry.",
    }


@app.get("/api/v1/legal/terms")
def legal_terms():
    """Terms of Service for Sutradhara."""
    return {
        "title": "Terms of Service — Sutradhara",
        "version": "1.0",
        "effective_date": "2026-10-01",
        "sections": [
            {
                "heading": "1. Nature of the Service",
                "text": (
                    "Sutradhara provides information about Indian and international intellectual "
                    "property law as it relates to traditional knowledge, Ayurvedic formulations, "
                    "and related products. All outputs are informational only and do not constitute "
                    "legal advice. No attorney-client relationship is created."
                ),
            },
            {
                "heading": "2. Accuracy and Limitations",
                "text": (
                    "Information is retrieved from a curated corpus of statutory texts and official "
                    "sources. The system may not reflect the most recent amendments. Always verify "
                    "with the competent authority or a qualified legal professional before acting."
                ),
            },
            {
                "heading": "3. Data Privacy",
                "text": (
                    "Query text is processed to generate answers and may be stored for audit "
                    "and quality purposes. See /api/privacy/policy for the full DPDP-aligned "
                    "privacy notice. You may request access or erasure at any time."
                ),
            },
            {
                "heading": "4. Citizen Claims",
                "text": (
                    "Claims submitted via /api/v1/claims are recorded in the system for "
                    "tracking. They do not create any legal right or filing. The blockchain "
                    "anchor is a simulated hash commitment, not an on-chain transaction."
                ),
            },
            {
                "heading": "5. Governing Law",
                "text": "These terms are governed by the laws of India.",
            },
        ],
    }


@app.get("/api/v1/legal/copyright")
def legal_copyright():
    """Copyright and IP notice for Sutradhara."""
    return {
        "title": "Copyright & IP Notice — Sutradhara",
        "copyright": "© 2026 Sutradhara Team (SIH26045). All rights reserved.",
        "corpus_sources": (
            "The legal corpus is composed of publicly available statutory texts, "
            "gazette notifications, and treaty documents. These are in the public "
            "domain or reproduced under fair dealing for informational purposes."
        ),
        "software_license": "Proprietary — SIH 2026 hackathon submission.",
        "tkdl_attribution": (
            "Traditional Knowledge Digital Library (TKDL) data is the property of "
            "the Government of India / CSIR. Sutradhara references TKDL for "
            "educational and prior-art identification purposes only."
        ),
        "ai_outputs": (
            "AI-generated analysis is informational and is not legal advice. "
            "Users retain rights to their own submitted descriptions; Sutradhara "
            "claims no IP over user inputs."
        ),
        "contact": "legal@sutradhara.example.in",
    }
