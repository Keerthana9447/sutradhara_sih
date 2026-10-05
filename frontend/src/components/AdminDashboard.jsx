import { useState, useEffect } from "react"
import { Shield, Radar, CheckCircle2, RefreshCw } from "lucide-react"
import { getAdminCopy } from "../adminCopy"
import useTranslatedStrings from "../hooks/useTranslatedStrings"
import { api } from "../api"

const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "")

function authHeaders() {
  try {
    const raw = localStorage.getItem("sutradhara_auth")
    const token = raw ? JSON.parse(raw).token : null
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch { return {} }
}

function requestError(status, copy) {
  if (status === 401) return copy.unauthorized
  if (status === 403) return copy.adminRequired
  if (status === 429) return copy.tooManyRequests
  return copy.requestFailed
}

async function apiPost(path, body, copy) {
  let res
  try {
    res = await fetch(`${API_ORIGIN}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error(copy.requestFailed)
  }
  if (!res.ok) throw new Error(requestError(res.status, copy))
  return res.json()
}

async function apiGet(path, copy) {
  let res
  try {
    res = await fetch(`${API_ORIGIN}${path}`, { headers: authHeaders() })
  } catch {
    throw new Error(copy.claimsLoadFailed)
  }
  if (!res.ok) throw new Error(requestError(res.status, copy))
  return res.json()
}

// -- Radar Panel -------------------------------------------------------------
function RadarPanel({ copy, language, externalProcessingConsent, onExternalProcessingConsentChange }) {
  const [form, setForm] = useState({ patent_title: "", patent_abstract: "", patent_claims: "", filing_office: "USPTO" })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const resultTranslationSource = result ? {
    ministryActionSummary: result.ministry_action_summary || "",
    ...Object.fromEntries((result.matches || []).flatMap((match, index) => [
      [`reference${index}`, match.reference_entry || ""],
      [`system${index}`, match.system || ""],
      [`recommendedAction${index}`, match.recommended_action || ""],
    ])),
  } : {}
  const {
    text: translatedResult,
    available: resultTranslationAvailable,
    pending: resultTranslationPending,
  } = useTranslatedStrings(
    language,
    resultTranslationSource,
    externalProcessingConsent,
  )

  async function run() {
    if (!form.patent_title || !form.patent_abstract) return
    setLoading(true); setError(null)
    try {
      let request = { ...form }
      if (language !== "en" && externalProcessingConsent) {
        const fields = ["patent_title", "patent_abstract", "patent_claims"].filter(key => form[key])
        try {
          const response = await api.translateTexts(fields.map(key => form[key]), "en", true)
          if (response.results.length !== fields.length || response.results.some(item => !item.success)) {
            throw new Error(copy.inputTranslationFailed)
          }
          request = {
            ...form,
            ...Object.fromEntries(fields.map((key, index) => [key, response.results[index].translated])),
          }
        } catch {
          throw new Error(copy.inputTranslationFailed)
        }
      }
      const radarResult = await apiPost("/api/v1/radar", request, copy)
      setResult({ ...radarResult, patent_title: form.patent_title })
    }
    catch (e) { setError(e.message || copy.requestFailed) }
    finally { setLoading(false) }
  }

  const riskColor = {
    Critical: "text-rust border-rust/40 bg-rust/10",
    High: "text-rust border-rust/30 bg-rust/5",
    Medium: "text-gold-dark border-gold/30 bg-gold-light/10",
    Low: "text-green border-green/30 bg-green-pale",
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <input value={form.patent_title} onChange={e => setForm(f => ({...f, patent_title: e.target.value}))}
          placeholder={copy.patentTitlePlaceholder}
          className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm" />
        <textarea value={form.patent_abstract} onChange={e => setForm(f => ({...f, patent_abstract: e.target.value}))}
          placeholder={copy.patentAbstractPlaceholder}
          rows={3} className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm" />
        <textarea value={form.patent_claims} onChange={e => setForm(f => ({...f, patent_claims: e.target.value}))}
          placeholder={copy.claimsPlaceholder}
          rows={2} className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm" />
        <div className="flex gap-2 items-center">
          <select value={form.filing_office} onChange={e => setForm(f => ({...f, filing_office: e.target.value}))}
            className="research-input border border-hairline rounded-md px-3 py-2 text-sm">
            <option>USPTO</option><option>EPO</option><option>IPO</option><option>WIPO</option>
          </select>
          <button onClick={run} disabled={loading || !form.patent_title || !form.patent_abstract}
            className="press flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark disabled:opacity-50">
            {loading ? copy.scanning : <><Radar size={14} /> {copy.runRadar}</>}
          </button>
        </div>
        {language !== "en" && (
          <div className="space-y-2">
            <label className="flex items-start gap-2 text-xs text-ink/60">
              <input
                type="checkbox"
                checked={externalProcessingConsent}
                onChange={event => onExternalProcessingConsentChange(event.target.checked)}
                className="mt-0.5"
              />
              <span>{copy.translationConsent}</span>
            </label>
            {!externalProcessingConsent && (
              <p className="text-xs text-ink/50">{copy.inputTranslationNotice}</p>
            )}
          </div>
        )}
      </div>
      {error && <p className="text-sm text-rust">{error}</p>}
      {result && (
        <div className="space-y-3 animate-in">
          <div className={`dossier-panel p-4 border ${riskColor[result.overall_risk] || "border-hairline"}`}>
            <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
              <p className="font-semibold text-sm">{result.patent_title}</p>
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${riskColor[result.overall_risk] || ""}`}>
                {copy[result.overall_risk?.toLowerCase()] || result.overall_risk} {copy.risk}
              </span>
            </div>
            <p className="text-sm text-ink/70">{translatedResult("ministryActionSummary")}</p>
            <p className="text-xs text-ink/40 mt-2">
              {copy.matchesSummary
                .replace("{total}", result.total_matches)
                .replace("{high}", result.high_risk_matches)
                .replace("{medium}", result.medium_risk_matches)}
            </p>
          </div>
          {result.matches.map((m, i) => (
            <div key={i} className="border border-hairline rounded-md p-3.5 bg-paper/60">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <p className="text-sm font-semibold">{translatedResult(`reference${i}`)}</p>
                <span className={`text-[11px] px-2 py-0.5 rounded-full border ${
                  m.risk_level === "High" ? "border-rust/30 bg-rust/10 text-rust" :
                  m.risk_level === "Medium" ? "border-gold/30 bg-gold-light/10 text-gold-dark" :
                  "border-green/30 bg-green-pale text-green"
                }`}>{copy[m.risk_level?.toLowerCase()] || m.risk_level}</span>
              </div>
              <p className="text-xs text-ink/55 mt-1">{copy.system}: {translatedResult(`system${i}`)} · {copy.score}: {m.score}</p>
              <p className="text-xs text-ink/60 mt-1.5 italic">{translatedResult(`recommendedAction${i}`)}</p>
              {m.matched_terms.length > 0 && (
                <div className="flex gap-1.5 flex-wrap mt-2">
                  {m.matched_terms.map((t, j) => <span key={j} className="text-[10px] border border-hairline rounded-full px-2 py-0.5">{t}</span>)}
                </div>
              )}
            </div>
          ))}
          <p className="text-[11px] text-ink/40 italic">{copy.radarDisclaimer}</p>
          {language !== "en" && !resultTranslationPending && !resultTranslationAvailable && (
            <p className="text-xs text-ink/50">
              {externalProcessingConsent ? copy.translationUnavailable : copy.dynamicTranslationNotice}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// -- Claims Queue Panel -------------------------------------------------------
function ClaimsQueue({ copy }) {
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState("Pending")
  const [busy, setBusy] = useState({})
  const [error, setError] = useState(null)

  async function loadClaims() {
    setLoading(true)
    setError(null)
    try { setClaims(await apiGet(`/api/v1/claims?status=${filter}&limit=50`, copy)) }
    catch (e) { setClaims([]); setError(e.message || copy.claimsLoadFailed) }
    finally { setLoading(false) }
  }

  useEffect(() => { loadClaims() }, [filter])

  async function doAction(id, action) {
    setBusy(b => ({...b, [id]: true}))
    try {
      await apiPost(`/api/v1/claims/${id}/${action}`, {}, copy)
      loadClaims()
    } catch (e) { alert(e.message || copy.requestFailed) }
    finally { setBusy(b => ({...b, [id]: false})) }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        {[["Pending", copy.pending], ["Verified", copy.verified], ["Blockchain Anchored", copy.anchored]].map(([s, label]) => (
          <button key={s} onClick={() => setFilter(s)}
            className={`press text-xs px-3 py-1.5 rounded-md border ${filter === s ? "bg-green text-paper border-green" : "border-hairline text-ink/60 hover:border-green/40"}`}>
            {label}
          </button>
        ))}
        <button onClick={loadClaims} aria-label={copy.refreshClaims} title={copy.refreshClaims} className="press ml-auto p-1.5 border border-hairline rounded-md text-ink/50">
          <RefreshCw size={13} />
        </button>
      </div>
      {error && <p role="alert" className="text-sm text-rust">{error}</p>}
      {loading ? <p className="text-sm text-ink/40 py-6 text-center">{copy.loading}</p> :
        error ? null :
        claims.length === 0 ? <p className="text-sm text-ink/40 py-6 text-center">{copy.noClaims.replace("{status}", filter === "Pending" ? copy.pending : filter === "Verified" ? copy.verified : copy.anchored)}</p> :
        claims.map(claim => (
          <div key={claim.claim_id} className="dossier-panel p-4 flex flex-col gap-2">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div>
                <p className="text-sm font-semibold">{claim.title}</p>
                <p className="text-xs text-ink/40">{claim.claim_id} · {claim.jurisdiction}</p>
              </div>
              <div className="flex gap-2">
                {claim.status === "Pending" && (
                  <button disabled={busy[claim.claim_id]} onClick={() => doAction(claim.claim_id, "verify")}
                    className="press text-xs px-3 py-1.5 bg-green text-paper rounded-md hover:bg-green-dark disabled:opacity-50">
                    {busy[claim.claim_id] ? "…" : copy.verify}
                  </button>
                )}
                {claim.status === "Verified" && (
                  <button disabled={busy[claim.claim_id]} onClick={() => doAction(claim.claim_id, "anchor")}
                    className="press text-xs px-3 py-1.5 bg-ink/80 text-paper rounded-md hover:bg-ink disabled:opacity-50">
                    {busy[claim.claim_id] ? "…" : copy.anchor}
                  </button>
                )}
              </div>
            </div>
            <p className="text-sm text-ink/60 line-clamp-2">{claim.description}</p>
          </div>
        ))}
    </div>
  )
}

// -- Main Admin Dashboard -----------------------------------------------------
const ADMIN_TABS = [
  { id: "radar", label: "patentRadar", icon: Radar },
  { id: "claims", label: "claimsQueue", icon: CheckCircle2 },
]

export default function AdminDashboard({
  user,
  language = "en",
  externalProcessingConsent = false,
  onExternalProcessingConsentChange,
}) {
  const [tab, setTab] = useState("radar")
  const copy = getAdminCopy(language)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-rust">
        <div className="flex items-start gap-3">
          <span className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-rust/10 text-rust shrink-0">
            <Shield size={20} />
          </span>
          <div>
            <h2 className="font-serif text-xl text-green-dark">{copy.dashboardTitle}</h2>
            <p className="text-sm text-ink/60 mt-1">
              {copy.dashboardSubtitle}
            </p>
            <span className="inline-flex items-center gap-1.5 mt-2 text-[11px] border border-rust/30 bg-rust/5 text-rust px-2.5 py-1 rounded-full">
              <Shield size={11} /> {copy.adminBadge} — {user?.name}
            </span>
          </div>
        </div>
      </div>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-hairline overflow-x-auto">
        {ADMIN_TABS.map(t => {
          const Icon = t.icon
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`press inline-flex items-center gap-1.5 px-4 py-2.5 text-sm border-b-2 whitespace-nowrap ${
                tab === t.id ? "border-rust text-rust" : "border-transparent text-ink/50 hover:text-ink"
              }`}>
              <Icon size={14} /> {copy[t.label]}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div key={tab} className="view-enter">
        {tab === "radar" && <RadarPanel
          copy={copy}
          language={language}
          externalProcessingConsent={externalProcessingConsent}
          onExternalProcessingConsentChange={onExternalProcessingConsentChange}
        />}
        {tab === "claims" && <ClaimsQueue copy={copy} />}
      </div>
    </div>
  )
}
