import { ShieldAlert, Send } from 'lucide-react'
import { BotanicalCorner } from './Botanical'

/**
 * Safe abstention.
 *
 * The system declining to answer is a feature that had to be engineered, and
 * it is the single most defensible thing about the product — so it is given
 * the same weight as the hero rather than being demoted to a yellow warning
 * box. Deep-green stage, struck seal, the invariant named out loud, and the
 * escalation route offered immediately.
 *
 * The graphic below is the evidence thread from the hero, cut short: the run
 * reaches the boundary and stops at an open node instead of closing on a gold
 * seal. Same drawing, opposite outcome — which is exactly what abstention is.
 */
function SeveredThread() {
  return (
    <svg viewBox="0 0 240 28" className="w-full max-w-[240px]" aria-hidden="true">
      <line x1="4" y1="14" x2="104" y2="14" stroke="#D9AE5F" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="104" y1="14" x2="150" y2="14" stroke="#D9AE5F" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="3 5" strokeOpacity="0.5" />
      <circle cx="4" cy="14" r="4" fill="#D9AE5F" />
      <circle cx="56" cy="14" r="4" fill="#D9AE5F" />
      <circle cx="104" cy="14" r="4" fill="#D9AE5F" />
      <circle cx="196" cy="14" r="5.5" fill="none" stroke="#D9AE5F" strokeWidth="1.4" strokeOpacity="0.45" strokeDasharray="2.5 3" />
      <line x1="168" y1="5" x2="176" y2="23" stroke="#FAF7EF" strokeWidth="1.2" strokeOpacity="0.35" strokeLinecap="round" />
      <line x1="176" y1="5" x2="168" y2="23" stroke="#FAF7EF" strokeWidth="1.2" strokeOpacity="0.35" strokeLinecap="round" />
    </svg>
  )
}

export default function EvidenceBoundary({ result, copy, onEscalate }) {
  const translationFailed = !result.translation_available && result.answer_language !== 'en'

  return (
    <div className="trust-panel p-5 sm:p-7 animate-in">
      <BotanicalCorner size={200} className="pointer-events-none absolute -right-8 -bottom-10 text-gold-light opacity-[0.1] scale-x-[-1]" />

      <div className="flex items-start gap-4">
        <span className="trust-seal">
          <ShieldAlert size={20} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <span className="trust-invariant mb-2.5">{copy.citationGrounded}</span>
          <p className="font-serif text-2xl text-paper leading-tight">{copy.evidenceBoundary}</p>
          <p className="text-sm text-paper/75 mt-2 leading-relaxed max-w-2xl">{result.answer || copy.evidenceBoundaryBody}</p>
        </div>
      </div>

      <div className="mt-6 sm:ml-[3.75rem]">
        <SeveredThread />
      </div>

      {translationFailed && (
        <p className="text-xs text-gold-light mt-4 sm:ml-[3.75rem]">
          {copy.translationUnavailableMessage}
        </p>
      )}

      <div className="mt-5 sm:ml-[3.75rem] pl-4 border-l border-gold/40">
        <p className="section-kicker text-gold-light mb-1.5">{copy.whyAbstained}</p>
        <p className="text-sm text-paper/70 max-w-2xl leading-relaxed">
          {result.classification?.needs_clarification
            ? result.classification.reason
            : copy.evidenceBoundaryReason}
        </p>
      </div>

      <div className="mt-6 sm:ml-[3.75rem]">
        <button
          onClick={onEscalate}
          className="press inline-flex items-center gap-1.5 px-4 py-2.5 bg-gold-light text-green-dark text-sm font-semibold rounded-md hover:bg-gold-pale shadow-[0_6px_16px_rgba(0,0,0,0.25)]"
        >
          <Send size={14} />
          {copy.escalate}
        </button>
      </div>
    </div>
  )
}
