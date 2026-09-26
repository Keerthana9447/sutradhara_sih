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
