import { useState, useEffect } from "react"
import { Database, Search, Filter, ExternalLink, CheckCircle2, Link2, Shield } from "lucide-react"
import useTranslatedStrings from '../hooks/useTranslatedStrings'

const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "")

async function fetchRegistry(system, keyword, limit, offset) {
  const params = new URLSearchParams({ limit, offset })
  if (system) params.set("system", system)
  if (keyword) params.set("keyword", keyword)
  const res = await fetch(`${API_ORIGIN}/api/v1/patents?${params}`)
  if (!res.ok) throw new Error("Registry fetch failed")
  return res.json()
}

const SYSTEM_COLORS = {
  "Ayurveda": "border-green/30 bg-green-pale text-green",
  "Siddha": "border-gold/30 bg-gold-light/10 text-gold-dark",
  "Unani": "border-earth/30 bg-earth/10 text-earth",
  "Citizen Claim": "border-ink/20 bg-ink/5 text-ink/70",
}

function RegistryCard({ entry, index, t }) {
  const sysColor = SYSTEM_COLORS[entry.system] || "border-hairline bg-paper/50 text-ink/60"
  return (
    <div className="lift-on-hover dossier-panel p-4 sm:p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <p className="font-semibold text-ink/90">{t(`name${index}`)}</p>
          <p className="text-xs text-ink/40 mt-0.5">{entry.id}</p>
        </div>
        <span className={`citation-marker shrink-0 text-[11px] px-2.5 py-1 rounded-full border ${sysColor}`}>
          {t(`system${index}`)}
        </span>
      </div>
      <p className="text-sm text-ink/65 leading-relaxed">{t(`description${index}`)}</p>
      {entry.ingredients && entry.ingredients.length > 0 && (
        <div className="flex gap-1.5 flex-wrap">
          {entry.ingredients.map((ing, i) => (
            <span key={i} className="text-[11px] border border-green/20 bg-green-pale text-green px-2 py-0.5 rounded-full">{t(`ingredient${index}_${i}`)}</span>
          ))}
        </div>
      )}
      {entry.therapeutic_use && (
        <p className="text-xs text-ink/50"><span className="font-medium">{t('useLabel')}</span> {t(`use${index}`)}</p>
      )}
      {entry.source_text && (
        <p className="text-xs text-ink/40 italic border-t border-hairline pt-2">{t(`sourceText${index}`)}</p>
      )}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <span className={`inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md ${
          entry.status?.includes("Revoked") ? "bg-rust/10 text-rust" :
          entry.status === "Blockchain Anchored" ? "bg-ink/5 text-ink/60" :
          entry.status === "Verified" ? "bg-green-pale text-green" :
          "bg-gold-light/10 text-gold-dark"
        }`}>
          {entry.status?.includes("Anchored") ? <Link2 size={11} /> :
           entry.status === "Verified" ? <CheckCircle2 size={11} /> :
           <Shield size={11} />}
          {t(`status${index}`)}
        </span>
      </div>
    </div>
  )
}

export default function PatentsRegistry({ copy, language = 'en' }) {
  const [entries, setEntries] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [keyword, setKeyword] = useState("")
  const [system, setSystem] = useState("")
  const [offset, setOffset] = useState(0)
  const LIMIT = 12
  const translationSource = {
    heading: 'Public prior-art references',
    intro: "Browse illustrative public prior-art references. These entries are not records from the restricted TKDL; verify source documents independently. Private citizen claims are not published here.",
    searchPlaceholder: 'Search by name, ingredient',
    allSystems: 'All Systems',
    search: 'Search',
    loadError: 'Could not load registry.',
    entriesFound: 'entries found',
    viewTKDL: 'TKDL access is restricted',
    loading: 'Loading registry',
    previous: 'Previous',
    next: 'Next',
    useLabel: 'Use:',
    translationUnavailable: 'Some registry text could not be translated and is shown in English.',
    ...Object.fromEntries(entries.flatMap((entry, index) => [
      [`name${index}`, entry.name],
      [`system${index}`, entry.system],
      [`description${index}`, entry.description],
      [`use${index}`, entry.therapeutic_use || ''],
      [`sourceText${index}`, entry.source_text || ''],
      [`status${index}`, entry.status],
      ...(entry.ingredients || []).map((ingredient, ingredientIndex) => [
        `ingredient${index}_${ingredientIndex}`,
        ingredient,
      ]),
    ])),
  }
  const { text: t, available: translationAvailable, pending: translationPending } =
    useTranslatedStrings(language, translationSource)

  const load = async (kw = keyword, sys = system, off = offset) => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchRegistry(sys, kw, LIMIT, off)
      setEntries(data.entries || [])
      setTotal(data.total || 0)
    } catch {
      setError("Could not load registry.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function handleSearch(e) {
    e.preventDefault()
    setOffset(0)
    load(keyword, system, 0)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-green">
        <div className="flex items-start gap-3">
          <span className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-green-pale text-green shrink-0">
            <Database size={20} />
          </span>
          <div>
            <h2 className="font-serif text-xl text-green-dark">{t('heading')}</h2>
            <p className="text-sm text-ink/60 mt-1 max-w-[65ch]">{t('intro')}</p>
          </div>
        </div>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="dossier-panel p-4 flex gap-3 flex-wrap">
        <div className="flex-1 min-w-48 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/35" />
          <input
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder={t('searchPlaceholder')}
            className="research-input w-full border border-hairline rounded-md pl-9 pr-4 py-2.5 text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-ink/35 shrink-0" />
          <select value={system} onChange={e => setSystem(e.target.value)}
            className="research-input border border-hairline rounded-md px-3 py-2.5 text-sm">
            <option value="">{t('allSystems')}</option>
            <option value="Ayurveda">Ayurveda</option>
            <option value="Siddha">Siddha</option>
            <option value="Unani">Unani</option>
          </select>
        </div>
        <button type="submit"
          className="press px-4 py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark">
          {t('search')}
        </button>
      </form>

      {!translationAvailable && !translationPending && language !== 'en' && <p role="status" className="text-xs text-earth">{t('translationUnavailable')}</p>}

      {error && (
        <div className="dossier-panel p-4 border-rust/40 bg-rust/5">
          <p className="text-sm text-rust">{error === 'Could not load registry.' ? t('loadError') : error}</p>
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center justify-between text-xs text-ink/45">
        <span>{total} {t('entriesFound')}</span>
        <a href="https://tkdl.res.in" target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1 hover:text-green underline underline-offset-2">
          <ExternalLink size={11} /> {t('viewTKDL')}
        </a>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-ink/40 gap-3">
          <svg className="animate-spin w-5 h-5 text-green" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm">{t('loading')}</span>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {entries.map((entry, index) => <RegistryCard key={entry.id} entry={entry} index={index} t={t} />)}
        </div>
      )}

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex items-center justify-center gap-3">
          <button disabled={offset === 0}
            onClick={() => { const o = Math.max(0, offset - LIMIT); setOffset(o); load(keyword, system, o) }}
            className="press px-4 py-2 text-sm border border-hairline rounded-md disabled:opacity-40 hover:border-green/40">
            ? {t('previous')}
          </button>
          <span className="text-xs text-ink/45">{Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}</span>
          <button disabled={offset + LIMIT >= total}
            onClick={() => { const o = offset + LIMIT; setOffset(o); load(keyword, system, o) }}
            className="press px-4 py-2 text-sm border border-hairline rounded-md disabled:opacity-40 hover:border-green/40">
            {t('next')} ?
          </button>
        </div>
      )}
    </div>
  )
}
