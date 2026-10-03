/**
 * Ambient knowledge field — the page's background.
 *
 * A sparse constellation of seed-nodes joined by dashed stems, with a few
 * leaves growing off the joins. It is the same vine/graph drawing used
 * everywhere else, just held at very low opacity behind the content.
 *
 * Implementation notes, because "background particles" is usually where a
 * demo starts dropping frames: this is ONE static SVG animated entirely in
 * CSS. There is no canvas, no requestAnimationFrame loop, no resize handler
 * and no per-particle state — the browser compositor handles it, the React
 * tree never re-renders it (hence React.memo), and it disappears completely
 * under prefers-reduced-motion. The node/edge coordinates below are fixed
 * rather than random so the composition is designed, not rolled.
 */
import { memo } from 'react'

// Laid out across a 1440x900 field, deliberately spread to the margins so the
// densest reading column down the middle stays quiet.
const NODES = [
  [72, 118], [196, 248], [88, 432], [214, 566], [96, 726], [248, 842],
  [388, 96], [566, 214], [712, 62], [654, 396], [536, 690], [830, 860],
  [946, 122], [1082, 300], [1004, 548], [1168, 690], [1290, 168],
  [1372, 412], [1246, 828], [1392, 662],
]

const EDGES = [
  [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [1, 6], [6, 7], [7, 8],
  [7, 9], [9, 10], [10, 5], [10, 11], [8, 12], [12, 13], [13, 9],
  [13, 14], [14, 15], [15, 11], [12, 16], [16, 17], [17, 15], [17, 19],
  [19, 18], [18, 15],
]

// Leaves sit on a handful of joins only — a vine, not a hedge.
const LEAVES = [
  [196, 248, -34, 1.5], [654, 396, 18, 1.8], [1082, 300, -52, 1.6],
  [214, 566, 142, 1.3], [1004, 548, 28, 1.5], [712, 62, 96, 1.2],
  [1290, 168, -18, 1.4], [536, 690, -74, 1.4],
]

const MOTES = [
  [310, 330, 0], [880, 210, 5], [1200, 520, 9], [470, 780, 3], [1330, 300, 7], [660, 560, 12],
]

const LEAF_D = 'M0 0 C 9 -8.5, 24 -7, 33 0 C 24 7, 9 8.5, 0 0 Z'

function AmbientField() {
  return (
    <div className="ambient-field" aria-hidden="true">
      <svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        {EDGES.map(([a, b]) => {
          const [x1, y1] = NODES[a]
          const [x2, y2] = NODES[b]
          // Bow each stem slightly perpendicular to its run so the network
          // grows like a plant rather than reading as a wireframe mesh.
          const mx = (x1 + x2) / 2 + (y2 - y1) * 0.12
          const my = (y1 + y2) / 2 - (x2 - x1) * 0.12
          return (
            <path
              key={`${a}-${b}`}
              className="ambient-edge"
              d={`M${x1} ${y1} Q ${mx.toFixed(1)} ${my.toFixed(1)} ${x2} ${y2}`}
              style={{ animationDelay: `${(a * 0.7) % 6}s` }}
            />
          )
        })}

        {LEAVES.map(([x, y, r, s], i) => (
          <path
            key={`leaf-${i}`}
            className="ambient-leaf"
            d={LEAF_D}
            transform={`translate(${x} ${y}) rotate(${r}) scale(${s})`}
          />
        ))}

        {NODES.map(([cx, cy], i) => (
          <circle
            key={`node-${i}`}
            className={`ambient-node${i % 5 === 0 ? ' ambient-node--gold' : ''}`}
            cx={cx}
            cy={cy}
            r={i % 4 === 0 ? 3.6 : 2.4}
            style={{ animationDelay: `${(i * 0.53) % 7}s` }}
          />
        ))}

        {MOTES.map(([cx, cy, d], i) => (
          <circle key={`mote-${i}`} className="ambient-mote" cx={cx} cy={cy} r="1.8" style={{ animationDelay: `${d}s` }} />
        ))}
      </svg>
    </div>
  )
}

export default memo(AmbientField)
