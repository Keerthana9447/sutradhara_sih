import { useState } from 'react'
import { ShieldCheck, ScrollText, Loader2, Search, Check, Minus, AlertCircle } from 'lucide-react'
import { api } from '../api'
import JurisdictionSwitch from './JurisdictionSwitch'
import SourceCard from './SourceCard'
import MicButton from './MicButton'
import ReadAloudButton from './ReadAloudButton'
import { EmptyPlate, LeafSprig, ManuscriptRule } from './Botanical'

/**
 * Standalone, single-purpose tools that expose individual pipeline
 * capabilities on their own rather than only as panels buried inside a
 * full /api/analyze result. This lets a judge probe ABS and TKDL directly.
 *
 * ABSTool and TKDLTool call /api/analyze (the endpoint that computes
 * abs_checklist / tk_pointer) and then render only their one relevant
 * panel, discarding the rest of the response.
 */

function ToolShell({ icon: Icon, title, lede, copy, children }) {
  return (
    <div className="animate-in relative">
      <LeafSprig size={130} flip className="pointer-events-none absolute -right-6 -top-6 text-green opacity-[0.07] hidden lg:block" />
      <div className="relative flex items-start gap-3.5 mb-1">
        <span className="inline-flex items-center justify-center w-11 h-11 rounded-lg border border-green/15 bg-gradient-to-br from-green-pale to-green-pale/50 text-green shrink-0 mt-0.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
          <Icon size={18} strokeWidth={2.1} />
        </span>
        <div>
          <p className="section-kicker mb-1">{copy.focusedTool}</p>
          <h2 className="font-serif text-2xl sm:text-[1.75rem] text-green-dark leading-tight tracking-tight">{title}</h2>
          <p className="text-sm text-ink/60 mt-1.5 max-w-[68ch] leading-relaxed">{lede}</p>
        </div>
      </div>
      <ManuscriptRule className="text-gold max-w-[180px] mt-4 ml-[3.5rem]" />
      <div className="mt-6 tool-surface">{children}</div>
    </div>
  )
}

function QueryBox({
  value,
  onChange,
  placeholder,
  onSubmit,
  loading,
  buttonLabel,
  loadingLabel,
  extra,
  copy,
  language,
  externalProcessingConsent,
  setExternalProcessingConsent,
  readAloudText,
  readAloudLang,
}) {
  return (
    <div className="dossier-panel p-4 sm:p-5 mb-6 border-green/20">
      {extra && <div className="flex items-center justify-end mb-3">{extra}</div>}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={3}
        className="research-input w-full min-h-24 border border-hairline rounded-md px-4 py-3 text-sm leading-relaxed focus:outline-none"
      />
      <label className="mt-3 flex items-start gap-2 text-xs leading-relaxed text-ink/60">
        <input
          type="checkbox"
          checked={externalProcessingConsent}
          onChange={(e) => setExternalProcessingConsent(e.target.checked)}
          className="mt-0.5"
        />
        <span>{copy.externalProcessingConsent}</span>
      </label>
      <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
        <span className="inline-flex items-center gap-2.5">
          <MicButton
            consentGiven={externalProcessingConsent}
            sourceLanguage={language}
            copy={copy}
            onTranscribed={(text) =>
              onChange(value.trim() ? `${value.trim()} ${text}` : text)
            }
          />

          <ReadAloudButton
            consentGiven={externalProcessingConsent}
            text={readAloudText || ''}
            lang={readAloudLang || language}
            copy={copy}
          />
        </span>

        <button
          onClick={onSubmit}
          disabled={!value.trim() || loading}
          className="press inline-flex items-center gap-2 px-5 py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark hover:-translate-y-0.5 disabled:opacity-50 shadow-panel"
        >
          {loading && <Loader2 size={14} className="animate-spin" />}
          {loading ? loadingLabel : buttonLabel}
        </button>
      </div>
    </div>
  )
}

