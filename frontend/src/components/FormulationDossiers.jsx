import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, ClipboardList, FolderOpen, Loader2, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { api } from '../api'
import useTranslatedStrings from '../hooks/useTranslatedStrings'

const CATEGORIES = [
  'Classical / Generic Medicine',
  'Patent / Proprietary Medicine',
  'New / Non-Classical Drug',
  'Phytopharmaceutical',
  'Ayurveda-Aahar / Nutraceutical',
  'Cosmetic',
]

const EMPTY_FORM = {
  name: '',
  ingredients: '',
  sourcing_type: '',
  indication: '',
  target_market: 'India',
}

const STATUS_CLASS = {
  draft: 'border-gold/40 bg-gold-light/10 text-gold-dark',
  classified: 'border-blue-300 bg-blue-50 text-blue-800',
  mapped: 'border-green/40 bg-green-pale text-green',
  under_review: 'border-earth/40 bg-earth/10 text-earth',
}

export default function FormulationDossiers({ language = 'en', externalProcessingConsent = false }) {
  const [dossiers, setDossiers] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const copySource = {
    title: 'Formulation Dossiers',
    intro: 'Keep a named, persistent record of each product, its ingredients, sourcing, intended use, and target market. Classification and evidence mapping are stored in the dossier history.',
    newDossier: 'New dossier',
    refresh: 'Refresh dossiers',
    name: 'Product or formulation name',
    ingredients: 'Ingredients (one per line or comma separated)',
    sourcing: 'Sourcing type',
    sourcingPlaceholder: 'e.g. cultivated, wild-harvested, purchased',
    indication: 'Claimed indication or intended use',
    market: 'Target market',
    india: 'India',
    international: 'International',
    both: 'Both',
    create: 'Save dossier',
    cancel: 'Cancel',
    empty: 'No formulation dossiers yet. Create one to start a persistent product record.',
    loading: 'Loading dossiers…',
    loadError: 'Could not load your dossiers.',
    saveError: 'Could not save the dossier.',
    actionError: 'The dossier action failed. Please retry.',
    created: 'Dossier saved.',
    classify: 'Classify',
    confirmCategory: 'Choose a category to confirm classification:',
    map: 'Map evidence',
    review: 'Start review',
    delete: 'Delete dossier',
    classification: 'Classification',
    evidence: 'Mapped evidence',
    areas: 'Applicable areas',
    noSources: 'No corpus sources matched this dossier. This is not a determination that no requirements apply.',
    source: 'Source',
    status: 'Status',
    history: 'Activity',
    draft: 'Draft',
    classified: 'Classified',
    mapped: 'Mapped',
    under_review: 'Under review',
    clarification: 'Please confirm the category before mapping evidence.',
    noClassification: 'Not classified yet.',
    targetDisclaimer: 'Evidence mapping is an informational aid, not legal advice. Verify the cited source and current requirements.',
    translationUnavailable: 'Some dossier labels could not be translated; English is shown.',
  }
  const { text: t, available, pending } = useTranslatedStrings(language, copySource, externalProcessingConsent)

  async function loadDossiers() {
    setLoading(true)
    setError('')
    try {
      setDossiers(await api.listDossiers())
    } catch {
      setError(t('loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadDossiers() }, [])

  async function createDossier(event) {
    event.preventDefault()
    const ingredients = form.ingredients.split(/[,\n]/).map((item) => item.trim()).filter(Boolean)
    if (!form.name.trim() || !ingredients.length || !form.sourcing_type.trim() || !form.indication.trim()) return
    setBusyId('create')
    setError('')
    try {
      await api.createDossier({ ...form, name: form.name.trim(), ingredients })
      setForm(EMPTY_FORM)
      setShowForm(false)
      setNotice(t('created'))
      await loadDossiers()
    } catch (failure) {
      setError(failure?.message || t('saveError'))
    } finally {
      setBusyId('')
    }
  }

  async function performAction(id, action, payload) {
    setBusyId(id)
    setError('')
    setNotice('')
    try {
      const updated = await action(id, payload)
      setDossiers((items) => items.map((item) => item.dossier_id === id ? updated : item))
    } catch (failure) {
      setError(failure?.message || t('actionError'))
    } finally {
      setBusyId('')
    }
  }

  async function removeDossier(id) {
    if (!window.confirm('Permanently delete this dossier and its activity history?')) return
    setBusyId(id)
    setError('')
    try {
      await api.deleteDossier(id)
      setDossiers((items) => items.filter((item) => item.dossier_id !== id))
    } catch (failure) {
      setError(failure?.message || t('actionError'))
    } finally {
      setBusyId('')
    }
  }

  return (
    <div className="space-y-6">
      <section className="dossier-panel p-5 sm:p-6 border-l-4 border-l-green">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-green-pale text-green shrink-0"><FolderOpen size={20} /></span>
            <div>
              <h2 className="font-serif text-xl text-green-dark">{t('title')}</h2>
              <p className="text-sm text-ink/60 mt-1 max-w-[70ch]">{t('intro')}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button type="button" aria-label={t('refresh')} onClick={loadDossiers} className="press p-2 rounded-md border border-hairline text-ink/50 hover:text-ink"><RefreshCw size={15} /></button>
            <button type="button" onClick={() => setShowForm((value) => !value)} className="press inline-flex items-center gap-1.5 px-4 py-2 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark"><Plus size={15} />{t('newDossier')}</button>
          </div>
        </div>
      </section>

      {!available && !pending && language !== 'en' && <p role="status" className="text-xs text-earth">{t('translationUnavailable')}</p>}
      {notice && <div role="status" className="dossier-panel p-3 border-green/40 bg-green-pale text-sm text-green">{notice}</div>}
      {error && <div role="alert" className="dossier-panel p-3 border-rust/40 bg-rust/5 text-sm text-rust flex gap-2"><AlertTriangle size={16} />{error}</div>}

      {showForm && (
        <form onSubmit={createDossier} className="dossier-panel p-5 space-y-3">
          <label className="block text-xs text-ink/60">{t('name')} *
            <input required maxLength={200} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs text-ink/60">{t('ingredients')} *
            <textarea required value={form.ingredients} onChange={(event) => setForm({ ...form, ingredients: event.target.value })} rows={3} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs text-ink/60">{t('sourcing')} *
            <input required maxLength={200} placeholder={t('sourcingPlaceholder')} value={form.sourcing_type} onChange={(event) => setForm({ ...form, sourcing_type: event.target.value })} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs text-ink/60">{t('indication')} *
            <textarea required maxLength={1000} value={form.indication} onChange={(event) => setForm({ ...form, indication: event.target.value })} rows={2} className="research-input mt-1 w-full border border-hairline rounded-md px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs text-ink/60">{t('market')}
            <select value={form.target_market} onChange={(event) => setForm({ ...form, target_market: event.target.value })} className="research-input mt-1 block border border-hairline rounded-md px-3 py-2 text-sm bg-paper">
              <option value="India">{t('india')}</option><option value="International">{t('international')}</option><option value="Both">{t('both')}</option>
            </select>
          </label>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-3 py-2 border border-hairline rounded-md text-sm">{t('cancel')}</button>
            <button disabled={busyId === 'create'} className="press px-4 py-2 bg-green text-paper rounded-md text-sm font-semibold disabled:opacity-50">{busyId === 'create' ? <Loader2 size={15} className="animate-spin" /> : t('create')}</button>
          </div>
        </form>
      )}

      {loading ? <div className="py-10 text-center text-sm text-ink/50">{t('loading')}</div> : dossiers.length === 0 ? (
        <div className="dossier-panel p-8 text-center text-sm text-ink/55">{t('empty')}</div>
      ) : (
        <div className="space-y-4">
          {dossiers.map((dossier) => {
            const classification = dossier.classification
            const clarificationNeeded = classification?.needs_clarification
            return (
              <article key={dossier.dossier_id} className="dossier-panel p-5 space-y-4">
                <header className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <h3 className="font-serif text-lg text-green-dark">{dossier.name}</h3>
                    <p className="text-xs text-ink/45">{dossier.dossier_id} · {dossier.target_market}</p>
                  </div>
                  <span className={`text-xs px-2.5 py-1 rounded-full border ${STATUS_CLASS[dossier.status]}`}>{t(dossier.status)}</span>
                </header>
                <div className="grid sm:grid-cols-2 gap-3 text-sm">
                  <div><span className="font-medium text-ink/65">{t('ingredients')}:</span> {dossier.ingredients.join(', ')}</div>
                  <div><span className="font-medium text-ink/65">{t('sourcing')}:</span> {dossier.sourcing_type}</div>
                  <div className="sm:col-span-2"><span className="font-medium text-ink/65">{t('indication')}:</span> {dossier.indication}</div>
                </div>

                {classification && (
                  <div className="rounded-md border border-hairline p-3">
                    <p className="section-kicker">{t('classification')}</p>
                    <p className="text-sm font-semibold mt-1">{classification.category}</p>
                    <p className="text-xs text-ink/55 mt-1">{classification.reason}</p>
                    {clarificationNeeded && <div className="mt-3"><p className="text-xs mb-2">{t('confirmCategory')}</p><div className="flex flex-wrap gap-2">{CATEGORIES.map((category) => <button key={category} disabled={busyId === dossier.dossier_id} onClick={() => performAction(dossier.dossier_id, api.classifyDossier, { confirmed_category: category })} className="text-xs border border-green/30 rounded px-2 py-1 text-green hover:bg-green-pale">{category}</button>)}</div></div>}
                  </div>
                )}

                {dossier.mapping && (
                  <div className="space-y-3">
                    <p className="section-kicker flex items-center gap-2"><ClipboardList size={14} />{t('evidence')}</p>
                    {Object.entries(dossier.mapping.jurisdictions || {}).map(([market, mapping]) => (
                      <div key={market} className="border border-hairline rounded-md p-3">
                        <p className="text-sm font-semibold">{market}</p>
                        <p className="text-xs text-ink/55 mt-1">{t('areas')}: {mapping.applicable_areas.join(', ')}</p>
                        {mapping.sources.length === 0 ? <p className="text-xs text-ink/55 mt-2">{t('noSources')}</p> : mapping.sources.map((source) => (
                          <div key={source.id} className="mt-2 border-t border-hairline pt-2 text-xs">
                            <p className="font-semibold">{source.title}</p>
                            <p className="text-ink/55">{source.authority} · {source.section} · {source.jurisdiction}</p>
                            {source.source_url && <a className="text-green underline" href={source.source_url} target="_blank" rel="noreferrer">{t('source')}</a>}
                          </div>
                        ))}
                      </div>
                    ))}
                    <p className="text-xs text-ink/45">{t('targetDisclaimer')}</p>
                  </div>
                )}

                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-hairline pt-3">
                  <div className="flex flex-wrap gap-2">
                    {dossier.status === 'draft' && <button disabled={busyId === dossier.dossier_id} onClick={() => performAction(dossier.dossier_id, api.classifyDossier)} className="press px-3 py-1.5 rounded-md bg-green text-paper text-xs font-semibold">{t('classify')}</button>}
                    {(dossier.status === 'classified' || dossier.status === 'mapped') && !clarificationNeeded && <button disabled={busyId === dossier.dossier_id} onClick={() => performAction(dossier.dossier_id, api.mapDossier)} className="press px-3 py-1.5 rounded-md bg-green text-paper text-xs font-semibold">{t('map')}</button>}
                    {dossier.status === 'mapped' && <button disabled={busyId === dossier.dossier_id} onClick={() => performAction(dossier.dossier_id, api.reviewDossier, {})} className="press px-3 py-1.5 rounded-md border border-earth/40 text-earth text-xs font-semibold">{t('review')}</button>}
                    {busyId === dossier.dossier_id && <Loader2 size={16} className="animate-spin text-green self-center" />}
                  </div>
                  <button aria-label={t('delete')} title={t('delete')} onClick={() => removeDossier(dossier.dossier_id)} className="press p-2 rounded-md text-rust/70 hover:bg-rust/5"><Trash2 size={15} /></button>
                </div>
                <details className="text-xs text-ink/50">
                  <summary className="cursor-pointer">{t('history')}</summary>
                  <ol className="mt-2 space-y-1">{dossier.history.map((event, index) => <li key={`${event.created_at}-${index}`}>{event.event_type.replaceAll('_', ' ')} · {new Date(event.created_at + 'Z').toLocaleString()}</li>)}</ol>
                </details>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
