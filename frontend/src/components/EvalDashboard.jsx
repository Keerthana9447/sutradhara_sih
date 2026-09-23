import { useEffect, useState } from 'react'
import { BarChart3, Check, CircleDashed, FileCheck2, Loader2, ShieldCheck, ShieldAlert, PlayCircle } from 'lucide-react'
import { api } from '../api'

function InvariantBadge({ ok, label, value }) {
  return (
    <div className={`flex items-center gap-2.5 rounded-md px-3.5 py-3 border transition-shadow ${ok ? 'bg-green-pale/70 border-green/25 shadow-[inset_3px_0_0_rgba(46,89,64,0.55)]' : 'bg-rust/10 border-rust/40 shadow-[inset_3px_0_0_rgba(160,62,42,0.6)]'}`}>
      {ok ? <ShieldCheck size={16} className="text-green shrink-0" /> : <ShieldAlert size={16} className="text-rust shrink-0" />}
      <div className="min-w-0">
        <p className={`text-sm font-semibold ${ok ? 'text-green-dark' : 'text-rust'}`}>{label}</p>
        <p className="citation-marker text-xs text-ink/50">{value}</p>
      </div>
    </div>
  )
}

function MetricBar({ label, value }) {
  const pct = value == null ? null : Math.round(value * 100)
  return (
    <div className="eval-metric-card rounded-md p-4">
      <p className="eval-metric-label text-sm font-semibold text-green-dark leading-snug">{label}</p>
      <p className="font-serif text-3xl text-green leading-none mt-2.5">{pct == null ? '—' : `${pct}%`}</p>
      {pct != null && (
        <div className="mt-3 h-1.5 bg-hairline/60 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-green-mid to-green rounded-full transition-[width] duration-700 ease-out" style={{ width: `${Math.min(pct, 100)}%` }} />
        </div>
      )}
    </div>
  )
}

function BenchmarkSection({ copy }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  async function run() {
    setLoading(true)
    setError(false)
    try {
      setReport(await api.evalBenchmark())
    } catch (e) {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dossier-panel p-5 sm:p-6 mt-6 border-gold/30 animate-in">
      <div className="flex items-start justify-between flex-wrap gap-3 mb-1">
        <div>
          <p className="section-kicker mb-1">{copy.eval.benchmarkKicker}</p>
          <h3 className="font-serif text-lg text-green-dark">{copy.eval.benchmarkTitle}</h3>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="press inline-flex items-center gap-2 px-4 py-2 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark disabled:opacity-60 shadow-panel shrink-0"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <PlayCircle size={14} />}
          {loading ? copy.working : copy.eval.benchmarkRun}
        </button>
      </div>
      <p className="text-sm text-ink/60 mb-4 max-w-2xl">{copy.eval.benchmarkLede}</p>

      {error && <p className="text-sm text-rust mb-2">{copy.systemError}</p>}

      {report && (
        <>
          <div className="grid sm:grid-cols-2 gap-3 mb-4">
            <InvariantBadge
              ok={report.jurisdiction_isolation_violations === 0}
              label={copy.eval.jurisdictionInvariant}
              value={`${report.jurisdiction_isolation_violations} ${copy.eval.violations}`}
            />
            <InvariantBadge
              ok={report.citation_integrity_violations === 0}
              label={copy.eval.citationInvariant}
              value={`${report.citation_integrity_violations} ${copy.eval.violations}`}
            />
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricBar label={copy.eval.classificationAccuracy} value={report.classification_accuracy} />
            <MetricBar label={copy.eval.abstentionAccuracyLabel} value={report.abstention_accuracy} />
            <MetricBar label={copy.eval.clarificationAccuracy} value={report.clarification_accuracy} />
            <MetricBar label={copy.eval.citationHitRate} value={report.citation_hit_rate} />
          </div>
          <p className="text-[11px] text-ink/45 mt-4 leading-relaxed">
            {copy.eval.benchmarkItemCount.replace('{n}', report.total_items)}
          </p>
        </>
      )}

      {!report && !loading && !error && (
        <p className="text-xs text-ink/45 italic">{copy.eval.benchmarkEmpty}</p>
      )}
    </div>
  )
}

export default function EvalDashboard({ copy }) {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api.evalSummary().then(setSummary).catch(() => setError(true))
  }, [])

  if (error) return <EmptyEval copy={copy} />

  if (!summary) {
    return (
      <div className="dossier-panel p-6 animate-in" aria-busy="true">
        <div className="skeleton h-3 w-32 rounded mb-4" />
        <div className="grid sm:grid-cols-3 gap-3">
          <div className="skeleton h-24 rounded-md" />
          <div className="skeleton h-24 rounded-md" />
          <div className="skeleton h-24 rounded-md" />
        </div>
      </div>
    )
  }

  const sessionRows = [
    [copy.eval.totalQueries, summary.total_queries],
    [copy.eval.safeAbstention, summary.safe_abstention_rate ?? copy.eval.pending],
    [copy.eval.averageConfidence, summary.average_confidence ?? copy.eval.pending],
  ]

  return (
    <div className="animate-in">
      <div className="data-stage">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 size={16} className="text-gold-light" />
          <div><p className="section-kicker">{copy.eval.observability}</p><h3 className="font-serif text-lg text-green-dark">{copy.eval.title}</h3></div>
        </div>
        <p className="text-xs text-paper/65 mb-4 max-w-xl">{copy.eval.sessionLede}</p>
        <div className="grid sm:grid-cols-3 gap-3">
          {sessionRows.map(([k, v]) => (
            <div key={k} className="eval-metric-card rounded-md p-4">
              <p className="eval-metric-label text-sm font-semibold text-green-dark leading-snug">{k}</p>
              <p className="citation-marker text-xs font-normal text-ink/70 mt-2 break-words">{v}</p>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-paper/65 mt-4 leading-relaxed">{copy.eval.note}</p>
      </div>

      <BenchmarkSection copy={copy} />
    </div>
  )
}

function EmptyEval({ copy }) {
  return <div className="animate-in">
    <div className="data-stage">
      <div className="flex items-center gap-2 mb-4"><BarChart3 size={16} className="text-gold-light" /><div><p className="section-kicker text-gold-light">{copy.eval.observability}</p><h3 className="font-serif text-xl text-paper">{copy.eval.title}</h3></div></div>
      <div className="eval-empty-dashboard">
        <div className="eval-empty-chart"><span /><span /><span /><span /><div className="eval-empty-line" /></div>
        <div><p className="font-serif text-xl text-paper">{copy.eval.emptyTitle}</p><p className="text-sm text-paper/60 mt-2 max-w-md">{copy.eval.emptyBody}</p><div className="flex gap-3 mt-5 text-xs text-paper/55"><span><FileCheck2 size={14} /> {copy.eval.citationReview}</span><span><Check size={14} /> {copy.eval.safeAbstention}</span></div></div>
      </div>
    </div>
    <BenchmarkSection copy={copy} />
  </div>
}
