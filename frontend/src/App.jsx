import { useState, useEffect } from 'react'
import { AlertTriangle, ArrowUpRight, BookOpen, CheckCircle2, FileCheck2, ShieldCheck, Sparkles, ListChecks, Fingerprint, FileDown } from 'lucide-react'
import { api } from './api'
import { COPY } from './copy'
import JurisdictionSwitch from './components/JurisdictionSwitch'
import { JurisdictionMark } from './components/JurisdictionMark'
import ConfidenceMeter from './components/ConfidenceMeter'
import SourceCard from './components/SourceCard'
import EscalationModal from './components/EscalationModal'
import KnowledgeGraphView from './components/KnowledgeGraphView'
import EvalDashboard from './components/EvalDashboard'
import Hero from './components/Hero'
import EvidenceBoundary from './components/EvidenceBoundary'
import Logo from './components/Logo'
import MicButton from './components/MicButton'
import ReadAloudButton from './components/ReadAloudButton'
import { ABSTool, TKDLTool, ConnectorTool } from './components/QuickTools'
import AmbientField from './components/Ambient'
import { BotanicalCorner, ManuscriptRule } from './components/Botanical'
import { navIcon, areaIcon } from './components/DomainIcons'

const NAV = ['analyze', 'abs', 'tkdl', 'graph', 'connectors', 'eval']
const NAV_KEY = { analyze: 'navAnalyze', abs: 'navAbs', tkdl: 'navTkdl', graph: 'navGraph', connectors: 'navConnectors', eval: 'navEval' }

const CLARIFICATION_CATEGORIES = [
  'Classical / Generic Medicine',
  'Patent / Proprietary Medicine',
  'New / Non-Classical Drug',
  'Phytopharmaceutical',
  'Ayurveda-Aahar / Nutraceutical',
  'Cosmetic',
]

/**
 * Loading state: rather than grey blocks, the skeleton shows the thread being
 * drawn — the same mark used in the hero — so waiting reads as "retrieval in
 * progress along the evidence chain" instead of "something is missing".
 */
function ResultSkeleton({ copy }) {
  return (
    <div className="space-y-4 animate-in" aria-label={copy.loadingAnalysis} aria-busy="true">
      <div className="dossier-panel p-5 sm:p-6 flex items-center gap-4">
        <svg width="60" height="30" viewBox="0 0 60 30" fill="none" aria-hidden="true" className="shrink-0">
          <path className="thread-draw" d="M4 22 C 16 22, 14 8, 30 8 C 46 8, 44 22, 56 22" stroke="#B8862E" strokeWidth="1.6" strokeLinecap="round" fill="none" />
          <circle cx="4" cy="22" r="3" fill="#1F3B2C" />
          <circle cx="56" cy="22" r="3" fill="#B8862E" />
        </svg>
        <div className="flex-1 min-w-0">
          <p className="section-kicker">{copy.loadingAnalysis}</p>
          <div className="skeleton h-3 w-2/3 rounded mt-2.5" />
        </div>
      </div>
      <div className="dossier-panel p-6"><div className="skeleton h-3 w-28 rounded mb-4" /><div className="skeleton h-6 w-2/3 rounded mb-3" /><div className="skeleton h-4 w-5/6 rounded" /></div>
      <div className="dossier-panel p-6"><div className="skeleton h-3 w-24 rounded mb-4" /><div className="skeleton h-4 w-full rounded mb-3" /><div className="skeleton h-4 w-5/6 rounded mb-3" /><div className="skeleton h-4 w-3/4 rounded" /></div>
      <div className="dossier-panel p-6"><div className="skeleton h-4 w-1/2 rounded" /></div>
    </div>
  )
}

