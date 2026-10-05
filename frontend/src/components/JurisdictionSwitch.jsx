import { JurisdictionMark } from './JurisdictionMark'

/**
 * Jurisdiction selector.
 *
 * This is the highest-consequence control in the app — it decides which
 * corpus is searched and which body of law the answer is allowed to cite —
 * so it is built like a physical selector rather than a pair of tabs: a
 * recessed track with a single seal-green tab that slides between the two
 * positions. The movement is the point: you can see the system switch
 * regimes.
 *
 * The tab is exactly one option wide (width: calc(50% - 3px) against 3px of
 * track padding), so translateX(100%) lands it precisely on the second
 * option at any container width — no magic pixel offsets to re-tune when the
 * label text changes length between languages.
 */
export default function JurisdictionSwitch({ value, onChange, copy, showLabel = true }) {
  const isIndia = value === 'India'

  return (
    <div className="inline-flex items-center gap-2.5">
      {showLabel && (
        <span className="section-kicker hidden sm:inline shrink-0">{copy.jurisdiction}</span>
      )}
      <div className="jx-switch" role="group" aria-label={copy.jurisdiction}>
        <span
          className="jx-switch__tab"
          aria-hidden="true"
          style={{ transform: isIndia ? 'translateX(0)' : 'translateX(100%)' }}
        />
        <button
          type="button"
          onClick={() => onChange('India')}
          aria-pressed={isIndia}
          className="jx-option press"
        >
          <JurisdictionMark jurisdiction="India" />
          {copy.india}
        </button>
        <button
          type="button"
          onClick={() => onChange('International')}
          aria-pressed={!isIndia}
          className="jx-option press"
        >
          <JurisdictionMark jurisdiction="International" />
          {copy.international}
        </button>
      </div>
    </div>
  )
}
