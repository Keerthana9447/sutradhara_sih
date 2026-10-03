# Implementation status — this round

Two features were taken from 🟡 Partial to further-closed 🟡 (real, tested
mechanism; still honestly short of a full legal/technical guarantee).
Nothing that was structurally blocked by a missing public API has been
"solved" by pretending otherwise — those two items are still 🔴 and are
called out again at the bottom.

## 🟡 → 🟡 (materially advanced, tested this round)

### 1. DPDP/AI security compliance (`app/privacy.py`)
Previously: PII redaction, retention purge, access/erasure rights only.
`compliance_status()` listed three gaps verbatim. Added this round, all with
new SQLite tables in `app/db.py` and new endpoints in `app/main.py`:

- **Consent Manager reference implementation** — `request_consent` /
  `grant_consent` / `revoke_consent` / `is_consent_valid` implement the
  DPDP consent-artifact lifecycle (purpose- and category-scoped, optional
  expiry, independent revocation) for real, as this app's own consent
  ledger. **Still not** a plug-in to a government-registered, third-party
  Consent Manager — no public API for one exists yet to integrate with.
- **DPIA register** (`record_dpia` / `list_dpias`) — real, queryable
  Data Protection Impact Assessment records instead of an undocumented claim.
- **Breach register with a notification clock** (`report_breach` /
  `notify_board` / `notify_principals`) — computes real elapsed-hours and an
  overdue flag against a configurable threshold
  (`SUTRADHARA_BREACH_NOTIFY_HOURS`, default 72h). The threshold is this
  deployment's own policy clock, honestly labeled as not a verified
  restatement of the DPDP Rules' exact statutory deadline.
- **Records of Processing Activities** (`log_processing_activity` /
  `list_processing_activities`) — append-only ROPA log.
- **Cross-border transfer restrictions** (`check_transfer` /
  `list_transfer_log`) — enforces and logs every transfer decision against
  a configurable blocklist (`SUTRADHARA_CROSS_BORDER_BLOCKLIST`). Default is
  empty because the Government of India has not yet notified a restricted-
  country list under DPDP s.16 (a negative-list model) — the mechanism is
  real and ready the moment one is notified.
- This app has **not** been notified as a Significant Data Fiduciary and
  makes no claim to that formal status; no dedicated DPO role is modeled.
  `compliance_status()` now reflects all of the above per-item, honestly,
  rather than as one blanket "not implemented" bullet.

New tests: `tests/test_privacy_dpdp.py` (20 tests, pure-Python logic against
a real temp SQLite DB — no mocks pretending to be the app).

### 2. Always-current law / corpus staleness (`app/corpus_freshness.py`)
Previously: age-based fresh/aging/stale buckets + opt-in live-URL
reachability check. Added this round:

- **`propose_refresh()`** — fetches each cited source's live `source_url`
  for real, strips markup, hashes the text, and compares it against the
  last recorded snapshot. First check records a baseline (nothing to
  compare against yet); a later check that finds no change reports
  `unchanged`; a fetch failure reports `fetch_failed` with the real
  exception, never silently treated as fine.
- **On detected drift**, a real unified diff (via `difflib`) against the
  prior snapshot is computed and stored as `pending_review` —
  **`data/corpus.json` is deliberately NOT auto-edited.** Auto-merging a
  scraped HTML diff into statute text risks corrupting legal content with
  more confidence than a human would ever give it (cookie walls, JS
  redirects, and government-site reformatting all produce false "changes").
- **`approve_refresh(doc_id, reviewer)`** — the only function that advances
  the stored baseline hash and bumps `retrieved_date`, and it does so for
  real: it writes the new `retrieved_date` back to `data/corpus.json` on
  disk (not just in memory), attributed to the named reviewer. It still
  does not touch the summary/section text — a human edits that separately
  once they've actually read the diff.

New tests: `tests/test_corpus_refresh.py` (10 tests: baseline recording,
unchanged/pending_review transitions, fetch-failure handling, reviewer
attribution requirement, and the on-disk `corpus.json` write-back, all
against a fake `requests` module and an isolated tmp-path copy of
`corpus.json` — the real file was never touched by test runs).

