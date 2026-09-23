import { useState } from 'react'
import { ChevronDown, ExternalLink, Scale, ShieldCheck } from 'lucide-react'
import { JurisdictionMark } from './JurisdictionMark'

const DIAL_R = 15
const DIAL_C = 2 * Math.PI * DIAL_R

/**
 * Relevance read as a dial rather than a percentage pill. The arc carries the
 * value at a glance across a stack of sources; the figure inside only
 * confirms it. Animating stroke-dashoffset means the arc draws in as the
 * result lands, which reads as a measurement being taken rather than a badge
 * being printed.
 */
function RelevanceDial({ score, label }) {
  const pct = Math.round(Math.min(Math.max(score, 0), 1) * 100)
  return (
    <div className="relevance-dial" title={`${pct}% ${label}`}>
      <svg width="40" height="40" viewBox="0 0 40 40">
        <circle className="relevance-dial__track" cx="20" cy="20" r={DIAL_R} fill="none" strokeWidth="2.5" />
        <circle
          className="relevance-dial__value"
          cx="20" cy="20" r={DIAL_R} fill="none" strokeWidth="2.5"
          strokeDasharray={DIAL_C}
          strokeDashoffset={DIAL_C * (1 - pct / 100)}
        />
      </svg>
      <span className="relevance-dial__figure">{pct}%</span>
    </div>
  )
}

export default function SourceCard({ source, index, copy }) {
  const [open, setOpen] = useState(index === 0)
  const url = source.source_url?.split(' ')[0]
  const isValidUrl = url && /^https?:\/\//.test(url)

  return (
    <div className="dossier-panel source-card overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-start justify-between gap-3 p-4 sm:p-5 pl-5 sm:pl-6 text-left hover:bg-green-pale/40 transition-colors"
      >
        <div className="flex items-start gap-3.5 min-w-0">
          {/* A struck seal, not a generic avatar square — every retained source
              is an instrument of record, and should look stamped. */}
          <span className="source-seal mt-0.5">
            <Scale size={15} strokeWidth={2.1} />
          </span>
          <div className="min-w-0">
            <span className="citation-marker inline-flex items-center gap-1.5 text-[10px] text-green/70 tracking-wide">
              {copy.sourceLabel} {String(index + 1).padStart(2, '0')}
              <span className="text-green/30">/</span>
              <JurisdictionMark jurisdiction={source.jurisdiction} size={11} className="text-green/70" />
              {source.jurisdiction}
            </span>
            <h4 className="font-serif text-base sm:text-[1.0625rem] text-green-dark mt-1 leading-snug">{source.title}</h4>
            <p className="text-sm text-ink/60 mt-0.5">{source.section}</p>
          </div>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <RelevanceDial score={source.relevance_score} label={copy.matchLabel} />
          <ChevronDown size={16} className={`text-ink/40 transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {open && (
        <div className="px-4 sm:px-5 pl-5 sm:pl-6 pb-5 pt-1 border-t border-hairline bg-paper/45 animate-in">
          <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-xs text-ink/70 mt-3">
            <div><dt className="inline font-medium text-ink/80">{copy.sourceFields.authority}: </dt><dd className="inline">{source.authority}</dd></div>
            <div><dt className="inline font-medium text-ink/80">{copy.sourceFields.domain}: </dt><dd className="inline">{source.domain}</dd></div>
            <div><dt className="inline font-medium text-ink/80">{copy.sourceFields.type}: </dt><dd className="inline">{source.source_type}</dd></div>
            <div><dt className="inline font-medium text-ink/80">{copy.sourceFields.version}: </dt><dd className="inline">{source.version_date}</dd></div>
            <div><dt className="inline font-medium text-ink/80">{copy.sourceFields.retrieved}: </dt><dd className="inline">{source.retrieved_date}</dd></div>
            <div className="sm:col-span-2"><dt className="inline font-medium text-ink/80">{copy.sourceFields.precision}: </dt><dd className="inline">{source.precision}</dd></div>
          </dl>
          <div className="evidence-rule mt-4 mb-3" />
          <div className="flex items-center justify-between gap-3 flex-wrap">
            {isValidUrl ? (
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-green hover:text-green-dark underline underline-offset-2"
              >
                {copy.viewSource} <ExternalLink size={12} />
              </a>
            ) : (
              <p className="text-[11px] text-ink/40 italic">{source.source_url}</p>
            )}
            <span className="citation-marker inline-flex items-center gap-1.5 text-[10px] text-green/60 shrink-0">
              <ShieldCheck size={12} strokeWidth={2.2} />
              {source.id}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
