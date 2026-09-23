/**
 * SUTRADHARA mark — "sutra" (thread) + "dhara" (holder/bearer).
 *
 * The mark is a single continuous thread looping through four beads,
 * echoing a japamala / knowledge-thread and, at the same time, tracing an
 * unbroken line from query to cited source — literally the product's job.
 * Deliberately not a generic sprout/leaf/shield icon: it's built from the
 * name's own meaning, not a stock "AI legal" glyph.
 *
 * Single-color (currentColor) so it works on both the deep-green header
 * (as paper) and the ivory background (as green-dark) without a second
 * asset.
 */
export default function Logo({ size = 32, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M8 12 C 8 8, 14 6, 20 10 C 26 14, 14 18, 20 22 C 26 26, 32 24, 32 28"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.55"
      />
      <circle cx="8" cy="12" r="3.1" fill="currentColor" />
      <circle cx="20" cy="10" r="2.1" fill="currentColor" opacity="0.85" />
      <circle cx="20" cy="22" r="2.1" fill="currentColor" opacity="0.85" />
      <circle cx="32" cy="28" r="3.1" fill="currentColor" />
    </svg>
  )
}