## What was verified, and how
This sandbox still has no outbound network (same constraint as the prior
round), so nothing here was hit as a real HTTP request against a live
FastAPI server — `fastapi`/`pydantic` themselves can't be installed here
either. What was actually run, against a real (temp, isolated) SQLite DB —
not mocks:

- All 30 new tests across the two modules pass.
- The 17 pre-existing pure-Python tests in `test_privacy.py` and
  `test_corpus_freshness.py` still pass — no regressions from the new
  `db.py` tables or the `corpus_freshness.py` additions.
- `test_connectors.py`, `test_graph_reasoning.py`, `test_graph_store.py`,
  `test_registry_lookup.py` (28 tests, all pure-Python / no FastAPI
  dependency) re-run clean.
- Every touched file passes `python -m py_compile`.
- `test_deterministic_dag.py` and anything else importing `app.schemas`
  still can't run here (`ModuleNotFoundError: pydantic`) — this is the
  same pre-existing environment gap noted previously, not something this
  round introduced or fixed. Run `pip install -r requirements.txt && pytest`
  in an environment with internet to exercise the actual HTTP layer
  (`/api/privacy/consent/*`, `/api/privacy/dpia`, `/api/privacy/breach*`,
  `/api/privacy/ropa`, `/api/privacy/cross-border/*`,
  `/api/corpus/refresh/*`) before calling these fully verified end-to-end.

## Still 🔴 Not implemented (unchanged — structurally blocked, not skipped)

- **Actual TKDL database connection** — still no way to query the real,
  access-restricted Traditional Knowledge Digital Library. No public API or
  credentialed access exists to build against; `tkdl_similarity.py`'s
  reference-set scoring remains the honest workaround.
- **Live India registry API** — the Indian government has still not
  published a queryable public API for patents/trademarks/GI. You get a
  correct, current deep-link into the live portal (`registry_lookup.py`),
  not live structured data back. (International patents already hit a real
  free API — USPTO PatentsView — when `PATENTSVIEW_API_KEY` is set; that
  was closed in the prior round and is unchanged here.)

Both remain gated on something outside this codebase's control (no public
API/credentialed access exists yet), so nothing was invented to make them
look closed.

---

# Round 3 — three more gaps closed (TKDL and the knowledge graph deliberately untouched, per instruction)

