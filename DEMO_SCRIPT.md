# SUTRADHARA — 5-Minute Demo Script & Judge Q&A Cheat Sheet

**Why this document exists.** An external assessment scored the engineering
at 18/20 but the demo narrative at only 8/15, for a specific reason: "the
material to build a great live demo exists... but none of it has been
rehearsed as a timed pitch yet." A judge never sees the code — they see five
minutes of delivery. This script closes that gap. **Rehearse it out loud,
with a timer, at least three times before the real thing.** The first
run-through will feel too long; that's normal, cut from the *explaining*,
never from the *live actions* — a working demo is worth more than a
sentence of explanation.

---

## 0. Before you walk in (5-minute pre-flight checklist)

- [ ] Backend running, `GET /api/health` returns `"status": "ok"` — check
      this in a terminal tab you can glance at, not just trust it.
- [ ] Frontend built/served and reachable — refresh it once, empty the
      textarea, confirm you're on the Analyze tab.
- [ ] Run the exact 4 demo queries below **once, just now**, so nothing is
      a cold cache-miss on stage. Screenshot each result as a backup in case
      of a live network hiccup.
- [ ] Have `LEGAL_CONTENT_REVIEW.md` open in a second tab — if asked about
      accuracy, you open it and point, you don't just describe it.
- [ ] Know which one laptop/browser tab you're demoing from. Don't context-
      switch mid-demo.
- [ ] Decide who talks during which segment **now**, not on stage. One
      person narrates, one drives the keyboard, unless it's one person doing
      both — either is fine, indecision on stage is not.

---

## 1. The five-minute script

Times are cumulative. Speak to the *judge*, glance at the screen — don't
narrate to the screen with your back to the room.

### 0:00–0:25 — The hook (say this, don't read it verbatim, know it cold)

> "An Ayurvedic founder today has to separately check patent law, biodiversity
> law, drug regulation, and international treaties — and get the *jurisdiction*
> right, because Indian and international rules genuinely conflict. Get it
> wrong and you either lose protection you were entitled to, or you
> accidentally commit biopiracy. SUTRADHARA is that check, in one query, with
> every claim traced to a named source."

Do **not** open with "we built a RAG chatbot." Every team says that. Open
with the problem a founder actually has.

### 0:25–1:30 — Demo query 1: the core "why jurisdiction matters" moment

**Action:** Type: *"Can I patent a classical Ayurvedic formulation already
described in a traditional text?"* — jurisdiction set to **India**. Click
Analyze.

