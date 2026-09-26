import logging
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()  # loads backend/.env (GROQ_API_KEY, GROQ_MODEL, ...) if present
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

from typing import List, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from . import jurisdiction, retrieval, db, translate, posture_pdf
from . import graph_reasoning, eval_runner, connectors, graph, asr, dag
from . import corpus_freshness, privacy, registry_lookup, graph_store
from .schemas import (
    AnalyzeRequest, AnalyzeResponse, SourceRef,
    EscalateRequest, FeedbackRequest, PostureRequest,
    ConnectorLinkRequest, ConnectorInfo, ConnectorRevokeRequest,
    GraphReasonRequest, ASRRequest, ASRResponse, TTSRequest, TTSResponse,
    RegistryLookupRequest, PrivacyLookupRequest, PrivacyPurgeRequest,
    ConsentRequestRequest, ConsentIdRequest, DPIARequest, BreachReportRequest,
    BreachIdRequest, ProcessingActivityRequest, CrossBorderCheckRequest,
    CorpusRefreshRequest, CorpusRefreshApproveRequest,
)

app = FastAPI(title="SUTRADHARA API", version="0.1.0-prototype")

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


@app.on_event("startup")
def _startup():
    db.init_db()


@app.get("/api/health")
def health():
    freshness = corpus_freshness.freshness_report()
    return {
        "status": "ok",
        "corpus_documents": len(retrieval._CORPUS),
        "stale_corpus_documents": freshness["counts"]["stale"],
        "retrieval_backend": retrieval.BACKEND,
        "dag_backend": dag.DAG_BACKEND,
        "graph_backend": graph_store.GRAPH_BACKEND,
        "sarvam_translate": translate.sarvam_translate_status(),
        "bhashini": translate.bhashini_status(),
        "sarvam_voice": asr.asr_status(),
        "bhashini_voice": asr.bhashini_asr_status(),
        "bhashini_tts": asr.bhashini_tts_status(),
        "patentsview": registry_lookup.patentsview_status(),
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """
    Thin HTTP adapter. All pipeline logic (language normalization, query
    expansion, classification, retrieval, confidence scoring, evidence
    enrichment, answer generation, paraphrasing, translation) lives in the
    deterministic LangGraph DAG defined in app/dag.py — see that module's
    docstring for the graph shape and the langgraph/sequential fallback.
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
        "jur": jur,
    }
    response_fields = dag.run_analyze_pipeline(initial_state)
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
            {"from": "product", "to": "category", "label": "belongs_to"},
            {"from": "category", "to": "regime", "label": "relevant_to"},
            {"from": "category", "to": "tk", "label": "may_reference"},
            {"from": "regime", "to": "law", "label": "governed_by"},
            {"from": "law", "to": "provision", "label": "contains"},
            {"from": "provision", "to": "source", "label": "supported_by"},
        ],
        "note": "Static schema view for the prototype. See graph/schema.cypher for the live Neo4j model.",
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
    audio = asr.synthesize(req.text, req.language, req.speaker)
    if audio is None:
        raise HTTPException(status_code=503, detail="Sarvam text-to-speech is unavailable")
    return TTSResponse(audio_base64=audio)


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


# --------------------------------------------------------------------------
# DPDP-aligned data governance rights — see app/privacy.py
# --------------------------------------------------------------------------
@app.get("/api/privacy/policy")
def privacy_policy():
    return privacy.compliance_status()


@app.post("/api/privacy/access")
def privacy_access(req: PrivacyLookupRequest):
    try:
        return privacy.access_report(req.query_text, req.contact_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/privacy/erase")
def privacy_erase(req: PrivacyLookupRequest):
    try:
        deleted = privacy.erase(req.query_text, req.contact_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "erased", "deleted": deleted}


@app.post("/api/privacy/purge-expired")
def privacy_purge_expired(req: PrivacyPurgeRequest):
    deleted = privacy.purge_expired(req.retention_days)
    return {"status": "purged", "deleted": deleted}


# --- Consent Manager reference implementation (see app/privacy.py) --------
@app.post("/api/privacy/consent/request")
def consent_request(req: ConsentRequestRequest):
    try:
        return privacy.request_consent(req.data_principal_ref, req.purpose, req.data_categories, req.expires_in_days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/privacy/consent/grant")
def consent_grant(req: ConsentIdRequest):
    try:
        return privacy.grant_consent(req.consent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/privacy/consent/revoke")
def consent_revoke(req: ConsentIdRequest):
    try:
        return privacy.revoke_consent(req.consent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/privacy/consent/{consent_id}")
def consent_get(consent_id: str):
    consent = privacy.get_consent(consent_id)
    if consent is None:
        raise HTTPException(status_code=404, detail="Consent artifact not found")
    return consent


@app.get("/api/privacy/consents")
def consent_list(data_principal_ref: Optional[str] = None):
    return privacy.list_consents(data_principal_ref)


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
