import { useState, useCallback, useEffect } from 'react'
import {
  AlertTriangle,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  FileCheck2,
  ShieldCheck,
  Sparkles,
  ListChecks,
  Fingerprint,
  Briefcase,
  FileDown,
  LogOut,
  User,
  Download,
  Trash2,
  Shield,
  Database,
  BookImage,
  Scale,
} from 'lucide-react'
import { api } from './api'
import { COPY } from './copy'
import useTranslatedStrings from './hooks/useTranslatedStrings'
import { useAuth } from './AuthContext'
import SignIn from './SignIn'
import SignUp from './SignUp'
import AdminSignIn from './AdminSignIn'
import ChatHistory from './components/ChatHistory'
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
import ClaimsWorkflow from './components/ClaimsWorkflow'
import ManuscriptOCR from './components/ManuscriptOCR'
import PatentsRegistry from './components/PatentsRegistry'
import AdminDashboard from './components/AdminDashboard'
import LegalPages from './components/LegalPages'

// 'workspace' and 'compliance' are parent tabs — each capability lives in
// the matching secondary tab bar rather than the primary navigation.
const CITIZEN_NAV = ['analyze', 'workspace', 'compliance', 'graph', 'connectors', 'eval', 'legal']
const ADMIN_NAV   = ['analyze', 'admin', 'workspace', 'compliance', 'graph', 'connectors', 'eval', 'legal']

// Sub-tabs for each parent, in display order. Components rendered for each
// value are unchanged from before this consolidation — see the render
// block below.
const WORKSPACE_SUBTABS = ['claims', 'ocr', 'registry']
const COMPLIANCE_SUBTABS = ['abs', 'tkdl']

// Reverse lookup for the remaining workspace and compliance tabs.
const SUBTAB_PARENT = {}
WORKSPACE_SUBTABS.forEach((t) => { SUBTAB_PARENT[t] = 'workspace' })
COMPLIANCE_SUBTABS.forEach((t) => { SUBTAB_PARENT[t] = 'compliance' })

const NAV_KEY = {
  analyze: 'navAnalyze',
  abs: 'navAbs',
  tkdl: 'navTkdl',
  graph: 'navGraph',
  connectors: 'navConnectors',
  eval: 'navEval',
  claims: 'navClaims',
  ocr: 'navOcr',
  registry: 'navRegistry',
  legal: 'navLegal',
  admin: 'navAdmin',
  workspace: 'navWorkspace',
  compliance: 'navCompliance',
}

const NAV_LABELS = {
  claims: 'My Claims',
  ocr: 'Manuscript',
  registry: 'Registry',
  legal: 'Legal',
  admin: 'Admin',
  // workspace/compliance intentionally have no English fallback here —
  // their labels come from copy.js in every supported language (see
  // NAV_KEY above), same as the other PS-named top-level tabs (abs, tkdl,
  // graph, connectors, eval, analyze).
}

const NAV_ICONS = {
  claims: FileCheck2,
  ocr: BookImage,
  registry: Database,
  legal: Scale,
  admin: Shield,
  workspace: Briefcase,
  compliance: ListChecks,
}


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
    <div
      className="space-y-4 animate-in"
      aria-label={copy.loadingAnalysis}
      aria-busy="true"
    >
      <div className="dossier-panel p-5 sm:p-6 flex items-center gap-4">
        <svg
          width="60"
          height="30"
          viewBox="0 0 60 30"
          fill="none"
          aria-hidden="true"
          className="shrink-0"
        >
          <path
            className="thread-draw"
            d="M4 22 C 16 22, 14 8, 30 8 C 46 8, 44 22, 56 22"
            stroke="#B8862E"
            strokeWidth="1.6"
            strokeLinecap="round"
            fill="none"
          />
          <circle cx="4" cy="22" r="3" fill="#1F3B2C" />
          <circle cx="56" cy="22" r="3" fill="#B8862E" />
        </svg>

        <div className="flex-1 min-w-0">
          <p className="section-kicker">{copy.loadingAnalysis}</p>
          <div className="skeleton h-3 w-2/3 rounded mt-2.5" />
        </div>
      </div>

      <div className="dossier-panel p-6">
        <div className="skeleton h-3 w-28 rounded mb-4" />
        <div className="skeleton h-6 w-2/3 rounded mb-3" />
        <div className="skeleton h-4 w-5/6 rounded" />
      </div>

      <div className="dossier-panel p-6">
        <div className="skeleton h-3 w-24 rounded mb-4" />
        <div className="skeleton h-4 w-full rounded mb-3" />
        <div className="skeleton h-4 w-5/6 rounded mb-3" />
        <div className="skeleton h-4 w-3/4 rounded" />
      </div>

      <div className="dossier-panel p-6">
        <div className="skeleton h-4 w-1/2 rounded" />
      </div>
    </div>
  )
}

