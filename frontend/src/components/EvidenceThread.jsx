import { stageIcon } from './DomainIcons'

/**
 * The evidence thread: Product → Classification → IP → Regulation → Evidence.
 *
 * This is the product's actual pipeline, not an illustration of a generic AI
 * system, so it gets the hero. A single gold rail runs through five seed-nodes
 * with a pulse travelling along it; each node's halo lights as the pulse
 * reaches it, and the run terminates in a gold seal at Evidence — because
 * landing on a citation is the whole point of the system.
 *
 * Motion is CSS-only (see .thread__rail / .thread-node in index.css) and stops
 * entirely under prefers-reduced-motion, leaving a perfectly legible static
 * diagram. Labels come from COPY so the stages translate with the rest of the
 * UI; the English fallback keeps the hero intact if a language pack is missing
 * the key.
 */
const FALLBACK_STAGES = ['Product', 'Classification', 'IP', 'Regulation', 'Evidence']

export default function EvidenceThread({ copy }) {
  const stages = copy?.pipeline?.length === 5 ? copy.pipeline : FALLBACK_STAGES

  return (
    <div className="thread">
      <div className="thread__track">
        <span className="thread__rail" aria-hidden="true" />
        <ol className="thread__stages">
          {stages.map((label, index) => {
            const Icon = stageIcon(index)
            const terminal = index === stages.length - 1
            return (
              <li
                key={index}
                className={`thread-stage${terminal ? ' thread-stage--terminal' : ''}`}
                style={{ '--i': index }}
              >
                <span className="thread-node">
                  <Icon size={19} strokeWidth={1.8} />
                </span>
                <span className="thread-stage__text">
                  <span className="thread-index">{String(index + 1).padStart(2, '0')}</span>
                  <span className="thread-label">{label}</span>
                </span>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