**While it loads (it's fast, but narrate through it):**
> "It first classifies the product — here, 'Classical / Generic Medicine' —
> then only searches within the areas that actually apply, and only within
> the jurisdiction I picked."

**When the result appears, point at three things in this order:**
1. The classification badge + why (one sentence).
2. The citation: *"Section 3(p), Patents Act — this bars patenting something
   that's already traditional knowledge. That's not a rule we wrote, that's
   the actual statute, and you can click through to verify it."*
3. The confidence score: *"71%, medium — composite of five real signals, not
   a made-up number. We show our work."*

**Now switch jurisdiction to International, same query, re-run.** This is
the single most important 20 seconds of the whole demo:

> "Same question, different jurisdiction — completely different sources.
> No Indian statute appears in this answer at all. That's not a filter we
> added on top — it's structurally impossible for an Indian-only source to
> leak into an International answer in this architecture. That distinction
> is the difference between a legal tool and a chatbot that sounds legal."

### 1:30–2:15 — Demo query 2: the safety story (abstention)

**Action:** Type something clearly out of scope, e.g. *"What is the boiling
point of tungsten?"* Click Analyze.

> "It doesn't guess. When there's no real evidence, it says so — this is the
> single most important thing a legal-information tool has to get right,
> because a confident wrong answer is worse than no answer."

Optionally show one more: an ambiguous query that triggers a *clarifying
question* instead of abstaining outright — shows the system asks rather than
assumes when it can.

### 2:15–3:15 — Demo query 3: the tangible deliverable (posture PDF)

**Action:** Re-run demo query 1 (India), scroll to the bottom, click
**"Download IP Posture Summary (PDF)."** Open the PDF.

> "This is a real, downloadable document — classification, cited evidence,
> the indicative regulatory pathway, confidence, all laid out for a founder
> to actually hand to a patent attorney. Most tools stop at a chat answer.
> We produce something you can act on outside the app."

Point at the **Indicative Regulatory Pathway** and the **TKDL resemblance
score** sections if they appear for the query you ran — these are quantified,
scoped, honestly-labeled additions most teams building this problem
statement will not have thought of.

### 3:15–4:00 — The rigor story (evaluation, not vibes)

**Action:** Switch to the Evaluation tab.

> "We didn't just test this by trying it a few times and hoping. This runs
> 20 labeled test queries through the real system on every load and checks
> two things that must always be zero: a source from the wrong jurisdiction
> ever appearing in an answer, and a citation that doesn't match what was
> actually retrieved. Both are zero, live, right now — not a number we
> picked once and put in a slide."

This is your strongest differentiator against 500 teams that will show 3–4
cherry-picked good answers and call it done. Say the word "live" out loud —
it's true, and it matters.

### 4:00–4:40 — Own the gaps before they're found (this is your best card)

> "Two things we want to be upfront about, because we think honesty here is
> part of the pitch: first, our multilingual layer tries Bhashini — India's
> own language infrastructure — before falling back to commercial
> translation, but we haven't been able to test the live Bhashini
> connection in our build environment, so tonight it's running on the
> fallback. Second, the underlying legal content hasn't had a professional
> IP review yet — we have a full written log of exactly what's verified and
> what still needs that review [gesture at LEGAL_CONTENT_REVIEW.md], and
> every single citation traces to a named, checkable source specifically so
> that gap can be closed in minutes, not months, once we get that review."Judges have seen dozens of teams oversell. A team that names its own limits,
precisely and without hand-wringing, reads as *more* credible, not less —
but only if you say it confidently, in this tone, not apologetically.

### 4:40–5:00 — Close

> "SUTRADHARA doesn't just answer IP questions about Ayurveda — it keeps
> India's and the world's rules structurally separate, shows its evidence
> for every claim, knows when to say 'I don't know,' and hands the founder
> something they can actually use next. That's what we built, and that's
> what SIH's own problem statement asked for, clause by clause."

Stop there. Don't keep talking into Q&A time.

---

## 2. Judge Q&A cheat sheet

Answer these **in your own words**, in the tone shown — direct, specific,
never defensive. A hedge-free "we don't know yet, here's our plan" beats a
vague deflection every time.

**"How is this different from just prompting ChatGPT with the right legal
documents?"**
> "Three structural things a prompt alone can't guarantee: jurisdiction
> isolation is enforced at the retrieval layer, not asked-for in a prompt —
> so it can't leak even if the model tries. Citations are template-assembled
> from what was actually retrieved, with a programmatic check that discards
> any AI-added text that isn't grounded — so citations can't be hallucinated
> by construction, not by instruction. And it can abstain — most prompt-only
> setups will always produce *an* answer."

**"Has a lawyer actually checked this content?"**
> Give the answer in §5 of `LEGAL_CONTENT_REVIEW.md` verbatim in spirit —
> honest, specific, points at the traceability as the mitigation.

**"What happens if Bhashini or the paid-subscription connector doesn't work
in production?"**
> "Each one fails safe to something real, never to a crash or a fabricated
> answer: Bhashini falls back to Google Translate, then MyMemory, then an
> offline glossary; the paid-connector lifecycle — link, consent, use,
> revoke — is fully functional even though we don't have a real commercial
> subscription to call in a demo, so it returns one clearly labeled
> simulated result instead of pretending to reach a provider we're not
> actually connected to."

**"How do you know your confidence score means anything?"**
> "It's five named, inspectable signals — retrieval relevance, source count,
> source authority, domain agreement, classification confidence — not a
> single opaque number. You can see all five for every answer. And our eval
> benchmark checks it against labeled expectations, live, every time."

**"What would you build next with more time?"**
> "Two things, in order: get an actual IP professional to review the corpus
> against our punch list, and swap the in-memory graph reasoning for a real
> Neo4j instance — the schema's already written to match, so that's
> mechanical, not a redesign."

**"Why should the Ministry trust an unreviewed AI tool with IP guidance at
all?"**
> "It shouldn't, unreviewed, for a final legal decision — and we don't
> position it that way. It's positioned as the first, fast, cited pass that
> tells a founder *which* provisions and authorities matter for their
> product, so the professional review that follows is faster and better-
> targeted, not skipped."

---

## 3. If something breaks live

- **Backend down / network hiccup:** Switch immediately to the pre-run
  screenshots from the pre-flight checklist. Say so plainly: "Let me show
  you the run we did just before coming up" — don't try to debug live.
- **A query gives a different/worse answer than rehearsed:** Don't panic-
  narrate. Say what you *expected* and pivot to a query you know works.
  Judges forgive a recovered stumble; they remember a flustered one.
- **Running over time:** Cut from the middle (§2.15–3.15, the PDF export),
  never from the jurisdiction-switch moment (§0:25–1:30) or the honesty
  segment (§4:00–4:40) — those two are what separate this from every other
  team's pitch.
