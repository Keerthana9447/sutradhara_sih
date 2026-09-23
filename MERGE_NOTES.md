# SUTRADHARA — Merge Notes (sutradhara_final.zip + sutradhara-main-improved.zip)

This build merges two parallel versions of the project. This document says
exactly what came from where and why, so nothing here is a mystery later.

## Comparison verdict

**sutradhara-main-improved.zip was used as the base.** On direct inspection
(not guesswork — I ran both test suites, read the actual code, and tested
the API live):

| Feature | Kept from | Why |
|---|---|---|
| Connectors (paid-subscription linking) | **improved** | `sutradhara_final`'s version pre-seeds three fake "already-consented" connectors with fabricated sample data and never actually asks for the user's own API key — the opposite of what the problem statement asks for. `improved`'s version hashes a real user-provided key, starts empty, and is fully audited. |
| TKDL similarity scoring | **improved** | `sutradhara_final`'s "TKDL Resemblance Score" is an arbitrary point formula (keyword count × 10 + source count × 20 + category weight) wearing alarming labels like `CRITICAL_PRIOR_ART` — a real overclaiming risk. `improved`'s version is real TF-IDF cosine similarity against 10 named reference formulations, explicitly scoped as illustrative-only. |
| Eval benchmark's jurisdiction check | **improved** | `sutradhara_final` checks 3 hardcoded phrases as a substring match — would miss most real jurisdiction leaks. `improved` checks the actual structured `jurisdiction` field on every source. `improved` also has a citation-integrity invariant that `sutradhara_final` lacks entirely. |
| Test suite health | **improved** | `sutradhara_final` ships with 2 failing tests out of the box (a `db.init_db()` ordering bug in tests that call `main.analyze()` directly, bypassing FastAPI's startup lifecycle). |
| **Dynamic per-query knowledge graph** | **sutradhara_final** ✅ | Its `graph.py` builds a live, query-specific graph automatically on every `/api/analyze` call — genuinely more compelling than `improved`'s separate, manually-triggered static tool. Ported in as `app/graph.py`, wired into `main.py` (`dynamic_graph` field on every analyze response). One bug fixed while porting: its empty-evidence fallback was fabricating a plausible-looking source ID (e.g. `IN-PAT-3P`) for queries that retrieved nothing at all — replaced with an honest "no sources retrieved" node, because a *dynamic, per-query* graph that shows a source not actually retrieved for that query defeats its own purpose. |
| Eval latency & feature-coverage tracking | **sutradhara_final** ✅ | Its `eval_benchmark.py` measured response latency and TKDL/pathway coverage — good ideas, folded additively into `improved`'s `eval_runner.py` (`avg_latency_ms`, `tkdl_similarity_coverage`, `regulatory_pathway_coverage`) without touching the hard invariant checks. |

`improved`'s existing `graph_reasoning.py` (the manual "what do I need to
export this abroad" what-if tool) was **kept alongside** the new dynamic
graph, not replaced — they answer different questions (explain what was
just retrieved, vs. explore a hypothetical) and both are real, tested
capabilities.

## New: Bhashini ASR (voice input) — neither project had this

You said you have two separate Bhashini API keys — one for NMT
(translation), one for ASR (speech recognition). Neither uploaded project
had any voice input at all, so this is new work, built to match that exact
two-key setup:

- `app/translate.py` (NMT/translation) now reads `BHASHINI_NMT_USER_ID` /
  `BHASHINI_NMT_API_KEY` first, falling back to the old unprefixed
  `BHASHINI_USER_ID` / `BHASHINI_API_KEY` names for backward compatibility.
- `app/asr.py` (new file) reads a **completely separate** credential pair,
  `BHASHINI_ASR_USER_ID` / `BHASHINI_ASR_API_KEY`, and implements the same
  two-step ULCA pipeline call pattern as the NMT side, but for `taskType:
  "asr"`. It never raises — any failure (missing keys, network error,
  unexpected response) returns a clean "couldn't transcribe, type instead"
  message, the same fail-safe philosophy as every other external call in
  this codebase.
- `POST /api/asr/transcribe` — new endpoint. Takes base64 audio + source
  language, returns transcribed text. Does not itself call `/api/analyze` —
  the frontend drops the transcript into the query box so you can review or
  edit it before submitting, same as if you'd typed it.
- `GET /api/health` now also reports `bhashini_asr.configured` so the
  frontend can honestly grey out the microphone button when ASR isn't set
  up, instead of showing a mic that silently fails.
- **Frontend**: new `components/MicButton.jsx` using the browser's
  `MediaRecorder` API — click to record, click again to stop, uploads to
  the new endpoint, drops the transcript into the query textarea. Sits next
  to the jurisdiction indicator in the Analyze tab. Verified in-browser
  (via an actual headless-Chromium screenshot, not just code review) that
  it correctly shows disabled/grey when `BHASHINI_ASR_*` isn't set and
  active/green when it is.

### One thing to verify once you add your real ASR key

The browser's `MediaRecorder` records in whatever codec it supports
(commonly WebM/Opus); Bhashini's ASR service may expect a specific format
(e.g. WAV/PCM). This sandbox has no network route to the live Bhashini
service, so this has only been tested against a mocked HTTP layer — the
request/response wiring is verified correct, but the real service's exact
format tolerance is not. If transcription comes back empty or garbled once
your real key is in, the fix is almost certainly a server-side transcode
step inside `app/asr.py`'s `_transcribe_via_bhashini()`, not a frontend
change — flagging this now so it's a known first troubleshooting step, not
a surprise.

## How to add your two Bhashini API keys

1. Copy `backend/.env.example` to `backend/.env`.
2. Fill in `BHASHINI_NMT_USER_ID` / `BHASHINI_NMT_API_KEY` with your
   translation-authorized key pair.
3. Fill in `BHASHINI_ASR_USER_ID` / `BHASHINI_ASR_API_KEY` with your
   speech-recognition-authorized key pair.
4. Restart the backend. Check `GET /api/health` — both
   `bhashini.configured` and `bhashini_asr.configured` should read `true`.
   If either is `false`, the app still works correctly (falls back to
   Google Translate for NMT, greys out the mic for ASR) — it just isn't
   using your real keys yet.
5. If your registered Bhashini account uses a non-default pipeline id for
   either service, set `BHASHINI_NMT_PIPELINE_ID` and/or
   `BHASHINI_ASR_PIPELINE_ID` (check the Bhashini developer console) —
   otherwise leave them unset and the well-known public pipeline id is used.

## What was intentionally left out of this merge

- `sutradhara_final`'s connectors, TKDL scoring, and eval-jurisdiction-check
  implementations — for the specific quality/honesty reasons in the table
  above, not because they were untested or unfinished.
- `sutradhara_final`'s `node_modules/`, `dist/`, `.git/`, and a stray empty
  `frontend/backend-Recursive/` folder found in that zip — build artifacts
  and what looks like an accidental nested copy, not source.

## Test status after merge

66 passed, 3 skipped (all three skips are live-external-service checks —
Bhashini NMT, Bhashini ASR, and one network-dependent embeddings check —
that only run when real credentials/network are present; they are designed
to skip cleanly rather than fail in a sandboxed environment).