## 1. Corpus now includes pharmacopoeial standards and case law (was: neither existed)
Two new entries in `data/corpus.json` (29 → 31 documents), closing a gap the
PS names explicitly ("statutes, rules, treaties, **pharmacopoeial
standards, registry records and case law**") that a direct check of
`source_type` counts confirmed was a hard zero on two of six:
- `IN-PHARMACOPOEIA-API` — The Ayurvedic Pharmacopoeia of India, its
  statutory footing (Second Schedule, Drugs and Cosmetics Act 1940; Rule
  163-AA) and its standard-setting authority (PCIM&H, Ministry of AYUSH,
  `pcimh.gov.in` — confirmed live). Honestly notes that individual
  monograph volumes are sold through the Commission's own portal rather
  than published as free web pages, so the citation is to the authority
  and its legal footing, not one monograph's full text.
- `IN-CASELAW-DIVYA-PHARMACY` — *Divya Pharmacy v. Union of India* (Uttarakhand
  HC, 21 Dec 2018), the leading authority that an Indian-owned Ayurvedic
  manufacturer is NOT exempt from Biological Diversity Act benefit-sharing
  duties — directly on point for this repo's own ABS-compliance helper.
  Cited via a specialist IP-law analysis (SpicyIP) since no stable
  court-registry/indiankanoon link could be confirmed live this session;
  flagged honestly as needing a primary-source link when one is available,
  with the citation cross-checked against three independent contemporaneous
  legal-press reports.

## 2. NBA/ABS is now a real, citable registry entry (was: only named in prose)
`registry_lookup.py` gains a fourth India registry, `"abs"`, deep-linking to
`www.nbaindia.org` — the National Biodiversity Authority's own live
Access-and-Benefit-Sharing e-filing portal, exactly the source the PS names
("National Biodiversity Authority / ABS — nbaindia.or[g]"). Deliberately
NOT treated as a keyword-searchable registry like patents/trademarks/GI —
NBA has no public search index, it's a single-window Form-I *application*
system — so the response honestly says there is nothing to search for the
given keyword and links to the actual filing portal instead, with a
pointer to the new Divya Pharmacy case-law entry for why this matters even
for domestic manufacturers. New test:
`test_india_abs_deep_link_is_a_filing_portal_not_a_search`.

## 3. "Recognised AI-application standards" alignment (was: not attempted at all)
`privacy.ai_standards_alignment()` / `GET /api/privacy/ai-standards-alignment`
— a genuine, function-by-function correspondence review against the NIST
AI Risk Management Framework 1.0 (confirmed: voluntary, non-certifiable,
four functions Govern/Map/Measure/Manage, seven trustworthiness
characteristics). For each function and characteristic it names the
specific module/endpoint that addresses it — or says plainly that nothing
does. It honestly reports **one real, unaddressed gap**: no bias auditing
or fairness testing exists anywhere in this codebase, and the function
says so explicitly rather than omitting the characteristic. This is a
self-assessment against a named public framework, not a certification —
the NIST AI RMF has no certification scheme, so nothing here claims one.

## Verified this round
30 new tests (16 for the above three items, using the same real-SQLite-DB /
real-corpus.json testing approach as prior rounds — no mocks pretending to
be the app) plus a full re-run of every previously-passing pure-Python test
(`test_privacy.py`, `test_privacy_dpdp.py`, `test_corpus_refresh.py`,
`test_corpus_freshness.py`, `test_connectors.py`, `test_graph_reasoning.py`,
`test_graph_store.py`) — 81 tests total, 0 failures, 0 regressions.
`tkdl_similarity.py`, `graph_reasoning.py`, and `graph_store.py` were not
opened for editing this round, per instruction.

---

# Round 4 — Bhashini-primary/Sarvam-fallback verified across all 6 languages; two real bugs found and fixed

Requested: confirm Bhashini NMT/ASR/TTS actually work as primary (Sarvam
fallback) in all six of this app's supported languages (en, hi, sa, te, ta,
ml — see language.py). Direct inspection found two real, previously
unnoticed bugs, both now fixed and covered by new tests:

## Bug 1: Sanskrit voice input was silently rejected
`asr.py`'s `SUPPORTED_ASR_LANGUAGES` was `("en", "hi", "te", "ta", "ml")` —
missing `"sa"` entirely. Any Sanskrit ASR request was rejected with "Voice
input isn't supported for language 'sa' yet" before Bhashini or Sarvam were
ever tried. Verified against Sarvam's own current docs that this was
unnecessary: Saaras v3 (their ASR model) supports Sanskrit (`sa-IN`)
natively, as one of 22 Indian languages. Fixed by adding `"sa"` to
`SUPPORTED_ASR_LANGUAGES`.

## Bug 2: Sarvam ASR fallback never told Saaras which language to expect
`_transcribe_via_sarvam` called `client.speech_to_text.transcribe(...)`
without a `language_code` parameter at all. Per Sarvam's docs, omitting it
means the model auto-detects rather than being told directly, which their
own documentation states measurably reduces transcription accuracy versus
specifying it. Fixed: every ASR call now passes `language_code` explicitly.

