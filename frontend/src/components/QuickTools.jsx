import { useState, useEffect } from 'react'
import { ShieldCheck, ScrollText, Loader2, Search, Check, Minus, AlertCircle, Link2, Unlink, PlugZap } from 'lucide-react'
import { api } from '../api'
import JurisdictionSwitch from './JurisdictionSwitch'
import SourceCard from './SourceCard'
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

function QueryBox({ value, onChange, placeholder, onSubmit, loading, buttonLabel, loadingLabel, extra }) {
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
      <div className="flex justify-end mt-3">
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

export function ABSTool({ copy, language }) {
  const [query, setQuery] = useState('')
  const [jurisdiction, setJurisdiction] = useState('India')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.analyze({ query, jurisdiction, language })
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

export function TKDLTool({ copy, language }) {
  const [query, setQuery] = useState('')
  const [jurisdiction, setJurisdiction] = useState('India')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.analyze({ query, jurisdiction, language })
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

export function ConnectorTool({ copy }) {
  const [provider, setProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [connectors, setConnectors] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [usageQuery, setUsageQuery] = useState('')
  const [usageTarget, setUsageTarget] = useState(null)
  const [usageResult, setUsageResult] = useState(null)
  const [usageLoading, setUsageLoading] = useState(false)

  async function refresh() {
    try {
      setConnectors(await api.connectors())
    } catch (e) {
      setError(copy.systemError)
    }
  }

  useEffect(() => { refresh() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function link() {
    if (!provider.trim() || !apiKey.trim()) return
    setLoading(true)
    setError(null)
    try {
      await api.connectorLink({ provider, api_key: apiKey, scope: 'patent_search' })
      setProvider('')
      setApiKey('')
      await refresh()
    } catch (e) {
      setError(copy.systemError)
    } finally {
      setLoading(false)
    }
  }

  async function revoke(id) {
    try {
      await api.connectorRevoke({ connector_id: id })
      if (usageTarget === id) { setUsageTarget(null); setUsageResult(null) }
      await refresh()
    } catch (e) {
      setError(copy.systemError)
    }
  }

  async function simulateUse() {
    if (!usageTarget || !usageQuery.trim()) return
    setUsageLoading(true)
    try {
      const res = await api.analyze({ query: usageQuery, jurisdiction: 'India', language: 'en', use_connector_id: usageTarget })
      setUsageResult(res.connector_source_used)
    } catch (e) {
      setError(copy.systemError)
    } finally {
      setUsageLoading(false)
    }
  }

  const activeConnectors = connectors.filter((c) => c.status === 'active')

  return (
    <ToolShell icon={PlugZap} title={copy.connectorsTitle} lede={copy.connectorsLede} copy={copy}>
      <div className="dossier-panel p-4 sm:p-5 mb-6 border-green/20">
        <p className="text-xs font-semibold text-ink/60 mb-3">{copy.connectorLinkHeading}</p>
        <div className="grid sm:grid-cols-2 gap-3 mb-3">
          <input
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            placeholder={copy.connectorProviderPlaceholder}
            className="border border-hairline rounded-md px-3 py-2.5 text-sm bg-paper focus:outline-none focus:ring-1 focus:ring-green"
          />
          <input
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={copy.connectorKeyPlaceholder}
            type="password"
            className="border border-hairline rounded-md px-3 py-2.5 text-sm bg-paper focus:outline-none focus:ring-1 focus:ring-green"
          />
        </div>
        <div className="flex justify-end">
          <button
            onClick={link}
            disabled={!provider.trim() || !apiKey.trim() || loading}
            className="press inline-flex items-center gap-2 px-5 py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark hover:-translate-y-0.5 disabled:opacity-50 shadow-panel"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Link2 size={14} />}
            {loading ? copy.working : copy.connectorLinkButton}
          </button>
        </div>
        <p className="text-[11px] text-ink/45 mt-3 leading-relaxed">{copy.connectorPrivacyNote}</p>
      </div>

      {error && <p className="text-sm text-rust mb-4">{error}</p>}

      {activeConnectors.length > 0 ? (
        <div className="space-y-3 mb-6">
          {activeConnectors.map((c) => (
            <div key={c.connector_id} className="dossier-panel lift-on-hover p-4 flex items-center justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink/85">{c.provider} <span className="citation-marker text-xs text-ink/40">···{c.key_fingerprint}</span></p>
                <p className="text-xs text-ink/55 mt-0.5">{copy.connectorScope}: {c.scope} · {copy.connectorLinkedAt} {new Date(c.linked_at).toLocaleDateString()}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => { setUsageTarget(c.connector_id); setUsageResult(null) }}
                  className={`press text-xs font-medium px-3 py-1.5 rounded-md border ${usageTarget === c.connector_id ? 'bg-green text-paper border-green' : 'border-green/30 text-green hover:bg-green-pale'}`}
                >
                  {copy.connectorSelectForTest}
                </button>
                <button
                  onClick={() => revoke(c.connector_id)}
                  className="press inline-flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-md border border-rust/30 text-rust hover:bg-rust/10"
                >
                  <Unlink size={12} /> {copy.connectorRevokeButton}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        !loading && (
          <div className="tool-empty mb-6">
            <EmptyPlate className="text-gold-dark opacity-70 shrink-0" />
            <p className="text-sm text-ink/55 max-w-sm leading-relaxed">{copy.connectorsEmpty}</p>
          </div>
        )
      )}

      {usageTarget && (
        <div className="dossier-panel p-4 sm:p-5 border-gold/40 animate-in">
          <p className="text-xs font-semibold text-ink/60 mb-3">{copy.connectorTestHeading}</p>
          <textarea
            value={usageQuery}
            onChange={(e) => setUsageQuery(e.target.value)}
            placeholder={copy.connectorTestPlaceholder}
            rows={2}
            className="research-input w-full border border-hairline rounded-md px-3 py-2.5 text-sm focus:outline-none mb-3"
          />
          <div className="flex justify-end">
            <button
              onClick={simulateUse}
              disabled={!usageQuery.trim() || usageLoading}
              className="press inline-flex items-center gap-2 px-4 py-2 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark disabled:opacity-50"
            >
              {usageLoading && <Loader2 size={14} className="animate-spin" />}
              {usageLoading ? copy.working : copy.connectorRunTest}
            </button>
          </div>
          {usageResult && (
            <div className="mt-4 border-t border-hairline pt-4">
              <p className="text-sm font-semibold text-ink/85">{usageResult.provider}</p>
              <p className="text-xs text-ink/60 mt-1">{usageResult.note}</p>
            </div>
          )}
        </div>
      )}
    </ToolShell>
  )
}
