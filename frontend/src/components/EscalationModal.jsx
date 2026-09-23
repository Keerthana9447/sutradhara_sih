import { useState } from 'react'
import { X, Send, CheckCircle2 } from 'lucide-react'
import { api } from '../api'
import { BotanicalCorner } from './Botanical'

export default function EscalationModal({ context, onClose, copy }) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle') // idle | sending | sent | error

  async function submit() {
    setStatus('sending')
    try {
      await api.escalate({
        query: context.query,
        product_category: context.category,
        jurisdiction: context.jurisdiction,
        relevant_ip_area: context.areas,
        retrieved_sources: context.sourceIds,
        contact_email: email || null,
      })
      setStatus('sent')
    } catch (e) {
      setStatus('error')
    }
  }

  return (
    <div className="fixed inset-0 bg-green-dark/65 backdrop-blur-[2px] flex items-center justify-center p-4 z-50 animate-in" role="dialog" aria-modal="true" aria-labelledby="escalation-title">
      <div className="dossier-panel relative overflow-hidden max-w-lg w-full p-6 sm:p-7 shadow-[0_28px_70px_rgba(13,33,23,0.38)] animate-in">
        <BotanicalCorner size={170} className="pointer-events-none absolute -right-10 -bottom-12 text-green opacity-[0.06] scale-x-[-1]" />
        <div className="relative flex items-start justify-between mb-1">
          <div><p className="section-kicker">{copy.reviewPathway}</p><h3 id="escalation-title" className="font-serif text-xl text-green-dark">{copy.escalateTitle}</h3></div>
          <button onClick={onClose} aria-label={copy.cancel} className="press text-ink/40 hover:text-ink/70 hover:bg-paper-dim rounded-md -mt-1 -mr-1 p-1.5">
            <X size={18} />
          </button>
        </div>
        <p className="relative text-sm text-ink/60 mb-4 max-w-[60ch]">
          {copy.escalationDescription}
        </p>

        {status === 'sent' ? (
          <div className="relative flex items-start gap-2.5 text-sm text-green bg-green-pale/60 border border-green/20 rounded-md p-4">
            <CheckCircle2 size={18} className="shrink-0 mt-0.5" />
            <span>{copy.escalationRecorded} {copy.escalationFollowUp}</span>
          </div>
        ) : (
          <>
            <div className="relative text-xs text-ink/70 space-y-2 mb-4 border border-hairline rounded-md p-4 bg-paper-dim/50 shadow-[inset_3px_0_0_rgba(184,134,46,0.55)]">
              <p><span className="font-medium">{copy.escalationFields.query}:</span> {context.query}</p>
              <p><span className="font-medium">{copy.escalationFields.category}:</span> {context.category || '—'}</p>
              <p><span className="font-medium">{copy.escalationFields.jurisdiction}:</span> {context.jurisdiction}</p>
              <p><span className="font-medium">{copy.escalationFields.areas}:</span> {(context.areas || []).join(', ') || '—'}</p>
              <p><span className="font-medium">{copy.escalationFields.sources}:</span> {(context.sourceIds || []).join(', ') || copy.noSources}</p>
            </div>
            <label className="block text-xs font-medium text-ink/70 mb-1">{copy.contactEmail}</label>
            <input
              className="research-input w-full border border-hairline rounded-md px-3 py-2 text-sm mb-1 focus:outline-none"
              placeholder={copy.emailPlaceholder}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {status === 'error' && (
              <p className="text-xs text-rust mt-1 mb-2">{copy.escalationError}</p>
            )}
            <div className="relative flex justify-end gap-2 mt-4">
              <button onClick={onClose} className="press px-3 py-2 text-sm text-ink/60 hover:text-ink hover:bg-paper-dim rounded-md">{copy.cancel}</button>
              <button
                onClick={submit}
                disabled={status === 'sending'}
                className="press inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-green text-paper rounded-md hover:bg-green-dark hover:-translate-y-0.5 disabled:opacity-60 shadow-panel"
              >
                <Send size={14} />
                {status === 'sending' ? copy.sending : copy.submit}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
