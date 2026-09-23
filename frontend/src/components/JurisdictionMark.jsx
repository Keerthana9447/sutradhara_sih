import { Globe2 } from 'lucide-react'

/**
 * Replaces the 🇮🇳 / 🌍 emoji flags used earlier. A literal flag emoji
 * renders inconsistently across OS/browser combos (exactly the kind of
 * thing that looks unpolished projected on a judging-hall screen), and
 * doesn't fit the manuscript/seal visual language used everywhere else.
 *
 * India: a small tricolor bar (Ashoka Chakra abstracted as a center dot,
 * not reproduced in detail — this is a wordmark accent, not the state
 * emblem). International: lucide's Globe2 glyph, consistent with the
 * other line-icons already in use across the app.
 */
export function IndiaMark({ size = 14 }) {
  const h = size / 3.2
  return (
    <span
      className="inline-flex flex-col rounded-[1px] overflow-hidden ring-1 ring-black/10 align-middle"
      style={{ width: size * 1.5, height: size }}
      aria-hidden="true"
    >
      <span style={{ height: h, background: '#B8862E' }} />
      <span style={{ height: h, background: '#FAF7EF' }} className="relative">
        <span
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ width: h * 0.55, height: h * 0.55, background: '#1F3B2C' }}
        />
      </span>
      <span style={{ height: h, background: '#1F3B2C' }} />
    </span>
  )
}

export function JurisdictionMark({ jurisdiction, size = 14, className = '' }) {
  if (jurisdiction === 'India') {
    return <IndiaMark size={size} />
  }
  return <Globe2 size={size} className={className} strokeWidth={2.2} />
}
