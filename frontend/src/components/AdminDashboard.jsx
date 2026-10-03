import { useState, useEffect } from "react"
import { Shield, Radar, CheckCircle2, Link2, Clock, AlertTriangle, RefreshCw, Search } from "lucide-react"

const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "")

function authHeaders() {
  try {
    const raw = localStorage.getItem("sutradhara_auth")
    const token = raw ? JSON.parse(raw).token : null
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch { return {} }
}

async function apiPost(path, body) {
  const res = await fetch(`${API_ORIGIN}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `${path} failed`) }
  return res.json()
}

async function apiGet(path) {
  const res = await fetch(`${API_ORIGIN}${path}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`${path} failed`)
  return res.json()
}

// -- Radar Panel -------------------------------------------------------------
function RadarPanel() {
  const [form, setForm] = useState({ patent_title: "", patent_abstract: "", patent_claims: "", filing_office: "USPTO" })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function run() {
    if (!form.patent_title || !form.patent_abstract) return
    setLoading(true); setError(null)
    try { setResult(await apiPost("/api/v1/radar", form)) }
    catch (e) { setError(e.message) }
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
          placeholder="Patent title *"
          className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm" />
        <textarea value={form.patent_abstract} onChange={e => setForm(f => ({...f, patent_abstract: e.target.value}))}
          placeholder="Patent abstract *"
          rows={3} className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm" />
        <textarea value={form.patent_claims} onChange={e => setForm(f => ({...f, patent_claims: e.target.value}))}
          placeholder="Claims (optional)"
          rows={2} className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm" />
        <div className="flex gap-2 items-center">
          <select value={form.filing_office} onChange={e => setForm(f => ({...f, filing_office: e.target.value}))}
            className="research-input border border-hairline rounded-md px-3 py-2 text-sm">
            <option>USPTO</option><option>EPO</option><option>IPO</option><option>WIPO</option>
          </select>
          <button onClick={run} disabled={loading || !form.patent_title || !form.patent_abstract}
            className="press flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark disabled:opacity-50">
            {loading ? "Scanning…" : <><Radar size={14} /> Run Radar Scan</>}
          </button>
        </div>
      </div>
      {error && <p className="text-sm text-rust">{error}</p>}
      {result && (
        <div className="space-y-3 animate-in">
          <div className={`dossier-panel p-4 border ${riskColor[result.overall_risk] || "border-hairline"}`}>
            <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
              <p className="font-semibold text-sm">{result.patent_title}</p>
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${riskColor[result.overall_risk] || ""}`}>
                {result.overall_risk} Risk
              </span>
            </div>
            <p className="text-sm text-ink/70">{result.ministry_action_summary}</p>
            <p className="text-xs text-ink/40 mt-2">{result.total_matches} TKDL matches • {result.high_risk_matches} high risk • {result.medium_risk_matches} medium risk</p>
          </div>
          {result.matches.map((m, i) => (
            <div key={i} className="border border-hairline rounded-md p-3.5 bg-paper/60">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <p className="text-sm font-semibold">{m.tkdl_entry}</p>
                <span className={`text-[11px] px-2 py-0.5 rounded-full border ${
                  m.risk_level === "High" ? "border-rust/30 bg-rust/10 text-rust" :
                  m.risk_level === "Medium" ? "border-gold/30 bg-gold-light/10 text-gold-dark" :
                  "border-green/30 bg-green-pale text-green"
                }`}>{m.risk_level}</span>
              </div>
              <p className="text-xs text-ink/55 mt-1">{m.system} · score: {m.score}</p>
              <p className="text-xs text-ink/60 mt-1.5 italic">{m.recommended_action}</p>
              {m.matched_terms.length > 0 && (
                <div className="flex gap-1.5 flex-wrap mt-2">
                  {m.matched_terms.map((t, j) => <span key={j} className="text-[10px] border border-hairline rounded-full px-2 py-0.5">{t}</span>)}
                </div>
              )}
            </div>
          ))}
          <p className="text-[11px] text-ink/40 italic">{result.disclaimer}</p>
        </div>
      )}
    </div>
  )
}

// -- Claims Queue Panel -------------------------------------------------------
function ClaimsQueue() {
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState("Pending")
  const [busy, setBusy] = useState({})

  async function loadClaims() {
    setLoading(true)
    try { setClaims(await apiGet(`/api/v1/claims?status=${filter}&limit=50`)) }
    catch { setClaims([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { loadClaims() }, [filter])

  async function doAction(id, action) {
    setBusy(b => ({...b, [id]: true}))
    try {
      await apiPost(`/api/v1/claims/${id}/${action}`, {})
      loadClaims()
    } catch (e) { alert(e.message) }
    finally { setBusy(b => ({...b, [id]: false})) }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        {["Pending", "Verified", "Blockchain Anchored"].map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`press text-xs px-3 py-1.5 rounded-md border ${filter === s ? "bg-green text-paper border-green" : "border-hairline text-ink/60 hover:border-green/40"}`}>
            {s}
          </button>
        ))}
        <button onClick={loadClaims} className="press ml-auto p-1.5 border border-hairline rounded-md text-ink/50">
          <RefreshCw size={13} />
        </button>
      </div>
      {loading ? <p className="text-sm text-ink/40 py-6 text-center">Loading…</p> :
        claims.length === 0 ? <p className="text-sm text-ink/40 py-6 text-center">No {filter} claims.</p> :
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
                    {busy[claim.claim_id] ? "…" : "Verify"}
                  </button>
                )}
                {claim.status === "Verified" && (
                  <button disabled={busy[claim.claim_id]} onClick={() => doAction(claim.claim_id, "anchor")}
                    className="press text-xs px-3 py-1.5 bg-ink/80 text-paper rounded-md hover:bg-ink disabled:opacity-50">
                    {busy[claim.claim_id] ? "…" : "Anchor"}
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
  { id: "radar", label: "Patent Radar", icon: Radar },
  { id: "claims", label: "Claims Queue", icon: CheckCircle2 },
]

export default function AdminDashboard({ user }) {
  const [tab, setTab] = useState("radar")

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-rust">
        <div className="flex items-start gap-3">
          <span className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-rust/10 text-rust shrink-0">
            <Shield size={20} />
          </span>
          <div>
            <h2 className="font-serif text-xl text-green-dark">Ministry Admin Dashboard</h2>
            <p className="text-sm text-ink/60 mt-1">
              Bio-piracy radar · Citizen claims queue
            </p>
            <span className="inline-flex items-center gap-1.5 mt-2 text-[11px] border border-rust/30 bg-rust/5 text-rust px-2.5 py-1 rounded-full">
              <Shield size={11} /> Admin — {user?.name}
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
              <Icon size={14} /> {t.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div key={tab} className="view-enter">
        {tab === "radar" && <RadarPanel />}
        {tab === "claims" && <ClaimsQueue />}
      </div>
    </div>
  )
}
