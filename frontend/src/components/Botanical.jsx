/**
 * Botanical ornament set.
 *
 * Everything here is drawn with the SAME stroke language as Logo.jsx — a thin
 * continuous thread through round seed-nodes. That is deliberate: in this
 * product the "knowledge network" and the "Ayurvedic plant" are not two
 * separate decorations bolted together, they're one drawing. Stems are edges,
 * seeds are nodes. A leaf growing off a graph edge is the whole thesis of the
 * app in one mark.
 *
 * All shapes use currentColor and are aria-hidden — they carry no information
 * and must never be read out or depended on for meaning.
 */

// A single lanceolate leaf in local coordinates: base at (0,0), tip at (34,0).
// Reused at different scales/rotations rather than redrawn per instance, so
// every leaf in the app is demonstrably the same leaf.
const LEAF_D = 'M0 0 C 9 -8.5, 24 -7, 33 0 C 24 7, 9 8.5, 0 0 Z'
const MIDRIB_D = 'M2.5 0 L 29 0'

function Leaf({ x, y, rotate, scale = 1, fillOpacity = 0.16 }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${rotate}) scale(${scale})`}>
      <path d={LEAF_D} fill="currentColor" fillOpacity={fillOpacity} stroke="currentColor" strokeWidth={1.1 / scale} strokeLinejoin="round" />
      <path d={MIDRIB_D} stroke="currentColor" strokeWidth={0.8 / scale} strokeOpacity="0.55" fill="none" strokeLinecap="round" />
    </g>
  )
}

/**
 * Upright sprig — an ashwagandha-like stem with alternating leaves and a
 * seed-node at each leaf axil. Used as a quiet margin ornament.
 */
export function LeafSprig({ size = 120, className = '', flip = false }) {
  return (
    <svg
      width={size}
      height={size * 1.34}
      viewBox="0 0 120 160"
      fill="none"
      className={className}
      aria-hidden="true"
      style={flip ? { transform: 'scaleX(-1)' } : undefined}
    >
      <path
        d="M60 158 C 56 128, 70 108, 58 82 C 48 60, 64 36, 58 6"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
      />
      <Leaf x={61} y={132} rotate={-28} scale={0.95} />
      <Leaf x={62} y={110} rotate={22} scale={0.8} />
      <Leaf x={59} y={110} rotate={158} scale={0.86} />
      <Leaf x={57} y={84} rotate={-34} scale={1.05} />
      <Leaf x={55} y={84} rotate={204} scale={0.78} />
      <Leaf x={57} y={58} rotate={26} scale={0.92} />
      <Leaf x={55} y={58} rotate={162} scale={0.7} />
      <Leaf x={60} y={32} rotate={-30} scale={0.8} />
      <Leaf x={58} y={14} rotate={196} scale={0.64} />
      {[[60, 132], [60, 110], [56, 84], [56, 58], [59, 32]].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.1" fill="currentColor" fillOpacity="0.7" />
      ))}
      <circle cx="58" cy="6" r="3" fill="currentColor" fillOpacity="0.5" />
    </svg>
  )
}

/**
 * Corner flourish — a vine that also reads as a graph branch: one trunk edge
 * splitting into three, nodes at every junction, leaves on the outer runs.
 * Anchored to a panel corner at low opacity.
 */
export function BotanicalCorner({ size = 180, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 180 180" fill="none" className={className} aria-hidden="true">
      <g stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round">
        <path d="M6 174 C 34 166, 52 148, 62 120" />
        <path d="M62 120 C 74 96, 96 86, 124 84" />
        <path d="M62 120 C 68 92, 62 66, 42 44" />
        <path d="M124 84 C 146 82, 160 68, 168 44" />
        <path d="M124 84 C 138 100, 142 122, 136 146" />
      </g>
      <Leaf x={70} y={104} rotate={-42} scale={0.9} />
      <Leaf x={96} y={88} rotate={-14} scale={1} />
      <Leaf x={58} y={92} rotate={-96} scale={0.82} />
      <Leaf x={52} y={66} rotate={-120} scale={0.74} />
      <Leaf x={132} y={104} rotate={58} scale={0.8} />
      <Leaf x={146} y={74} rotate={-34} scale={0.76} />
      {[[62, 120], [124, 84], [42, 44], [168, 44], [136, 146]].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.6" fill="currentColor" fillOpacity="0.75" />
      ))}
    </svg>
  )
}

/**
 * Manuscript rule — a hairline with a small seed lozenge at its centre, the
 * way a folio separates sections. Used instead of a plain <hr> so section
 * breaks carry the same hand as everything else.
 */
export function ManuscriptRule({ className = '' }) {
  return (
    <svg viewBox="0 0 300 12" preserveAspectRatio="none" className={className} aria-hidden="true" style={{ width: '100%', height: 12, display: 'block' }}>
      <line x1="0" y1="6" x2="128" y2="6" stroke="currentColor" strokeWidth="1" strokeOpacity="0.32" />
      <line x1="172" y1="6" x2="300" y2="6" stroke="currentColor" strokeWidth="1" strokeOpacity="0.32" />
      <path d="M150 0.5 C 157 3.5, 157 8.5, 150 11.5 C 143 8.5, 143 3.5, 150 0.5 Z" fill="currentColor" fillOpacity="0.5" />
      <circle cx="136" cy="6" r="1.4" fill="currentColor" fillOpacity="0.45" />
      <circle cx="164" cy="6" r="1.4" fill="currentColor" fillOpacity="0.45" />
    </svg>
  )
}

/**
 * Empty-state plate — a folio page with a sprig growing out of it. Stands in
 * where a panel has nothing to show yet, so an empty screen still looks
 * composed rather than unfinished.
 */
export function EmptyPlate({ className = '' }) {
  return (
    <svg width="104" height="112" viewBox="0 0 104 112" fill="none" className={className} aria-hidden="true">
      <rect x="18.5" y="14.5" width="62" height="84" rx="3" fill="currentColor" fillOpacity="0.05" stroke="currentColor" strokeOpacity="0.4" />
      <path d="M12 22 L 12 104 L 74 104" stroke="currentColor" strokeOpacity="0.22" strokeWidth="1" fill="none" />
      {[30, 40, 50, 60].map((y) => (
        <line key={y} x1="29" y1={y} x2={y === 60 ? 58 : 70} y2={y} stroke="currentColor" strokeOpacity="0.22" strokeWidth="3" strokeLinecap="round" />
      ))}
      <path d="M49 96 C 47 82, 56 76, 52 66 C 49 58, 55 50, 53 42" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none" />
      <Leaf x={53} y={72} rotate={-36} scale={0.72} fillOpacity={0.14} />
      <Leaf x={51} y={72} rotate={206} scale={0.6} fillOpacity={0.14} />
      <Leaf x={53} y={52} rotate={28} scale={0.64} fillOpacity={0.14} />
      <circle cx="53" cy="42" r="2.6" fill="currentColor" fillOpacity="0.6" />
    </svg>
  )
}