export function ABSTool({ copy, language, externalProcessingConsent, setExternalProcessingConsent }) {
  const [query, setQuery] = useState('')
  const [jurisdiction, setJurisdiction] = useState('India')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.analyze({
        query,
        jurisdiction,
        language,
        external_processing_consent: externalProcessingConsent,
      })
      setResult(res)
    } catch (e) {
      setError(copy.systemError)
    } finally {
      setLoading(false)
    }
  }

  const checklist = result?.abs_checklist

  return (
    <ToolShell icon={ShieldCheck} title={copy.absTitle} lede={copy.absLede} copy={copy}>
      <QueryBox
        value={query}
        onChange={setQuery}
        placeholder={copy.absPlaceholder}
        onSubmit={run}
        loading={loading}
        buttonLabel={copy.absButton}
        loadingLabel={copy.working}
        extra={<JurisdictionSwitch value={jurisdiction} onChange={setJurisdiction} copy={copy} />}
        copy={copy}
        language={language}
        externalProcessingConsent={externalProcessingConsent}
        setExternalProcessingConsent={setExternalProcessingConsent}
        readAloudText={!loading && result && !result.abstained ? result.answer : ''}
        readAloudLang={result?.answer_language || language}
      />

      {error && <p className="text-sm text-rust mb-4">{error}</p>}

      {result && (
        checklist ? (
          <div className="dossier-panel p-5 border-gold/40 animate-in">
            <p className="section-kicker mb-3 font-medium flex items-center gap-2">
              <Search size={14} />
              {copy.absConsiderations}
            </p>
            <ul className="text-sm text-ink/75 divide-y divide-hairline/70 border-y border-hairline/70">
              {[
                [checklist.biological_resource_involved, copy.absChecklist.biologicalResource],
                [checklist.provenance_identified, copy.absChecklist.provenance],
                [checklist.abs_framework_identified, copy.absChecklist.framework],
                [checklist.supporting_source_retrieved, copy.absChecklist.source],
              ].map(([met, text]) => (
                <li key={text} className="flex items-center gap-2.5 py-2.5">
                  <span className={`inline-flex items-center justify-center w-5 h-5 rounded-[4px] shrink-0 border ${met ? 'bg-green-pale border-green/30 text-green' : 'bg-paper-dim border-hairline text-ink/30'}`}>
                    {met ? <Check size={12} strokeWidth={3} /> : <Minus size={12} strokeWidth={3} />}
                  </span>
                  <span className={met ? 'text-ink/85' : 'text-ink/50'}>{text}</span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-ink/50 mt-3">{checklist.note}</p>
          </div>
        ) : (
          <div className="dossier-panel p-7 text-center animate-in">
            <AlertCircle size={20} className="mx-auto mb-2.5 text-gold-dark" />
            <p className="text-sm text-ink/55 max-w-md mx-auto leading-relaxed">{copy.absNotTriggered}</p>
          </div>
        )
      )}

      {!result && !loading && !error && (
          <EmptyTool icon={ShieldCheck} label={copy.absChecklistLabel} preview={copy.preview} text={copy.absEmpty} />
      )}
    </ToolShell>
  )
}

export function TKDLTool({ copy, language, externalProcessingConsent, setExternalProcessingConsent }) {
  const [query, setQuery] = useState('')
  const [jurisdiction, setJurisdiction] = useState('India')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.analyze({
        query,
        jurisdiction,
        language,
        external_processing_consent: externalProcessingConsent,
      })
      setResult(res)
    } catch (e) {
      setError(copy.systemError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <ToolShell icon={ScrollText} title={copy.tkdlTitle} lede={copy.tkdlLede} copy={copy}>
      <QueryBox
        value={query}
        onChange={setQuery}
        placeholder={copy.tkdlPlaceholder}
        onSubmit={run}
        loading={loading}
        buttonLabel={copy.tkdlButton}
        loadingLabel={copy.working}
        extra={<JurisdictionSwitch value={jurisdiction} onChange={setJurisdiction} copy={copy} />}
        copy={copy}
        language={language}
        externalProcessingConsent={externalProcessingConsent}
        setExternalProcessingConsent={setExternalProcessingConsent}
        readAloudText={!loading && result && !result.abstained ? result.answer : ''}
        readAloudLang={result?.answer_language || language}
      />

      {error && <p className="text-sm text-rust mb-4">{error}</p>}

      {result && !result.needs_clarification && (
        result.tk_pointer ? (
          <>
            <div className="dossier-panel p-5 border-gold/40 animate-in mb-4">
              <p className="section-kicker mb-1.5 font-medium flex items-center gap-2">
                <Search size={14} />
                {copy.tkPointer}
              </p>
              <p className="text-sm text-ink/75">{result.tk_pointer}</p>
            </div>
            {result.sources?.length > 0 && (
              <div className="grid gap-3">
                {result.sources.map((s, i) => (
                  <SourceCard key={s.id} source={s} index={i} copy={copy} />
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="dossier-panel p-7 text-center animate-in">
            <AlertCircle size={20} className="mx-auto mb-2.5 text-gold-dark" />
            <p className="text-sm text-ink/55 max-w-md mx-auto leading-relaxed">{copy.tkdlNotTriggered}</p>
          </div>
        )
      )}

      {!result && !loading && !error && (
        <EmptyTool icon={ScrollText} label={copy.tkdlPointerLabel} preview={copy.preview} text={copy.tkdlEmpty} />
      )}
    </ToolShell>
  )
}

function EmptyTool({ icon: Icon, label, preview, text }) {
  return (
    <div className="tool-empty">
      <EmptyPlate className="text-gold-dark opacity-70 shrink-0" />
      <div>
        <p className="citation-marker inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] text-gold-dark">
          <Icon size={13} strokeWidth={2.2} />
          {label} {preview}
        </p>
        <p className="text-sm text-ink/55 mt-1.5 max-w-sm leading-relaxed">{text}</p>
      </div>
    </div>
  )
}
