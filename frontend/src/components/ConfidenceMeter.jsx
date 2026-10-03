import { ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react'

const LABEL_STYLE = {
  HIGH: { text: 'text-green', bar: 'bg-green', border: 'border-green/30', bg: 'bg-green-pale', rule: '#2E5940', Icon: ShieldCheck },
  MEDIUM: { text: 'text-gold-dark', bar: 'bg-gold', border: 'border-gold/30', bg: 'bg-gold-light/20', rule: '#B8862E', Icon: ShieldQuestion },
  LOW: { text: 'text-rust', bar: 'bg-rust', border: 'border-rust/30', bg: 'bg-rust/10', rule: '#A03E2A', Icon: ShieldAlert },
}

const FACTOR_LABELS = {
  retrieval_relevance: 'Retrieval relevance',
  source_count_factor: 'Source count',
  source_authority: 'Source authority',
  agreement: 'Domain agreement',
  classification_confidence: 'Classification confidence',
}

export default function ConfidenceMeter({ confidence, label, breakdown, copy }) {
  const style = LABEL_STYLE[label] || LABEL_STYLE.LOW
  const Icon = style.Icon
  const widthPct = Math.round(Math.min(confidence, 1) * 100)

  return (
    <div className="dossier-panel p-5 sm:p-6 border-l-4 border-l-green">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <span className="section-kicker">{copy?.confidence || 'Evidence Confidence'}</span>
          <p className="text-xs text-ink/45 mt-1">{copy?.confidenceSupport}</p>
        </div>
        <span className={`inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-md border ${style.border} ${style.bg} ${style.text}`}>
          <Icon size={15} strokeWidth={2.2} />
          {label}
        </span>
      </div>

      {/* The score is set as a figure in a margin, the way a folio carries a
          marginal note — it belongs to the analysis rather than floating
          above it as a dashboard stat. */}
      <div className="flex items-end gap-3.5 mb-3 pl-3.5" style={{ borderLeft: `2px solid ${style.rule}` }}>
        <span className={`font-serif text-[2.75rem] leading-[0.85] tracking-tight ${style.text}`}>{widthPct}%</span>
        <span className="text-xs text-ink/45 mb-1">{copy?.compositeConfidence}</span>
      </div>

      <div className="confidence-scale" aria-label={`${widthPct}% ${copy?.confidenceScale}`}>
        {Array.from({ length: 10 }, (_, index) => (
          <span
            key={index}
            className={index < Math.ceil(widthPct / 10) ? style.bar : ''}
            style={{ transitionDelay: `${index * 45}ms` }}
          />
        ))}
        <i style={{ left: `${widthPct}%` }} />
      </div>

      {breakdown && Object.keys(breakdown).length > 0 && (
        <dl className="mt-5 space-y-2.5">
          {Object.entries(breakdown).map(([k, v], i) => (
            <div key={k} className="flex items-center gap-3 confidence-factor-row">
              <dt className="text-xs text-ink/60 w-44 shrink-0 confidence-factor-label">{copy?.confidenceFactors?.[k] || FACTOR_LABELS[k] || k.replaceAll('_', ' ')}</dt>
              <div className="flex-1 h-1.5 bg-hairline/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-mid/75 rounded-full transition-[width] duration-700 ease-out"
                  style={{ width: `${Math.round(Math.min(v, 1) * 100)}%`, transitionDelay: `${i * 70}ms` }}
                />
              </div>
              <dd className="citation-marker text-xs text-ink/50 w-10 text-right">{v}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="evidence-rule mt-4 mb-2.5" />
      <p className="text-[11px] text-ink/40 leading-relaxed">
        {copy?.confidenceNote}
      </p>
    </div>
  )
}