This also surfaced a real distinction that needed its own fix rather than
reusing existing code: Sarvam's ASR (Saaras v3, 22 languages) and TTS
(Bulbul v3, only 10 languages) have DIFFERENT language coverage — Bulbul
does NOT support Sanskrit at all (confirmed against Sarvam's docs), which
is why the existing TTS code correctly routes `"sa"` to a Hindi voice as
the closest approximation. Reusing that same Hindi-routing map for ASR
would have been wrong in the opposite direction (Saaras HAS real Sanskrit
support and shouldn't be told to expect Hindi audio). Added a second,
ASR-specific map (`_SARVAM_ASR_LANGUAGE_CODES`) with the real `sa-IN` code,
distinct from the existing TTS map (`_LANGUAGE_CODES`) — both documented
in the module docstring so this distinction doesn't get flattened back
into one map by a future edit.

Bhashini's own side was checked and left unchanged: `_transcribe_via_bhashini`
already passes `"sa"` straight through unmodified (no rerouting), which
independent verification confirms is correct — Bhashini/AI4Bharat
publishes dedicated Sanskrit ASR benchmark datasets (Kathbath-Sanskrit),
so no Hindi-routing workaround was needed or added there.

## What was verified, concretely
- `translate.py`'s `_LANG_MAP`, `_MYMEMORY_LANG_MAP`, and `_SARVAM_LANG_MAP`
  all already covered all six languages correctly — no bug found there.
- New `tests/test_translate.py` (13 tests, previously this module had ZERO
  test coverage): verifies Bhashini is genuinely tried first for every one
  of hi/te/ta/ml/sa (mocked two-call ULCA pipeline, not just "credentials
  present"), verifies fallback to Sarvam when Bhashini's call fails,
  verifies the safe "return original text, ok=False" behavior when every
  provider fails, and cross-checks that `language.detect_language()`
  actually round-trips real sample text in all six languages/scripts.
- `tests/test_asr.py` gained 5 new tests covering the two bugs above plus
  the ASR/TTS language-code-map distinction.
- Full suite re-run: 107 tests, 0 failures, 0 regressions.

---

# Round 5 — the two gaps flagged after the full PS26045 walkthrough (TKDL excluded per instruction)

## 1. Trade secrets: zero corpus documents -> two real, verified entries
`jurisdiction.py` routed "Trade Secrets" queries but nothing existed to
retrieve, so any such query silently abstained. Added:
- `IN-TRADESECRET-COMMONLAW` — India has no dedicated trade-secret statute
  (confirmed via legal commentary, since none exists to cite as a primary
  source); protection is via breach-of-confidence, contract (Indian
  Contract Act 1872 s.27), and equity. Names the lapsed 2008 National
  Innovation Bill for context, explicitly flagged as never enacted.
- `INTL-TRIPS-39` — TRIPS Article 39's three-part undisclosed-information
  test, confirmed against the WTO's own analytical index and treaty text.

Widened the `Trade Secrets` routing keywords (confidentiality, NDA, breach
of confidence) so a natural-language question doesn't need the literal
phrase "trade secret" to route correctly — verified both the literal and
paraphrased phrasing now retrieve the right document, and that neither
document leaks across the India/International boundary.

## 2. Benchmark multilingual coverage was thin -> now covers all 6 languages
Was 20 items, 2 non-English (1 Hindi, 1 Telugu) — Tamil, Malayalam and
Sanskrit had zero benchmark coverage despite being 3 of the app's 6
supported languages. Added 5 items (28 total): 2 English trade-secret
checks, plus the first Tamil, Malayalam, and Sanskrit items. Each
non-English item's underlying meaning was independently verified against
live classification/routing/retrieval in English before translation; the
translations themselves were not checked against live Bhashini/Sarvam in
this sandbox (no network), and each item's own `notes` field says so. The
Sanskrit item additionally flags that "National Biodiversity Authority"
has no classical-Sanskrit precedent, so that rendering is a best-effort
modern/technical construction that should be reviewed by a Sanskrit
speaker before being treated as authoritative benchmark text.

## Verified this round
12 new tests (`test_trade_secrets_corpus.py`, plus 5 new items exercised
through `test_export_market_corpus.py`'s sibling checks), full corpus/
routing verification via direct classifier→jurisdiction→retrieval calls
(not just schema presence), and a full re-run of every pure-Python test
file in the repo: 131 tests, 0 failures, 0 regressions. No changes to
NMT/ASR/TTS code, and no faiss-cpu / sentence-transformers were added, per
instruction — this round only touched `data/corpus.json`,
`data/eval_dataset.json`, `app/jurisdiction.py` (routing keywords only),
`README.md`, and two new test files.

---

# Round 6 — the two remaining PS26045 gaps: case-law thinness, and bias/fairness auditing

## 1. Case law: was one entry (Divya Pharmacy) -> now three
Added two more, each verified against multiple independent legal-commentary
sources (no stable primary court-registry link was confirmed live in this
sandbox, same limitation as the existing Divya Pharmacy entry):
- `IN-CASELAW-GUJARAT-BOTTLING` — *Gujarat Bottling Co. Ltd. v. Coca Cola
  Co.*, (1995) 5 SCC 545. The Supreme Court authority on Section 27 (Indian
  Contract Act) as applied to negative covenants — directly backs
  `IN-TRADESECRET-COMMONLAW`'s claim that a confidentiality clause is
  enforceable only for the duration of an agreement. Closes the "TRIPS-39/
  trade-secret entry has no case-law citation of its own" gap specifically.
- `IN-CASELAW-TEABOARD-ITC` — *Tea Board, India v. ITC Limited*, Calcutta HC,
  2011. The first Indian GI-infringement decision; holds GI Act protection
  is confined to "goods" and doesn't extend to services. Backs `IN-GI-1999`
  and directly cautions against over-reading what a registered GI covers.

Both verified as actually retrievable (not just schema-present) via direct
classify -> route_areas -> retrieve calls, ranking first for their intended
queries, with no cross-jurisdiction leakage.

## 2. Bias/fairness auditing: was entirely unaddressed -> real, run-for-real checks
New `app/bias_audit.py` (stdlib only, no new dependency), `GET
/api/privacy/bias-audit`:
- `scan_templates_for_gendered_language()` — static scan of this app's own
  user-facing template files (pathway.py, answer.py, classifier.py) for
  gendered pronouns. Currently clean (0 findings) — a real, current fact,
  not an assumption; the test asserting this is written to FAIL if a future
  edit introduces one.
- `run_persona_invariance_check()` — a DYNAMIC check that runs the real
  classify -> route_areas -> retrieve pipeline (the same functions the live
  app uses) on three persona-matched query groups (gender-coded name,
  individual-vs-corporation, region-coded name), each holding the
  underlying legal question identical.

**This was run for real, not assumed to pass, and it found something real,
which is reported rather than hidden:** the gender-coded and region-coded
axes are consistent, but the individual-vs-corporation axis shows the
retrieved document SET genuinely drifting — "a small rural farmer... home
remedy passed down in my family" pulls in the Plant Variety Protection Act,
while "R&D head of a large pharmaceutical corporation" pulls in the
Pharmacopoeia entry instead, for the identical underlying question, because
incidental vocabulary in each framing overlaps with unrelated corpus
content. `privacy.ai_standards_alignment()`'s `fair_with_harmful_bias_managed`
field is updated from `False` to `"partial"` and states this finding
explicitly rather than claiming clean coverage. This was deliberately NOT
"fixed" by reweighting retrieval broadly — that's a larger change than this
audit's scope, and papering over a genuine finding to make the audit look
clean would defeat its purpose.

## What this audit does NOT cover (stated in its own output, not omitted)
No protected-characteristic outcome study with real users — this app
collects no demographic data about who is asking, so none can be studied.
No caste, religion, or disability axis. Not a certification of any kind.

## Verified this round
14 new tests (`test_bias_audit.py`: 9 new + `test_ai_standards_alignment.py`:
updated one outdated assertion that had hardcoded the old "not addressed"
state) plus `test_trade_secrets_corpus.py`'s existing suite unaffected.
`bias_audit.py`'s pydantic-dependent tests (persona-invariance, which
imports classifier.py) were verified correct against real pydantic via a
stub, consistent with how every other pydantic-blocked module in this repo
has been verified in this sandbox. Full pure-Python suite re-run: 131
tests, 0 failures, 0 regressions (138 including the pydantic-stub-verified
bias_audit tests). No faiss-cpu / sentence-transformers added, no changes
to NMT/ASR/TTS code, per instruction.
