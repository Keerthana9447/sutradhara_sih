# SUTRADHARA — Content Provenance & Legal Review Log

**Purpose of this document.** An external technical assessment scored this
project 4/10 on "legal/content accuracy risk," for one specific, correct
reason: no actual IP professional has reviewed the corpus. That's still true
after this document — we can't manufacture a credential we don't have. What
this document does instead is the thing a careful team actually can do
before a demo: state precisely what level of verification each piece of
content has, flag exactly what still needs a professional's eyes, and give
the team a straight answer to give a judge who pushes on this. Presenting
this document *to* a judge, unprompted, is itself part of closing the gap —
it demonstrates the due diligence a professional review would build on,
rather than hoping the question doesn't come up.

---

## 1. What "review status" means here

Every one of the 29 entries in `backend/data/corpus.json` falls into one of
three tiers. None of them means "professionally reviewed" — that tier
doesn't exist yet for this project.

- **Tier A — Established/textbook fact.** The Act name, year, and general
  provision described are settled, widely-taught facts (e.g. the Berne
  Convention dates to 1886; TRIPS Article 27 sets the baseline patentability
  test). Risk of outright fabrication is very low. Risk of *nuance* being
  wrong (how a court has actually interpreted the provision, exceptions,
  recent amendments) is not zero.
- **Tier B — Recently verified against a primary/official source.** Checked
  against WIPO's own treaty-status pages, official Gazette-notification
  reporting, or the Act's own text at the time this corpus entry was written
  or last updated. Still not the same as a lawyer confirming the
  *application* of the provision to a specific fact pattern.
- **Tier C — Interpretive synthesis.** The `summary` field in every corpus
  entry is *our own paraphrase* of what a provision does, written to be
  readable by a founder, not a verbatim reproduction of statutory text. Even
  where the underlying Act/citation is Tier A or B, the paraphrase itself
  has only had engineering-team eyes on it, not legal ones. **This is the
  actual place the 4/10 score is pointing at**, more than the citations
  themselves.

## 2. Full corpus review table

| ID | Instrument | Tier | Note |
|---|---|---|---|
| IN-PAT-3P | Patents Act, 1970, §3(p) | A | Well-known provision; wording matches standard legal reference texts |
| IN-PAT-3J | Patents Act, 1970, §3(j) | A | Same |
| IN-BDA-2002 | Biological Diversity Act, 2002 | A | General framework only, not a specific clause |
| IN-DC-1940 | Drugs and Cosmetics Act, 1940 + Rules 1945 | A | Ayurvedic/Siddha/Unani chapter is well-documented |
| IN-FSSAI-2016 | FSSAI Ayurveda-Aahar category | A | General scope only |
| IN-GI-1999 | Geographical Indications Act, 1999 | A | General framework |
| INTL-TRIPS-27 | TRIPS Art. 27 | A | Extremely well-established |
| INTL-CBD-1992 | Convention on Biological Diversity | A | Extremely well-established |
| INTL-NAGOYA-2010 | Nagoya Protocol | A | Extremely well-established |
| INTL-TKDL | TKDL description | A | General description of a known, named database |
| INTL-WIPO-TK | WIPO IGC mandate | A | General description of a known, named body |
| IN-TM-1999 | Trade Marks Act, 1999 | A | General framework |
| IN-COPYRIGHT-1957 | Copyright Act, 1957 | A | General framework |
| IN-DESIGNS-2000 | Designs Act, 2000 | A | General framework |
| IN-PPVFR-2001 | Protection of Plant Varieties and Farmers' Rights Act, 2001 | A | General framework |
| IN-DMR-1954 | Drugs and Magic Remedies Act, 1954 | A | General framework |
| IN-LM-2011 | Legal Metrology (Packaged Commodities) Rules, 2011 | A | General framework |
| IN-FSSA-2006 | Food Safety and Standards Act, 2006 | A | General framework |
| INTL-WIPO-CONV-1967 | WIPO Convention, 1967 | A | Extremely well-established |
| INTL-PCT-1970 | Patent Cooperation Treaty, 1970 | A | Extremely well-established |
| INTL-MADRID-1989 | Madrid Protocol, 1989 | A | Extremely well-established |
| INTL-HAGUE-1999 | Hague Agreement, 1999 Act | A | Extremely well-established |
| INTL-BERNE-1886 | Berne Convention, 1886 | A | Extremely well-established |
| INTL-PARIS-1883 | Paris Convention, 1883 | A | Extremely well-established |
| INTL-UPOV-1991 | UPOV Convention, 1991 Act | A | Extremely well-established |
| **INTL-WIPO-GRATK-2024** | WIPO GRATK Treaty, 2024 | **B** | Re-verified via live web search on the date of this document; confirmed adopted 24 May 2024, only 2 of 15 required ratifications deposited (Malawi, Uganda), **not in force**, India not a signatory. See §3. |
| **INTL-BUDAPEST-1977** | Budapest Treaty, 1977/1980 | A | Well-established framework treaty |
| **IN-PAT-RULES-2024** | Patents (Amendment) Rules, 2024 | **B** | Sourced from public secondary legal-analysis reporting on the March 2024 Gazette notification, not the primary Gazette text directly — flagged in the corpus entry itself |
| **IN-BD-RULES-2024** | Biological Diversity Rules, 2024 | **B** | Same caveat — secondary reporting on the Oct/Dec 2024 notification, not primary Gazette text |

