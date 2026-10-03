import { useEffect, useState } from 'react'
import { AlertTriangle, ExternalLink, Eye, Loader2, Plus, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react'
import { api } from '../api'
import useTranslatedStrings from '../hooks/useTranslatedStrings'

const BAND_STYLE = {
  red: 'border-rust/40 bg-rust/10 text-rust',
  amber: 'border-gold/40 bg-gold-light/15 text-gold-dark',
  green: 'border-green/40 bg-green-pale text-green',
  grey: 'border-ink/20 bg-ink/5 text-ink/55',
}

const EMPTY_FORM = {
  filing_number: '',
  title: '',
  abstract: '',
  publication_date: '',
  stream: 'domestic',
  source_url: '',
}

export default function PrahariWatchlist({ language = 'en', externalProcessingConsent = false }) {
  const [alerts, setAlerts] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState('')
  const [error, setError] = useState('')

  const copySource = {
    title: 'Prahari · Patent Watch',
    intro: 'Track published competitor patent filings in domestic and foreign streams. Deadlines and resemblance scores update as time passes.',
    add: 'Add filing',
    refresh: 'Refresh watchlist',
    filingNumber: 'Publication or filing number',
    titleLabel: 'Patent title',
    abstract: 'Abstract or claims summary',
    published: 'Publication date',
    stream: 'Filing stream',
    domestic: 'Domestic (India)',
    foreign: 'Foreign',
    sourceUrl: 'Official filing or source URL (optional)',
    save: 'Add to watchlist',
    cancel: 'Cancel',
    loading: 'Loading watchlist…',
    empty: 'No filings in your watchlist yet. Add a published filing to monitor its date and prior-art resemblance.',
    loadError: 'Could not load the Prahari watchlist.',
    actionError: 'Could not update the watchlist.',
    filingAdded: 'Filing added to your watchlist.',
    filing: 'Filing',
    publication: 'Publication',
    target: 'Six-month monitoring target',
    daysLeft: 'days remaining',
    targetPassed: 'monitoring target passed',
    urgency: 'Urgency',
    risk: 'Prior-art resemblance risk',
    references: 'Closest public reference signals',
    noMatches: 'No match above the minimum similarity threshold in the small illustrative reference set.',
    source: 'View source',
    delete: 'Remove filing',
    red: 'Urgent',
    amber: 'Approaching',
    green: 'Monitoring',
    grey: 'Target passed',
    ruleNote: 'Legal timing notice: the six-month date is an internal monitoring target, not a statutory deadline. India Patent Rules, Rule 55(1A), allows a pre-grant representation after publication and before grant; it does not prescribe a fixed six-month period. Verify grant status and obtain legal advice.',
    ruleSource: 'Official Indian Patent Rules (PDF)',
    riskNote: 'Heuristic text resemblance against a small public illustrative reference set; not an official TKDL search, infringement finding, or legal conclusion.',
    collectionNote: 'Watchlist entries are saved from information you enter. This prototype does not automatically poll patent registries; use the official source link to verify current status.',
    translationUnavailable: 'Some labels could not be translated; English is shown.',
  }
  const { text: t, available, pending } = useTranslatedStrings(language, copySource, externalProcessingConsent)

  async function loadAlerts() {
    setLoading(true)
    setError('')
    try {
      setAlerts(await api.listPrahariAlerts())
    } catch {
      setError(t('loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadAlerts() }, [])

  async function addAlert(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.createPrahariAlert({
        ...form,
        filing_number: form.filing_number.trim(),
        title: form.title.trim(),
        abstract: form.abstract.trim(),
        source_url: form.source_url.trim() || null,
      })
      setForm(EMPTY_FORM)
      setShowForm(false)
      await loadAlerts()
    } catch (failure) {
      setError(failure?.message || t('actionError'))
    } finally {
      setSaving(false)
    }
  }

  async function removeAlert(alertId) {
    if (!window.confirm('Remove this filing from your Prahari watchlist?')) return
    setBusyId(alertId)
    setError('')
    try {
      await api.deletePrahariAlert(alertId)
      setAlerts((items) => items.filter((item) => item.alert_id !== alertId))
    } catch (failure) {
      setError(failure?.message || t('actionError'))
    } finally {
      setBusyId('')
    }
  }

  return (
    <div className="space-y-6">
      <section className="dossier-panel p-5 sm:p-6 border-l-4 border-l-gold">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-gold-light/20 text-gold-dark shrink-0"><ShieldAlert size={20} /></span>
            <div>
              <h2 className="font-serif text-xl text-green-dark">{t('title')}</h2>
              <p className="text-sm text-ink/60 mt-1 max-w-[70ch]">{t('intro')}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button type="button" aria-label={t('refresh')} onClick={loadAlerts} className="press p-2 rounded-md border border-hairline text-ink/50 hover:text-ink"><RefreshCw size={15} /></button>
            <button type="button" onClick={() => setShowForm((value) => !value)} className="press inline-flex items-center gap-1.5 px-4 py-2 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark"><Plus size={15} />{t('add')}</button>
          </div>
        </div>
      </section>

      {!available && !pending && language !== 'en' && <p role="status" className="text-xs text-earth">{t('translationUnavailable')}</p>}
      {error && <div role="alert" className="dossier-panel p-3 border-rust/40 bg-rust/5 text-sm text-rust flex gap-2"><AlertTriangle size={16} />{error}</div>}

      {showForm && (
        <form onSubmit={addAlert} className="dossier-panel p-5 space-y-3">
          <label className="block text-xs text-ink/60">{t('filingNumber')} *
            <input required maxLength={100} value={form.filing_number} onChange={(event) => setForm({ ...form, filing_number: event.target.value })} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs text-ink/60">{t('titleLabel')} *
            <input required maxLength={500} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs text-ink/60">{t('abstract')} *
            <textarea required maxLength={12000} rows={4} value={form.abstract} onChange={(event) => setForm({ ...form, abstract: event.target.value })} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
          </label>
          <div className="grid sm:grid-cols-2 gap-3">
            <label className="block text-xs text-ink/60">{t('published')} *
              <input required type="date" max={new Date().toISOString().slice(0, 10)} value={form.publication_date} onChange={(event) => setForm({ ...form, publication_date: event.target.value })} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
            </label>
            <label className="block text-xs text-ink/60">{t('stream')}
              <select value={form.stream} onChange={(event) => setForm({ ...form, stream: event.target.value })} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm bg-paper">
                <option value="domestic">{t('domestic')}</option><option value="foreign">{t('foreign')}</option>
              </select>
            </label>
          </div>
          <label className="block text-xs text-ink/60">{t('sourceUrl')}
            <input type="url" maxLength={2000} value={form.source_url} onChange={(event) => setForm({ ...form, source_url: event.target.value })} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
          </label>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-3 py-2 border border-hairline rounded-md text-sm">{t('cancel')}</button>
            <button disabled={saving} className="press px-4 py-2 bg-green text-paper rounded-md text-sm font-semibold disabled:opacity-50">{saving ? <Loader2 size={15} className="animate-spin" /> : t('save')}</button>
          </div>
        </form>
      )}

      <p className="text-xs text-ink/50">{t('collectionNote')}</p>
      {loading ? <div className="py-10 text-center text-sm text-ink/50">{t('loading')}</div> : alerts.length === 0 ? (
        <div className="dossier-panel p-8 text-center text-sm text-ink/55">{t('empty')}</div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-4">
          {alerts.map((alert) => (
            <article key={alert.alert_id} className="dossier-panel p-5 space-y-4">
              <header className="flex justify-between items-start gap-3">
                <div>
                  <span className="citation-marker text-[10px] text-ink/45">{alert.stream === 'domestic' ? t('domestic') : t('foreign')} · {alert.filing_number}</span>
                  <h3 className="font-serif text-lg text-green-dark mt-1">{alert.title}</h3>
                  <p className="text-xs text-ink/50">{t('publication')}: {alert.publication_date}</p>
                </div>
                <button aria-label={t('delete')} title={t('delete')} onClick={() => removeAlert(alert.alert_id)} disabled={busyId === alert.alert_id} className="press p-2 rounded-md text-rust/70 hover:bg-rust/5">{busyId === alert.alert_id ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}</button>
              </header>
              <p className="text-sm text-ink/75 leading-relaxed">{alert.abstract}</p>

              <div className={`rounded-md border p-3 ${BAND_STYLE[alert.urgency_band]}`}>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <p className="text-xs font-semibold uppercase tracking-wide">{t('urgency')}: {t(alert.urgency_band)}</p>
                  <p className="text-xs font-semibold">{alert.days_remaining < 0 ? `${Math.abs(alert.days_remaining)} ${t('targetPassed')}` : `${alert.days_remaining} ${t('daysLeft')}`}</p>
                </div>
                <p className="text-sm mt-1">{t('target')}: <strong>{alert.monitoring_target_date}</strong></p>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1"><span className="font-semibold">{t('risk')}</span><strong>{alert.risk_score}/100</strong></div>
                <div role="meter" aria-label={t('risk')} aria-valuemin="0" aria-valuemax="100" aria-valuenow={alert.risk_score} className="h-2 rounded-full bg-ink/10 overflow-hidden"><div className="h-full bg-earth" style={{ width: `${alert.risk_score}%` }} /></div>
                {alert.risk_matches.length > 0 ? (
                  <div className="mt-3"><p className="text-xs font-semibold text-ink/65">{t('references')}</p>{alert.risk_matches.map((match) => <div key={match.name} className="mt-1 flex items-center justify-between gap-2 text-xs"><span>{match.name}</span><span className="font-semibold">{Math.round(match.similarity * 100)}%</span></div>)}</div>
                ) : <p className="text-xs text-ink/50 mt-2">{t('noMatches')}</p>}
                <p className="text-[11px] text-ink/45 mt-2">{t('riskNote')}</p>
              </div>

              <div className="border-t border-hairline pt-3 space-y-2">
                <p className="text-xs text-ink/65 leading-relaxed">{t('ruleNote')}</p>
                <a href={alert.deadline_source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-green underline"><ExternalLink size={12} />{t('ruleSource')}</a>
                {alert.source_url && <a href={alert.source_url} target="_blank" rel="noreferrer" className="ml-4 inline-flex items-center gap-1 text-xs text-green underline"><Eye size={12} />{t('source')}</a>}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