export default function App() {
  const [lang, setLang] = useState('en')
  const [jurisdiction, setJurisdiction] = useState('India')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [pendingClarification, setPendingClarification] = useState(null)
  const [tab, setTab] = useState('analyze')
  const [showEscalate, setShowEscalate] = useState(false)
  const [error, setError] = useState(null)
  const [lastConfirmedCategory, setLastConfirmedCategory] = useState(null)
  const [showHero, setShowHero] = useState(true)

  const copy = COPY[lang]

  useEffect(() => {
    api.health()
      .then((h) => setAsrConfigured(!!h?.sarvam_voice?.configured))
      .catch(() => setAsrConfigured(false))
  }, [])

  async function runAnalyze(confirmedCategory, langOverride) {
    setLoading(true)
    setError(null)
    try {
      const payload = { query, jurisdiction, language: langOverride || lang }
      if (confirmedCategory) payload.confirmed_category = confirmedCategory
      const res = await api.analyze(payload)
      if (res.classification.needs_clarification) {
        setPendingClarification(res.classification.clarification_question)
        setResult(res)
      } else {
        setPendingClarification(null)
        setResult(res)
        setLastConfirmedCategory(confirmedCategory || res.classification.category)
      }
    } catch (e) {
      setError(copy.systemError)
    } finally {
      setLoading(false)
    }
  }

  function startAnalysis() {
    setShowHero(false)
    document.getElementById('sutradhara-query')?.focus()
  }

  return (
    <>
      <AmbientField />
      <div className="app-shell min-h-screen flex flex-col">
        <header className="relative overflow-hidden border-b border-green-dark/40 bg-green text-paper sticky top-0 z-40 shadow-[0_4px_18px_rgba(20,42,31,0.16)]">
          <Logo
            size={180}
            className="pointer-events-none absolute -right-8 -top-14 text-paper opacity-[0.06]"
          />
          <BotanicalCorner size={150} className="pointer-events-none absolute -left-8 -bottom-12 text-gold-light opacity-[0.08]" />

          <div className="relative max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-gold-light/35 bg-paper/10 text-gold-light shrink-0 shadow-inner">
                <Logo size={22} />
              </span>
              <div>
                <h1 className="font-serif text-2xl leading-none tracking-wide">{copy.appName}</h1>
                <p className="citation-marker text-[10px] text-gold-light/80 mt-1 tracking-[0.12em] uppercase">{copy.tagline}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="inline-flex border border-paper/25 rounded-md overflow-hidden bg-green-dark/25">
                {[
                  ['en', copy.languageEnglish],
                  ['te', copy.languageTelugu],
                  ['hi', copy.languageHindi],
                  ['ta', copy.languageTamil],
                  ['ml', copy.languageMalayalam],
                  ['sa', copy.languageSanskrit],
                ].map(([code, label], i) => (
                  <button
                    key={code}
                    onClick={() => {
                      if (lang === code) return
                      setLang(code)
                      if (result && !result.abstained) runAnalyze(lastConfirmedCategory, code)
                    }}
                    aria-pressed={lang === code}
                    className={`press px-3 py-1.5 text-xs font-medium ${i > 0 ? 'border-l border-paper/25' : ''} ${lang === code ? 'bg-paper text-green' : 'text-paper/75 hover:text-paper hover:bg-paper/10'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <nav className="relative max-w-6xl mx-auto px-4 sm:px-6 flex gap-1 text-sm overflow-x-auto" aria-label={copy.primaryNavigation}>
            {NAV.map((t) => {
              const Icon = navIcon(t)
              const active = tab === t
              return (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  aria-current={active ? 'page' : undefined}
                  className={`press inline-flex items-center gap-2 px-3 py-2.5 border-b-2 whitespace-nowrap ${
                    active ? 'border-gold bg-paper/10 text-paper' : 'border-transparent text-paper/55 hover:text-paper/90 hover:bg-paper/5'
                  }`}
                >
                  <Icon size={14} strokeWidth={active ? 2.3 : 1.9} className={active ? 'text-gold-light' : ''} />
                  {copy[NAV_KEY[t]]}
                </button>
              )
            })}
          </nav>

          <div className="h-[2.5px] bg-green-dark/40 overflow-hidden">
            {loading && <div className="trace-line h-full w-full bg-green-dark/40" />}
          </div>
        </header>

        <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 py-8 lg:py-10">
          {/* Keyed so each tool arrives with one short settle rather than
              swapping instantly — the only page-level motion in the app. */}
          <div key={tab} className="view-enter">
            {tab === 'graph' && (
              <KnowledgeGraphView
                copy={copy}
                defaultCategory={result?.classification?.category}
                defaultJurisdiction={jurisdiction}
              />
            )}
            {tab === 'eval' && <EvalDashboard copy={copy} />}
            {tab === 'abs' && <ABSTool copy={copy} language={lang} />}
            {tab === 'tkdl' && <TKDLTool copy={copy} language={lang} />}
            {tab === 'connectors' && <ConnectorTool copy={copy} />}

            {tab === 'analyze' && (
              <>
                {showHero && !result && <Hero copy={copy} onStart={startAnalysis} />}

                <div className="dossier-panel p-4 sm:p-6 mb-7 border-green/20" id="sutradhara-analyze-panel">
                  <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-green-pale text-green shrink-0"><Sparkles size={16} /></span>
                      <div>
                        <label htmlFor="sutradhara-query" className="block text-sm font-semibold text-green-dark">{copy.inputLabel}</label>
                        <span className="text-xs text-ink/45">{copy.analysisHelper}</span>
                      </div>
                    </div>
                    <JurisdictionSwitch value={jurisdiction} onChange={setJurisdiction} copy={copy} />
                  </div>
                  <textarea
                    id="sutradhara-query"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={copy.placeholder}
                    rows={3}
                    className="research-input w-full min-h-28 border border-hairline rounded-md px-4 py-3 text-sm leading-relaxed focus:outline-none"
                  />
                  <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
                    <span className="inline-flex items-center gap-2.5 text-xs text-ink/45">
                      <JurisdictionMark jurisdiction={jurisdiction} size={13} />
                      {jurisdiction}
                      <MicButton
                        sourceLanguage={lang}
                        copy={copy}
                        onTranscribed={(text) => setQuery((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text))}
                      />
                      <ReadAloudButton
                        text={!loading && result && !result.abstained ? result.answer : ''}
                        lang={result?.answer_language || lang}
                        copy={copy}
                      />
                    </span>
                    <button
                      onClick={() => { setShowHero(false); runAnalyze() }}
                      disabled={!query.trim() || loading}
                      className="press inline-flex items-center gap-2 px-5 py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0 shadow-[0_5px_14px_rgba(31,59,44,0.18)]"
                    >
                      {loading ? copy.analyzing : copy.analyze}
                      {!loading && <ArrowUpRight size={16} />}
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="dossier-panel p-4 mb-6 border-rust/40 bg-rust/5 flex items-start gap-2.5 animate-in">
                    <AlertTriangle size={16} className="text-rust shrink-0 mt-0.5" />
                    <p className="text-sm text-rust">{error}</p>
                  </div>
                )}

                {loading && <ResultSkeleton copy={copy} />}

                {!loading && pendingClarification && (
                  <div className="dossier-panel p-5 mb-6 border-gold/40 bg-gold-light/10 animate-in">
                    <p className="text-sm font-medium mb-3">{pendingClarification}</p>
                    <div className="flex gap-2 flex-wrap">
                      {CLARIFICATION_CATEGORIES.map((cat, index) => (
                        <button
                          key={cat}
                          onClick={() => runAnalyze(cat)}
                          className="press text-xs border border-green/40 bg-paper px-3 py-1.5 rounded-md text-green hover:bg-green hover:text-paper"
                        >
                          {copy.clarificationCategories[index]}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {!loading && result && !pendingClarification && (
                  <div className="space-y-6 stagger">
                    <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-green">
                      <span className="citation-marker inline-flex items-center gap-1.5 text-xs text-green/70">
                        <JurisdictionMark jurisdiction={jurisdiction} size={13} className="text-green/70" />
                        {copy.jurisdictionPrefix}: {result.jurisdiction.toUpperCase()}
                        {result.input_language !== 'en' && (
                          <> · {copy.detectedLanguage}: {result.input_language.toUpperCase()}</>
                        )}
                      </span>
                      <div className="flex items-start gap-3 mt-3">
                        <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-green-pale text-green shrink-0"><FileCheck2 size={18} /></span>
                        <div>
                          <h2 className="font-serif text-xl text-green-dark">{copy.classification}</h2>
                          <p className="mt-1 text-lg font-semibold">{copy.classificationCategories?.[result.classification.category] || result.classification.category}</p>
                        </div>
                      </div>
                      <p className="text-sm text-ink/60 mt-1">{result.classification.reason}</p>

                      {result.applicable_areas.length > 0 && (
                        <div className="mt-5">
                          <div className="evidence-rule mb-3" />
                          <p className="section-kicker mb-2.5">{copy.applicableAreas}</p>
                          <div className="flex gap-2 flex-wrap">
                            {result.applicable_areas.map((a) => {
                              const AreaIcon = areaIcon(a)
                              return (
                                <span key={a} className="area-chip">
                                  <AreaIcon size={13} strokeWidth={2} />
                                  {copy.areaLabels?.[a] || a}
                                </span>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>

                    {result.abstained ? (
                      <EvidenceBoundary result={result} copy={copy} onEscalate={() => setShowEscalate(true)} />
                    ) : (
                      <>
                        <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-gold">
                          <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                            <div className="flex items-center gap-2"><BookOpen size={17} className="text-gold-dark" /><h3 className="font-serif text-lg">{copy.assessment}</h3></div>
                            {result.llm_paraphrased && (
                              <span className="citation-marker text-[10px] text-ink/40 border border-hairline px-2 py-0.5 rounded-full">
                                {copy.paraphraseVerified}
                              </span>
                            )}
                          </div>
                          {!result.translation_available && result.answer_language !== 'en' && (
                            <p className="text-xs text-rust mb-2">
                              {copy.translationUnavailableAnswer}
                            </p>
                          )}
                          <p className="text-sm leading-[1.75] whitespace-pre-line text-ink/85 max-w-[72ch]">{result.answer}</p>
                        </div>

                        {result.tk_pointer && (
                          <div className="dossier-panel p-5 border-gold/40 bg-gold-light/10">
                            <p className="section-kicker mb-1.5 font-medium">
                              {copy.tkPointer}
                            </p>
                            <p className="text-sm text-ink/75 max-w-[72ch]">{result.tk_pointer}</p>
                          </div>
                        )}

                        {result.abs_checklist && (
                          <div className="dossier-panel p-5 border-l-4 border-l-earth">
                            <p className="section-kicker text-ink/55 mb-2 font-medium flex items-center gap-2"><ShieldCheck size={14} className="text-earth" />
                              {copy.absConsiderations}
                            </p>
                            <ul className="text-sm space-y-1 text-ink/75">
                              <li>{result.abs_checklist.biological_resource_involved ? '☑' : '☐'} {copy.absChecklist.biologicalResource}</li>
                              <li>{result.abs_checklist.provenance_identified ? '☑' : '☐'} {copy.absChecklist.provenance}</li>
                              <li>{result.abs_checklist.abs_framework_identified ? '☑' : '☐'} {copy.absChecklist.framework}</li>
                              <li>{result.abs_checklist.supporting_source_retrieved ? '☑' : '☐'} {copy.absChecklist.source}</li>
                            </ul>
                            <p className="text-xs text-ink/50 mt-2">{result.abs_checklist.note}</p>
                          </div>
                        )}

                        <ConfidenceMeter
                          confidence={result.confidence}
                          label={result.confidence_label}
                          breakdown={result.confidence_breakdown}
                          copy={copy}
                        />

                        <div>
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <CheckCircle2 size={17} className="text-green" />
                              <h3 className="font-serif text-lg">{copy.sources}</h3>
                              <span className="citation-marker text-[11px] text-ink/40 border border-hairline rounded-full px-2 py-0.5">{result.sources.length}</span>
                            </div>
                          </div>
                          <div className="grid gap-3">
                            {result.sources.map((s, i) => (
                              <SourceCard key={s.id} source={s} index={i} copy={copy} />
                            ))}
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-2 flex-wrap gap-3">
                          <p className="text-xs text-ink/45 italic">{copy.disclaimer}</p>
                          <div className="text-right">
                            <p className="text-xs text-ink/55 mb-1">{copy.needExpert}</p>
                            <button
                              onClick={() => setShowEscalate(true)}
                              className="text-sm text-green underline underline-offset-2 hover:text-green-dark"
                            >
                              {copy.escalate}
                            </button>
                          </div>
                        </div>
                      </>
                    )}

                    {result.regulatory_pathway && result.regulatory_pathway.length > 0 && (
                      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-green">
                        <div className="flex items-center gap-2 mb-3">
                          <ListChecks size={17} className="text-green" />
                          <h3 className="font-serif text-lg">{copy.regulatoryPathway}</h3>
                        </div>
                        <ol className="space-y-3">
                          {result.regulatory_pathway.map((step, i) => (
                            <li key={i} className="flex gap-3 text-sm text-ink/80 max-w-[70ch]">
                              <span className="citation-marker shrink-0 w-6 h-6 rounded-full bg-green-pale text-green text-[11px] flex items-center justify-center mt-px border border-green/15">{i + 1}</span>
                              <span className="pt-0.5">{step}</span>
                            </li>
                          ))}
                        </ol>
                        <p className="text-xs text-ink/45 mt-3 italic">{copy.pathwayDisclaimer}</p>
                      </div>
                    )}

                    {result.tk_similarity && result.tk_similarity.length > 0 && (
                      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-earth">
                        <div className="flex items-center gap-2 mb-1">
                          <Fingerprint size={17} className="text-earth" />
                          <h3 className="font-serif text-lg">{copy.tkResemblance}</h3>
                        </div>
                        <p className="text-xs text-ink/50 mb-3 max-w-[70ch]">{copy.tkResemblanceNote}</p>
                        <div className="space-y-2">
                          {result.tk_similarity.map((m) => (
                            <div key={m.name} className="lift-on-hover flex items-center justify-between gap-3 border border-hairline rounded-md px-3.5 py-2.5 bg-paper/50">
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-ink/85">{m.name}</p>
                                <p className="text-xs text-ink/55 truncate">{m.description}</p>
                              </div>
                              <span className="citation-marker shrink-0 text-xs font-semibold text-earth bg-earth/10 border border-earth/20 px-2 py-1 rounded-md">
                                {Math.round(m.similarity * 100)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex justify-end">
                      <button
                        onClick={() => api.downloadPosturePdf({ query, result })}
                        className="press inline-flex items-center gap-2 px-4 py-2.5 border border-green text-green text-sm font-semibold rounded-md hover:bg-green hover:text-paper"
                      >
                        <FileDown size={15} />
                        {copy.downloadPosture}
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </main>

        <footer className="border-t border-hairline py-7 text-center">
          <ManuscriptRule className="text-gold max-w-[220px] mx-auto mb-3" />
          <p className="citation-marker text-[11px] text-ink/40">{copy.appName} · {copy.team} · SIH26045</p>
        </footer>

        {showEscalate && result && (
          <EscalationModal
            copy={copy}
            context={{
              query,
              category: result.classification?.category,
              jurisdiction: result.jurisdiction,
              areas: result.applicable_areas,
              sourceIds: (result.sources || []).map((s) => s.id),
            }}
            onClose={() => setShowEscalate(false)}
          />
        )}
      </div>
    </>
  )
}
