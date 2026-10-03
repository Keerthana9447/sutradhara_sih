import { useState, useEffect } from "react"
import { FileCheck2, Plus, CheckCircle2, Link2, AlertTriangle, Clock, RefreshCw } from "lucide-react"
import useTranslatedStrings from '../hooks/useTranslatedStrings'

const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "")

function authHeaders() {
  try {
    const raw = localStorage.getItem("sutradhara_auth")
    const token = raw ? JSON.parse(raw).token : null
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch { return {} }
}

async function apiPost(path, body) {
  const res = await fetch(`${API_ORIGIN}/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json()
}

async function apiGet(path) {
  const res = await fetch(`${API_ORIGIN}/api/v1${path}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json()
}

const STATUS_COLORS = {
  "Pending": "border-gold/40 bg-gold-light/10 text-gold-dark",
  "Verified": "border-green/40 bg-green-pale text-green",
  "Blockchain Anchored": "border-ink/20 bg-ink/5 text-ink/70",
}

const STATUS_ICONS = {
  "Pending": Clock,
  "Verified": CheckCircle2,
  "Blockchain Anchored": Link2,
}

function ClaimCard({ claim, index, t }) {
  const Icon = STATUS_ICONS[claim.status] || Clock
  return (
    <div className="lift-on-hover dossier-panel p-4 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="min-w-0">
          <p className="font-semibold text-sm text-ink/90 truncate">{t(`claimTitle${index}`)}</p>
          <p className="text-xs text-ink/50 mt-0.5">{claim.claim_id} � {claim.jurisdiction}</p>
        </div>
        <span className={`citation-marker shrink-0 inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full border ${STATUS_COLORS[claim.status] || "border-hairline"}`}>
          <Icon size={11} />
          {t(`status${claim.status.replaceAll(' ', '')}`)}
        </span>
      </div>
      <p className="text-sm text-ink/65 line-clamp-2">{t(`claimDescription${index}`)}</p>
      {claim.anchor_hash && (
        <div className="mt-1 p-2 rounded-md bg-ink/5 border border-hairline">
          <p className="text-[10px] text-ink/50 font-mono break-all">{claim.anchor_hash}</p>
          <p className="text-[10px] text-ink/40 mt-0.5 italic">{t(`claimAnchorNote${index}`)}</p>
        </div>
      )}
      <p className="text-[10px] text-ink/35 mt-1">
        {t('submitted')} {new Date(claim.submitted_at).toLocaleString()}
        {claim.verified_at && ` · ${t('verified')} ${new Date(claim.verified_at).toLocaleString()}`}
      </p>
    </div>
  )
}

export default function ClaimsWorkflow({ copy, language = 'en' }) {
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: "", description: "", jurisdiction: "India", category: "" })
  const translationSource = {
    heading: 'Citizen Claims',
    intro: 'Submit your TK formulation for tracking. Claims follow the lifecycle:',
    statusPending: 'Pending',
    statusVerified: 'Verified',
    statusBlockchainAnchored: 'Blockchain Anchored',
    newClaim: 'New Claim',
    loadError: 'Could not load claims.',
    submitError: 'Submission failed. Please try again.',
    submitHeading: 'Submit a New Claim',
    titleLabel: 'Title *',
    titlePlaceholder: 'e.g. Turmeric-Pepper Anti-inflammatory Formulation',
    descriptionLabel: 'Description *',
    descriptionPlaceholder: 'Describe the formulation, ingredients, method, and traditional usage...',
    jurisdiction: 'Jurisdiction',
    category: 'Category',
    categoryPlaceholder: 'e.g. Classical Medicine',
    international: 'International',
    cancel: 'Cancel',
    submitting: 'Submitting…',
    submit: 'Submit Claim',
    loading: 'Loading claims…',
    noClaims: 'No claims yet. Submit your first claim to get started.',
    disclaimer: 'Claims are recorded for tracking purposes only. They do not constitute filed applications or create legal rights. The blockchain anchor is a simulated SHA-256 commitment, not an actual on-chain transaction.',
    submitted: 'Submitted',
    verified: 'Verified',
    success: 'Claim submitted successfully!',
    translationUnavailable: 'Some text could not be translated and is shown in English.',
    ...Object.fromEntries(claims.flatMap((claim, index) => [
      [`claimTitle${index}`, claim.title],
      [`claimDescription${index}`, claim.description],
      [`claimAnchorNote${index}`, claim.anchor_note || ''],
    ])),
  }
  const { text: t, available: translationAvailable, pending: translationPending } =
    useTranslatedStrings(language, translationSource)

  const loadClaims = async () => {
    setLoading(true)
    try {
      const data = await apiGet("/claims")
      setClaims(Array.isArray(data) ? data : [])
    } catch (e) {
      setError("Could not load claims.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadClaims() }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.title.trim() || !form.description.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const claim = await apiPost("/claims", form)
      setSuccess(`${claim.claim_id} ${t('success')}`)
      setShowForm(false)
      setForm({ title: "", description: "", jurisdiction: "India", category: "" })
      loadClaims()
    } catch {
      setError("Submission failed. Please try again.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-green">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-start gap-3">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-green-pale text-green shrink-0">
              <FileCheck2 size={20} />
            </span>
            <div>
              <h2 className="font-serif text-xl text-green-dark">{t('heading')}</h2>
              <p className="text-sm text-ink/60 mt-1 max-w-[65ch]">
                {t('intro')}
                <strong className="mx-1 text-gold-dark">{t('statusPending')}</strong>?
                <strong className="mx-1 text-green">{t('statusVerified')}</strong>?
                <strong className="mx-1 text-ink/70">{t('statusBlockchainAnchored')}</strong>
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={loadClaims} className="press p-2 rounded-md border border-hairline text-ink/50 hover:text-ink hover:border-ink/30">
              <RefreshCw size={15} />
            </button>
            <button
              onClick={() => setShowForm(s => !s)}
              className="press inline-flex items-center gap-1.5 px-4 py-2 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark"
            >
              <Plus size={15} /> {t('newClaim')}
            </button>
          </div>
        </div>
      </div>

      {success && (
        <div className="dossier-panel p-3.5 border-green/40 bg-green-pale flex items-center gap-2.5">
          <CheckCircle2 size={16} className="text-green shrink-0" />
          <p className="text-sm text-green">{success}</p>
        </div>
      )}

      {!translationAvailable && !translationPending && language !== 'en' && <p role="status" className="text-xs text-earth">{t('translationUnavailable')}</p>}

      {error && (
        <div className="dossier-panel p-3.5 border-rust/40 bg-rust/5 flex items-start gap-2.5">
          <AlertTriangle size={16} className="text-rust shrink-0 mt-0.5" />
          <p className="text-sm text-rust">{error === 'Could not load claims.' ? t('loadError') : error === 'Submission failed. Please try again.' ? t('submitError') : error}</p>
        </div>
      )}

      {/* Submit form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="dossier-panel p-5 space-y-4 animate-in">
          <h3 className="font-serif text-base text-green-dark">{t('submitHeading')}</h3>
          <div>
            <label className="block text-xs font-semibold text-ink/60 mb-1.5">{t('titleLabel')}</label>
            <input
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              placeholder={t('titlePlaceholder')}
              className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink/60 mb-1.5">{t('descriptionLabel')}</label>
            <textarea
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder={t('descriptionPlaceholder')}
              rows={4}
              className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm"
              required
            />
          </div>
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-32">
              <label className="block text-xs font-semibold text-ink/60 mb-1.5">{t('jurisdiction')}</label>
              <select value={form.jurisdiction} onChange={e => setForm(f => ({ ...f, jurisdiction: e.target.value }))}
                className="research-input w-full border border-hairline rounded-md px-3 py-2.5 text-sm">
                <option value="India">India</option>
                <option value="International">{t('international')}</option>
              </select>
            </div>
            <div className="flex-1 min-w-32">
              <label className="block text-xs font-semibold text-ink/60 mb-1.5">{t('category')}</label>
              <input value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                placeholder={t('categoryPlaceholder')}
                className="research-input w-full border border-hairline rounded-md px-3 py-2.5 text-sm" />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setShowForm(false)}
              className="press px-4 py-2 text-sm border border-hairline rounded-md text-ink/60 hover:text-ink">
              {t('cancel')}
            </button>
            <button type="submit" disabled={submitting}
              className="press px-4 py-2 text-sm bg-green text-paper font-semibold rounded-md hover:bg-green-dark disabled:opacity-50">
              {submitting ? t('submitting') : t('submit')}
            </button>
          </div>
        </form>
      )}

      {/* Claims list */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-ink/40 gap-3">
          <svg className="animate-spin w-5 h-5 text-green" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm">{t('loading')}</span>
        </div>
      ) : claims.length === 0 ? (
        <div className="dossier-panel p-10 text-center text-ink/40">
          <FileCheck2 size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{t('noClaims')}</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {claims.map((claim, index) => <ClaimCard key={claim.claim_id} claim={claim} index={index} t={t} />)}
        </div>
      )}

      <div className="dossier-panel p-4 border-rust/20 bg-rust/5">
        <p className="text-xs text-ink/50 italic">
          {t('disclaimer')}
        </p>
      </div>
    </div>
  )
}