/**
 * Secondary tab bar for a consolidated parent tab (Patent Workspace,
 * Compliance Tools). Reuses the exact same label/icon resolution as the
 * primary nav (NAV_LABELS / NAV_ICONS / NAV_KEY / navIcon fallback), just
 * rendered one level down and visually lighter, so grouping these tools
 * under one parent doesn't change how any individual tool is labeled.
 */
function SubTabBar({ items, active, onChange, copy, labelOverrides = {} }) {
  return (
    <div
      className="flex gap-1 text-sm overflow-x-auto mb-6 border-b border-ink/10"
      role="tablist"
    >
      {items.map((t) => {
        const Icon = NAV_ICONS[t] || navIcon(t)
        const isActive = active === t
        const label = labelOverrides[t] || NAV_LABELS[t] || copy[NAV_KEY[t]] || t
        return (
          <button
            key={t}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(t)}
            className={`press inline-flex items-center gap-2 px-3 py-2 border-b-2 whitespace-nowrap text-[13px] ${
              isActive
                ? 'border-gold text-ink font-medium'
                : 'border-transparent text-ink/50 hover:text-ink/80'
            }`}
          >
            <Icon size={13} strokeWidth={isActive ? 2.3 : 1.9} className={isActive ? 'text-gold-dark' : ''} />
            {label}
          </button>
        )
      })}
    </div>
  )
}