**26 of 29 entries are Tier A** (long-settled law, low fabrication risk).
**3 entries are Tier B** — all three are the most *recent* additions (2024
instruments), which is exactly where "recent enough that we should double-
check it" and "novel enough that few competing teams will even know it
exists" overlap. That overlap is a genuine differentiator (see the earlier
competitive-differentiation notes) but it's also where the real residual
risk concentrates. **Every corpus entry, Tier A through C, is Tier C for its
`summary` paraphrase** — see §1.

## 3. What changed today

The `INTL-WIPO-GRATK-2024` entry was re-verified against live WIPO
treaty-status documentation as part of responding to this review. Two
things were added that were previously only asserted in general terms:

- Exact ratification count as of the most recent available WIPO status
  notification: **2 of 15 required** (Malawi, 5 Dec 2024; Uganda, 9 Jul
  2025) — meaning the treaty's disclosure obligation is **not binding
  anywhere yet**, a fact that matters if a judge asks "so does this apply to
  me?" (Answer: not yet, anywhere, but it's worth knowing about now because
  it signals where international disclosure obligations are heading.)
- Confirmed India does not appear among the treaty's signatories in that
  same WIPO status list, as of the same check.

This is the kind of correction a professional review would also make —
which is the point: it shows the review *process* works, not that the
process is finished.

## 4. What still needs a professional's eyes, specifically

If the team has any access at all to a law student specializing in IP, a
junior associate at an IP firm, or a facilitator at AIIA's own legal/IP
cell, the highest-value use of even 60–90 minutes of their time, ranked:

1. **Read the `summary` field of the 6 most-retrieved corpus entries**
   (IN-PAT-3P, IN-PAT-3J, IN-DC-1940, IN-BDA-2002, IN-PAT-RULES-2024,
   IN-BD-RULES-2024 — check via `GET /api/eval/benchmark` or the audit log
   for which sources actually get cited most in practice) and flag any
   paraphrase that overstates, understates, or subtly mischaracterizes what
   the provision does.
2. **Sanity-check the `pathway.py` regulatory checklists** (the
   "Indicative Regulatory Pathway" section shown after every answered
   query) — these are the most exposed content in the app, because they
   read as actionable instructions rather than descriptive summaries, even
   though they're phrased as "indicative" and carry a disclaimer.
3. **Re-verify the two 2024 Rules entries** (`IN-PAT-RULES-2024`,
   `IN-BD-RULES-2024`) against the actual Gazette notifications rather than
   secondary reporting, since those are explicitly flagged as unverified at
   that level in the corpus itself.
4. Everything else is Tier A and lower-priority for a first review pass.

## 5. If a judge challenges a specific citation live

Say this, not less than this and not more:

> "That specific citation is [Tier A/B — check the table]. The Act name,
> section, and general effect are accurate to [established legal reference /
> a primary WIPO source we checked]. The plain-language summary is our own
> paraphrase for readability, and like every legal-AI tool at this stage, it
> hasn't had a professional review yet — that's the single biggest thing on
> our punch list before this goes near a real filing decision. We built the
> system so that gap is checkable at all: every claim traces to a named
> source with a URL, so a professional can verify or correct it in minutes,
> not hours."

That answer is true, specific, and turns the weakness into a demonstration
of the architecture's actual strength (traceability) rather than a dodge.

## 6. What this document deliberately does not claim

- It does not claim any entry has been reviewed by a licensed advocate,
  patent agent, or IP professional.
- It does not claim Tier A status means zero error risk — only that the
  *kind* of error most likely (a citation to a nonexistent provision) is
  very unlikely for long-settled law.
- It does not extend review status to interpretive content generated at
  answer-time (the LLM paraphrase layer, when enabled) beyond what the
  citation-preservation check in `app/llm.py` already structurally
  guarantees (no new factual claims can be added, only tone changed).