export default function App() {
  const { auth, signOut } = useAuth()

  // ── Chat session state ─────────────────────────────────────────────────
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [sessionLoading, setSessionLoading] = useState(false)

  // ── Analyze state ──────────────────────────────────────────────────────
  const [lang, setLang] = useState('en')
  const [queryDepth, setQueryDepth] = useState('guided')
  const [jurisdiction, setJurisdiction] = useState('India')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [pendingClarification, setPendingClarification] = useState(null)
  const [tab, setTab] = useState('analyze')
  // Sub-tab within each consolidated parent. Kept as two separate pieces of
  // state (rather than one) so switching away from, say, "workspace" and
  // back to it later restores whichever sub-tool was open, instead of
  // always resetting to the first one.
  const [workspaceSubTab, setWorkspaceSubTab] = useState('claims')
  const [complianceSubTab, setComplianceSubTab] = useState('abs')
  const [showEscalate, setShowEscalate] = useState(false)
  const [error, setError] = useState(null)
  const [lastConfirmedCategory, setLastConfirmedCategory] = useState(null)
  const [showHero, setShowHero] = useState(true)
  const [userRole, setUserRole] = useState('citizen') // 'citizen' | 'admin'
  const [authPage, setAuthPage] = useState('signin') // 'signin' | 'signup' | 'admin'

  const copy = COPY[lang]
  const { text: navLabel } = useTranslatedStrings(lang, NAV_LABELS)
  const analysisTranslationSource = {
    queryDepthLabel: 'Query depth',
    quickDepth: 'Quick · 3 sources',
    guidedDepth: 'Guided · 5 sources',
    deepDepth: 'Deep · up to 10 sources',
    evidenceCoverage: 'Answer integrity checks:',
    pass: 'pass',
    retryWith: 'Retry with',
    depthSuffix: 'depth',
    regimeMatrix: 'Per-regime screening matrix',
    translationUnavailable: 'Some analysis labels or explanations could not be translated; untranslated text is shown in English.',
    evalMethod: result?.eval_method || '',
    ...Object.fromEntries((result?.regime_verdicts || []).flatMap((item, index) => [
      [`regimeLabel${index}`, item.label],
      [`regimeVerdict${index}`, item.verdict.replaceAll('_', ' ')],
      [`regimeBasis${index}`, item.basis],
    ])),
  }
  const { text: analysisText, available: analysisTranslationAvailable, pending: analysisTranslationPending } =
    useTranslatedStrings(lang, analysisTranslationSource)

  // ── Fetch user role after sign-in ───────────────────────────────────────
  useEffect(() => {
    if (!auth) return
    const API_ORIGIN = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
    fetch(`${API_ORIGIN}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
      .then(r => r.ok ? r.json() : { role: 'citizen' })
      .then(d => setUserRole(d.role || 'citizen'))
      .catch(() => setUserRole('citizen'))
  }, [auth])

  const NAV = userRole === 'admin' ? ADMIN_NAV : CITIZEN_NAV

  // ── Deep-linkability for consolidated tabs ──────────────────────────────
  // Hash shape is #<parentTab> or #<parentTab>/<subTab>, e.g. #workspace/ocr,
  // #compliance/tkdl, #graph. Existing supported sub-tabs are resolved
  // through SUBTAB_PARENT; removed feature hashes are ignored.
  useEffect(() => {
    const applyHash = (hash) => {
      const [rawTab, rawSub] = hash.replace(/^#/, '').split('/')
      if (!rawTab) return
      if (SUBTAB_PARENT[rawTab]) {
        // Legacy flat hash, e.g. #ocr -> workspace/ocr
        const parent = SUBTAB_PARENT[rawTab]
        setTab(parent)
        if (parent === 'workspace') setWorkspaceSubTab(rawTab)
        else setComplianceSubTab(rawTab)
        return
      }
      if (rawTab === 'workspace' || rawTab === 'compliance') {
        setTab(rawTab)
        if (rawSub && SUBTAB_PARENT[rawSub] === rawTab) {
          if (rawTab === 'workspace') setWorkspaceSubTab(rawSub)
          else setComplianceSubTab(rawSub)
        }
        return
      }
      if (NAV.includes(rawTab) || CITIZEN_NAV.includes(rawTab) || ADMIN_NAV.includes(rawTab)) {
        setTab(rawTab)
      }
    }
    if (window.location.hash) applyHash(window.location.hash)
    const onHashChange = () => applyHash(window.location.hash)
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Keep the URL hash in sync so the current view is always bookmarkable/
  // shareable, including which sub-tool is open inside a parent tab.
  useEffect(() => {
    const sub = tab === 'workspace' ? workspaceSubTab : tab === 'compliance' ? complianceSubTab : null
    const next = '#' + (sub ? `${tab}/${sub}` : tab)
    if (window.location.hash !== next) {
      window.history.replaceState(null, '', next)
    }
  }, [tab, workspaceSubTab, complianceSubTab])

  const createNewSession = useCallback(async () => {
    if (!auth) return null
    try {
      const session = await api.createChatSession(auth.user.id)
      setActiveSessionId(session.id)
      // Clear current view
      setQuery('')
      setResult(null)
      setPendingClarification(null)
      setError(null)
      setShowHero(true)
      return session.id
    } catch {
      return null
    }
  }, [auth])

  // ── Load a past session's messages into the view ──────────────────────
  const loadSession = useCallback(async (sessionId) => {
    if (!auth) return
    setSessionLoading(true)
    setActiveSessionId(sessionId)
    setResult(null)
    setQuery('')
    setPendingClarification(null)
    setError(null)
    setShowHero(false)
    try {
      const messages = await api.getChatMessages(sessionId, auth.user.id)
      // Find the last assistant message and restore it as the current result
      const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
      const lastUser = [...messages].reverse().find((m) => m.role === 'user')
      if (lastAssistant) {
        try {
          setResult(JSON.parse(lastAssistant.content))
        } catch {
          setResult(null)
        }
      }
      if (lastUser) setQuery(lastUser.content)
    } catch {
      /* ignore */
    } finally {
      setSessionLoading(false)
    }
  }, [auth])

  // ── Ensure there's always an active session once signed in ───────────
  useEffect(() => {
    if (auth && !activeSessionId) {
      createNewSession()
    }
  }, [auth, activeSessionId, createNewSession])

  async function runAnalyze(confirmedCategory, langOverride, depthOverride) {
    setLoading(true)
    setError(null)

    try {
      const payload = {
        query,
        jurisdiction,
        language: langOverride || lang,
        query_depth: depthOverride || queryDepth,
        session_id: activeSessionId || undefined,
        user_id: auth?.user?.id || undefined,
      }

      if (confirmedCategory) {
        payload.confirmed_category = confirmedCategory
      }

      // Use session-aware endpoint when signed in, otherwise plain analyze
      const res = auth
        ? await api.analyzeSession(payload)
        : await api.analyze(payload)

      if (res.classification.needs_clarification) {
        setPendingClarification(
          res.classification.clarification_question
        )
        setResult(res)
      } else {
        setPendingClarification(null)
        setResult(res)
        setLastConfirmedCategory(
          confirmedCategory || res.classification.category
        )
      }
    } catch (e) {
      console.error('Analyze error:', e)
      setError(copy.systemError)
    } finally {
      setLoading(false)
    }
  }

  function startAnalysis() {
    setShowHero(false)
    document.getElementById('sutradhara-query')?.focus()
  }

  async function handleSignOut() {
    if (auth?.token) {
      try { await api.signOut() } catch { /* ignore */ }
    }
    signOut()
    setActiveSessionId(null)
    setResult(null)
    setQuery('')
  }

  // DPDP rights over the signed-in account's own data.
  async function handleExportAccount() {
    try {
      const data = await api.exportAccount()
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      const a = document.createElement('a')
      a.href = url
      a.download = 'sutradhara-my-data.json'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      window.alert('Could not export your data. Please sign in again and retry.')
    }
  }

  async function handleDeleteAccount() {
    if (!window.confirm('Permanently delete your account, all saved conversations and login sessions? This cannot be undone.')) return
    try {
      await api.deleteAccount()
      signOut()
      setActiveSessionId(null)
      setResult(null)
      setQuery('')
    } catch {
      window.alert('Could not delete your account. Please sign in again and retry.')
    }
  }

  // ── Auth gate ─────────────────────────────────────────────────────────
  if (!auth) {
    if (authPage === 'admin') return <AdminSignIn onGoBack={() => setAuthPage('signin')} />
    return authPage === 'signin'
      ? <SignIn onGoSignUp={() => setAuthPage('signup')} onGoAdmin={() => setAuthPage('admin')} />
      : <SignUp onGoSignIn={() => setAuthPage('signin')} />
  }

  return (
    <>
      <AmbientField />

      <div className="app-shell h-screen flex flex-col overflow-hidden">
        <header className="relative overflow-hidden border-b border-green-dark/40 bg-green text-paper sticky top-0 z-40 shadow-[0_4px_18px_rgba(20,42,31,0.16)]">
          <Logo
            size={180}
            className="pointer-events-none absolute -right-8 -top-14 text-paper opacity-[0.06]"
          />

          <BotanicalCorner
            size={150}
            className="pointer-events-none absolute -left-8 -bottom-12 text-gold-light opacity-[0.08]"
          />

          <div className="relative max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between flex-wrap gap-4 header-inner">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-gold-light/35 bg-paper/10 text-gold-light shrink-0 shadow-inner">
                <Logo size={22} />
              </span>

              <div>
                <h1 className="font-serif text-2xl leading-none tracking-wide">
                  {copy.appName}
                </h1>

                <p className="citation-marker text-[10px] text-gold-light/80 mt-1 tracking-[0.12em] uppercase">
                  {copy.tagline}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="lang-scroll border border-paper/25 rounded-md overflow-hidden bg-green-dark/25">
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

                      if (result && !result.abstained) {
                        runAnalyze(lastConfirmedCategory, code)
                      }
                    }}
                    aria-pressed={lang === code}
                    className={`press px-3 py-1.5 text-xs font-medium ${
                      i > 0
                        ? 'border-l border-paper/25'
                        : ''
                    } ${
                      lang === code
                        ? 'bg-paper text-green'
                        : 'text-paper/75 hover:text-paper hover:bg-paper/10'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* User info + sign out */}
              <div className="flex items-center gap-2 border-l border-paper/20 pl-3">
                <span className="flex items-center gap-1.5 text-xs text-paper/70">
                  <User size={13} />
                  {auth.user.name}
                </span>
                <button
                  onClick={handleExportAccount}
                  title="Download my data (JSON)"
                  className="press p-1.5 rounded-md text-paper/50 hover:text-paper hover:bg-paper/10"
                >
                  <Download size={14} />
                </button>
                <button
                  onClick={handleDeleteAccount}
                  title="Delete my account and data"
                  className="press p-1.5 rounded-md text-paper/50 hover:text-paper hover:bg-paper/10"
                >
                  <Trash2 size={14} />
                </button>
                <button
                  onClick={handleSignOut}
                  title="Sign out"
                  className="press p-1.5 rounded-md text-paper/50 hover:text-paper hover:bg-paper/10"
                >
                  <LogOut size={14} />
                </button>
              </div>
            </div>
          </div>

          <nav
            className="relative max-w-6xl mx-auto px-4 sm:px-6 flex gap-1 text-sm overflow-x-auto nav-tabs"
            aria-label={copy.primaryNavigation}
          >
            {NAV.map((t) => {
              const Icon = NAV_ICONS[t] || navIcon(t)
              const active = tab === t
              const label = navLabel(t) || copy[NAV_KEY[t]] || t

              return (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  aria-current={active ? 'page' : undefined}
                  className={`press inline-flex items-center gap-2 px-3 py-2.5 border-b-2 whitespace-nowrap ${
                    active
                      ? t === 'admin'
                        ? 'border-rust bg-paper/10 text-paper'
                        : 'border-gold bg-paper/10 text-paper'
                      : 'border-transparent text-paper/55 hover:text-paper/90 hover:bg-paper/5'
                  }`}
                >
                  <Icon
                    size={14}
                    strokeWidth={active ? 2.3 : 1.9}
                    className={active ? (t === 'admin' ? 'text-rust' : 'text-gold-light') : ''}
                  />

                  {label}
                </button>
              )
            })}
          </nav>

          <div className="h-[2.5px] bg-green-dark/40 overflow-hidden">
            {loading && (
              <div className="trace-line h-full w-full bg-green-dark/40" />
            )}
          </div>
        </header>

        {/* Body: sidebar + main content */}
        <div className="relative flex flex-1 min-h-0">
          <ChatHistory
            userId={auth.user.id}
            activeSessionId={activeSessionId}
            onSelectSession={loadSession}
            onNewSession={createNewSession}
          />

          <main className="app-main flex-1 min-w-0 overflow-y-auto px-4 sm:px-6 py-8 lg:py-10 mobile-py">
          <div key={tab} className="view-enter max-w-5xl mx-auto">
            {tab === 'graph' && (
              <KnowledgeGraphView
                copy={copy}
                defaultCategory={result?.classification?.category}
                defaultJurisdiction={jurisdiction}
              />
            )}

            {tab === 'eval' && <EvalDashboard copy={copy} />}
            {tab === 'compliance' && (
              <>
                <SubTabBar
                  items={COMPLIANCE_SUBTABS}
                  active={complianceSubTab}
                  onChange={setComplianceSubTab}
                  copy={copy}
                  labelOverrides={Object.fromEntries(Object.keys(NAV_LABELS).map((key) => [key, navLabel(key)]))}
                />
                {complianceSubTab === 'abs' && (
                  <ABSTool copy={copy} language={lang} />
                )}
                {complianceSubTab === 'tkdl' && (
                  <TKDLTool copy={copy} language={lang} />
                )}
              </>
            )}

            {tab === 'connectors' && (
              <ConnectorTool copy={copy} language={lang} />
            )}

            {/* ── New feature tabs, grouped under Patent Workspace ── */}
            {tab === 'workspace' && (
              <>
                <SubTabBar
                  items={WORKSPACE_SUBTABS}
                  active={workspaceSubTab}
                  onChange={setWorkspaceSubTab}
                  copy={copy}
                  labelOverrides={Object.fromEntries(Object.keys(NAV_LABELS).map((key) => [key, navLabel(key)]))}
                />
                {workspaceSubTab === 'claims' && (
                  <ClaimsWorkflow copy={copy} language={lang} />
                )}
                {workspaceSubTab === 'ocr' && (
                  <ManuscriptOCR copy={copy} language={lang} />
                )}
                {workspaceSubTab === 'registry' && (
                  <PatentsRegistry copy={copy} language={lang} />
                )}
              </>
            )}

            {tab === 'legal' && (
              <LegalPages copy={copy} language={lang} />
            )}

            {tab === 'admin' && userRole === 'admin' && (
              <AdminDashboard user={auth.user} />
            )}

            {tab === 'analyze' && (
              <>
                {sessionLoading && (
                  <div className="flex items-center justify-center py-16 text-ink/40 gap-3">
                    <svg className="animate-spin w-5 h-5 text-green" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    <span className="text-sm">Loading conversation…</span>
                  </div>
                )}

                {!sessionLoading && showHero && !result && (
                  <Hero copy={copy} onStart={startAnalysis} />
                )}

                {!sessionLoading && (
                <div
                  className="dossier-panel p-4 sm:p-6 mb-7 border-green/20"
                  id="sutradhara-analyze-panel"
                >
                  <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-green-pale text-green shrink-0">
                        <Sparkles size={16} />
                      </span>

                      <div>
                        <label
                          htmlFor="sutradhara-query"
                          className="block text-sm font-semibold text-green-dark"
                        >
                          {copy.inputLabel}
                        </label>

                        <span className="text-xs text-ink/45">
                          {copy.analysisHelper}
                        </span>
                      </div>
                    </div>

                    <JurisdictionSwitch
                      value={jurisdiction}
                      onChange={setJurisdiction}
                      copy={copy}
                    />
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
                      <JurisdictionMark
                        jurisdiction={jurisdiction}
                        size={13}
                      />

                      {jurisdiction}

                      <MicButton
                        sourceLanguage={lang}
                        copy={copy}
                        onTranscribed={(text) =>
                          setQuery((prev) =>
                            prev.trim()
                              ? `${prev.trim()} ${text}`
                              : text
                          )
                        }
                      />

                      <ReadAloudButton
                        text={
                          !loading &&
                          result &&
                          !result.abstained
                            ? result.answer
                            : ''
                        }
                        lang={result?.answer_language || lang}
                        copy={copy}
                      />
                    </span>

                    <button
                      onClick={() => {
                        setShowHero(false)
                        runAnalyze()
                      }}
                      disabled={!query.trim() || loading}
                      className="press inline-flex items-center gap-2 px-5 py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0 shadow-[0_5px_14px_rgba(31,59,44,0.18)]"
                    >
                      {loading ? copy.analyzing : copy.analyze}

                      {!loading && <ArrowUpRight size={16} />}
                    </button>
                  </div>
                  <label className="mt-3 flex items-center gap-2 text-xs text-ink/60">
                    {analysisText('queryDepthLabel')}
                    <select value={queryDepth} onChange={(e) => setQueryDepth(e.target.value)} className="border border-hairline rounded px-2 py-1 bg-paper text-ink">
                      <option value="quick">{analysisText('quickDepth')}</option>
                      <option value="guided">{analysisText('guidedDepth')}</option>
                      <option value="deep">{analysisText('deepDepth')}</option>
                    </select>
                  </label>
                </div>
                )}{/* end !sessionLoading */}

                {error && (
                  <div className="dossier-panel p-4 mb-6 border-rust/40 bg-rust/5 flex items-start gap-2.5 animate-in">
                    <AlertTriangle
                      size={16}
                      className="text-rust shrink-0 mt-0.5"
                    />

                    <p className="text-sm text-rust">
                      {error}
                    </p>
                  </div>
                )}

                {loading && <ResultSkeleton copy={copy} />}

                {!loading && pendingClarification && (
                  <div className="dossier-panel p-5 mb-6 border-gold/40 bg-gold-light/10 animate-in">
                    <p className="text-sm font-medium mb-3">
                      {pendingClarification}
                    </p>

                    <div className="flex gap-2 flex-wrap">
                      {CLARIFICATION_CATEGORIES.map(
                        (cat, index) => (
                          <button
                            key={cat}
                            onClick={() => runAnalyze(cat)}
                            className="press text-xs border border-green/40 bg-paper px-3 py-1.5 rounded-md text-green hover:bg-green hover:text-paper"
                          >
                            {copy.clarificationCategories[index]}
                          </button>
                        )
                      )}
                    </div>
                  </div>
                )}

                {!loading &&
                  result &&
                  !pendingClarification && (
                    <div className="space-y-6 stagger">
                      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-green">
                        <span className="citation-marker inline-flex items-center gap-1.5 text-xs text-green/70">
                          <JurisdictionMark
                            jurisdiction={jurisdiction}
                            size={13}
                            className="text-green/70"
                          />

                          {copy.jurisdictionPrefix}:{' '}
                          {result.jurisdiction.toUpperCase()}

                          {result.input_language !== 'en' && (
                            <>
                              {' · '}
                              {copy.detectedLanguage}:{' '}
                              {result.input_language.toUpperCase()}
                            </>
                          )}
                        </span>

                        <div className="flex items-start gap-3 mt-3">
                          <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-green-pale text-green shrink-0">
                            <FileCheck2 size={18} />
                          </span>

                          <div>
                            <h2 className="font-serif text-xl text-green-dark">
                              {copy.classification}
                            </h2>

                            <p className="mt-1 text-lg font-semibold">
                              {copy.classificationCategories?.[
                                result.classification.category
                              ] ||
                                result.classification.category}
                            </p>
                          </div>
                        </div>

                        <p className="text-sm text-ink/60 mt-1">
                          {result.classification.reason}
                        </p>

                        {result.applicable_areas.length > 0 && (
                          <div className="mt-5">
                            <div className="evidence-rule mb-3" />

                            <p className="section-kicker mb-2.5">
                              {copy.applicableAreas}
                            </p>

                            <div className="flex gap-2 flex-wrap">
                              {result.applicable_areas.map((a) => {
                                const AreaIcon = areaIcon(a)

                                return (
                                  <span
                                    key={a}
                                    className="area-chip"
                                  >
                                    <AreaIcon
                                      size={13}
                                      strokeWidth={2}
                                    />

                                    {copy.areaLabels?.[a] || a}
                                  </span>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </div>

                      {result.abstained ? (
                        <EvidenceBoundary
                          result={result}
                          copy={copy}
                          onEscalate={() =>
                            setShowEscalate(true)
                          }
                        />
                      ) : (
                        <>
                          <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-gold">
                            <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                              <div className="flex items-center gap-2">
                                <BookOpen
                                  size={17}
                                  className="text-gold-dark"
                                />

                                <h3 className="font-serif text-lg">
                                  {copy.assessment}
                                </h3>
                              </div>

                              {result.llm_paraphrased && (
                                <span className="citation-marker text-[10px] text-ink/40 border border-hairline px-2 py-0.5 rounded-full">
                                  {copy.paraphraseVerified}
                                </span>
                              )}
                            </div>

                            {!result.translation_available &&
                              result.answer_language !== 'en' && (
                                <p className="text-xs text-rust mb-2">
                                  {copy.translationUnavailableAnswer}
                                </p>
                              )}

                            <p className="text-sm leading-[1.75] whitespace-pre-line text-ink/85 max-w-[72ch]">
                              {result.answer}
                            </p>
                          </div>

                          {result.tk_pointer && (
                            <div className="dossier-panel p-5 border-gold/40 bg-gold-light/10">
                              <p className="section-kicker mb-1.5 font-medium">
                                {copy.tkPointer}
                              </p>

                              <p className="text-sm text-ink/75 max-w-[72ch]">
                                {result.tk_pointer}
                              </p>
                            </div>
                          )}

                          {result.abs_checklist && (
                            <div className="dossier-panel p-5 border-l-4 border-l-earth">
                              <p className="section-kicker text-ink/55 mb-2 font-medium flex items-center gap-2">
                                <ShieldCheck
                                  size={14}
                                  className="text-earth"
                                />

                                {copy.absConsiderations}
                              </p>

                              <ul className="text-sm space-y-1 text-ink/75">
                                <li>
                                  {result.abs_checklist
                                    .biological_resource_involved
                                    ? '☑'
                                    : '☐'}{' '}
                                  {copy.absChecklist.biologicalResource}
                                </li>

                                <li>
                                  {result.abs_checklist
                                    .provenance_identified
                                    ? '☑'
                                    : '☐'}{' '}
                                  {copy.absChecklist.provenance}
                                </li>

                                <li>
                                  {result.abs_checklist
                                    .abs_framework_identified
                                    ? '☑'
                                    : '☐'}{' '}
                                  {copy.absChecklist.framework}
                                </li>

                                <li>
                                  {result.abs_checklist
                                    .supporting_source_retrieved
                                    ? '☑'
                                    : '☐'}{' '}
                                  {copy.absChecklist.source}
                                </li>
                              </ul>

                              <p className="text-xs text-ink/50 mt-2">
                                {result.abs_checklist.note}
                              </p>
                            </div>
                          )}

                          <ConfidenceMeter
                            confidence={result.confidence}
                            label={result.confidence_label}
                            breakdown={result.confidence_breakdown}
                            copy={copy}
                          />
                          <div className="dossier-panel p-4 text-sm">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p><strong>{analysisText('evidenceCoverage')}</strong> {result.eval_score ?? '—'}/100 · {analysisText(`${result.query_depth || 'guided'}Depth`)} {analysisText('pass')}</p>
                              {result.suggested_query_depth && <button onClick={() => { setQueryDepth(result.suggested_query_depth); runAnalyze(lastConfirmedCategory, undefined, result.suggested_query_depth) }} className="text-xs text-green underline">{analysisText('retryWith')} {analysisText(`${result.suggested_query_depth}Depth`)} {analysisText('depthSuffix')}</button>}
                            </div>
                            <p className="text-xs text-ink/50 mt-1">{analysisText('evalMethod')}</p>
                            {!!result.regime_verdicts?.length && <details className="mt-3"><summary className="cursor-pointer font-semibold">{analysisText('regimeMatrix')}</summary><ul className="mt-2 grid sm:grid-cols-2 gap-2 text-xs">{result.regime_verdicts.map((v, index) => <li key={v.regime} className="border border-hairline rounded p-2"><strong>{analysisText(`regimeLabel${index}`)}: {analysisText(`regimeVerdict${index}`)}</strong><p className="mt-1 text-ink/55">{analysisText(`regimeBasis${index}`)}</p></li>)}</ul></details>}
                            {!analysisTranslationAvailable && !analysisTranslationPending && lang !== 'en' && <p role="status" className="mt-2 text-xs text-earth">{analysisText('translationUnavailable')}</p>}
                          </div>

                          <div>
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-2">
                                <CheckCircle2
                                  size={17}
                                  className="text-green"
                                />

                                <h3 className="font-serif text-lg">
                                  {copy.sources}
                                </h3>

                                <span className="citation-marker text-[11px] text-ink/40 border border-hairline rounded-full px-2 py-0.5">
                                  {result.sources.length}
                                </span>
                              </div>
                            </div>

                            <div className="grid gap-3">
                              {result.sources.map((s, i) => (
                                <SourceCard
                                  key={s.id}
                                  source={s}
                                  index={i}
                                  copy={copy}
                                />
                              ))}
                            </div>
                          </div>

                          <div className="flex items-center justify-between pt-2 flex-wrap gap-3">
                            <p className="text-xs text-ink/45 italic">
                              {copy.disclaimer}
                            </p>

                            <div className="text-right">
                              <p className="text-xs text-ink/55 mb-1">
                                {copy.needExpert}
                              </p>

                              <button
                                onClick={() =>
                                  setShowEscalate(true)
                                }
                                className="text-sm text-green underline underline-offset-2 hover:text-green-dark"
                              >
                                {copy.escalate}
                              </button>
                            </div>
                          </div>
                        </>
                      )}

                      {result.regulatory_pathway &&
                        result.regulatory_pathway.length > 0 && (
                          <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-green">
                            <div className="flex items-center gap-2 mb-3">
                              <ListChecks
                                size={17}
                                className="text-green"
                              />

                              <h3 className="font-serif text-lg">
                                {copy.regulatoryPathway}
                              </h3>
                            </div>

                            <ol className="space-y-3">
                              {result.regulatory_pathway.map(
                                (step, i) => (
                                  <li
                                    key={i}
                                    className="flex gap-3 text-sm text-ink/80 max-w-[70ch]"
                                  >
                                    <span className="citation-marker shrink-0 w-6 h-6 rounded-full bg-green-pale text-green text-[11px] flex items-center justify-center mt-px border border-green/15">
                                      {i + 1}
                                    </span>

                                    <span className="pt-0.5">
                                      {step}
                                    </span>
                                  </li>
                                )
                              )}
                            </ol>

                            <p className="text-xs text-ink/45 mt-3 italic">
                              {copy.pathwayDisclaimer}
                            </p>
                          </div>
                        )}

                      {result.tk_similarity &&
                        result.tk_similarity.length > 0 && (
                          <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-earth">
                            <div className="flex items-center gap-2 mb-1">
                              <Fingerprint
                                size={17}
                                className="text-earth"
                              />

                              <h3 className="font-serif text-lg">
                                {copy.tkResemblance}
                              </h3>
                            </div>

                            <p className="text-xs text-ink/50 mb-3 max-w-[70ch]">
                              {copy.tkResemblanceNote}
                            </p>

                            <div className="space-y-2">
                              {result.tk_similarity.map((m) => (
                                <div
                                  key={m.name}
                                  className="lift-on-hover flex items-center justify-between gap-3 border border-hairline rounded-md px-3.5 py-2.5 bg-paper/50"
                                >
                                  <div className="min-w-0">
                                    <p className="text-sm font-semibold text-ink/85">
                                      {m.name}
                                    </p>

                                    <p className="text-xs text-ink/55 truncate">
                                      {m.description}
                                    </p>
                                  </div>

                                  <span className="citation-marker shrink-0 text-xs font-semibold text-earth bg-earth/10 border border-earth/20 px-2 py-1 rounded-md">
                                    {Math.round(
                                      m.similarity * 100
                                    )}
                                    %
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                      <div className="flex justify-end">
                        <button
                          onClick={() =>
                            api.downloadPosturePdf({
                              query,
                              result,
                            })
                          }
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

          {showEscalate && result && (
            <EscalationModal
              copy={copy}
              context={{
                query,
                category: result.classification?.category,
                jurisdiction: result.jurisdiction,
                areas: result.applicable_areas,
                sourceIds: (result.sources || []).map(
                  (s) => s.id
                ),
              }}
              onClose={() => setShowEscalate(false)}
            />
          )}
          </main>
          </div>{/* end flex body */}

          <footer className="border-t border-hairline py-7 text-center">
            <ManuscriptRule className="text-gold max-w-[220px] mx-auto mb-3" />

            <p className="citation-marker text-[11px] text-ink/40">
              {copy.appName} · {copy.team} · SIH26045
            </p>
          </footer>
      </div>
    </>
  )
}
