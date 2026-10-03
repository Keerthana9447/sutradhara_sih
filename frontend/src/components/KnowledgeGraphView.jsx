import { useEffect, useMemo, useState } from 'react'
import { Network, Loader2, Waypoints, GitBranch } from 'lucide-react'
import { api } from '../api'
import JurisdictionSwitch from './JurisdictionSwitch'
import { EmptyPlate, LeafSprig } from './Botanical'

const CATEGORIES = [
  'Classical / Generic Medicine',
  'Patent / Proprietary Medicine',
  'New / Non-Classical Drug',
  'Phytopharmaceutical',
  'Ayurveda-Aahar / Nutraceutical',
  'Cosmetic',
]

const TYPE_COLOR = {
  Product: '#1F3B2C',
  ProductCategory: '#1F3B2C',
  IPRegime: '#8F6A22',
  ExportIntent: '#A03E2A',
}
function colorFor(node) {
  if (node.type === 'Law') return node.source_id?.startsWith('INTL') ? '#A03E2A' : '#2E5940'
  return TYPE_COLOR[node.type] || '#8F6A22'
}

const COL_W = 260
const ROW_H = 72
const NODE_W = 158
const MARGIN = 50

// BFS layered layout: depth = hop count from the root ("n_product"), so the
// graph always lays out left-to-right in the same order it was reasoned —
// this is a real computed layout, not a fixed lookup table, because the
// shape of the tree changes with every category/jurisdiction/export choice.
function layoutGraph(nodes, edges) {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]))
  const children = {}
  edges.forEach((e) => { (children[e.from] ||= []).push(e.to) })

  const depth = {}
  const root = nodes.find((n) => n.type === 'Product')?.id || nodes[0]?.id
  const queue = root ? [[root, 0]] : []
  const seen = new Set()
  while (queue.length) {
    const [id, d] = queue.shift()
    if (seen.has(id)) continue
    seen.add(id)
    depth[id] = d
    ;(children[id] || []).forEach((c) => queue.push([c, d + 1]))
  }

  const levels = {}
  nodes.forEach((n) => {
    const d = depth[n.id] ?? 0
    ;(levels[d] ||= []).push(n.id)
  })

  const positions = {}
  const maxCount = Math.max(1, ...Object.values(levels).map((l) => l.length))
  const totalH = maxCount * ROW_H
  Object.entries(levels).forEach(([d, ids]) => {
    const levelH = ids.length * ROW_H
    const offset = (totalH - levelH) / 2
    ids.forEach((id, i) => {
      positions[id] = { x: MARGIN + Number(d) * COL_W, y: MARGIN + offset + i * ROW_H + ROW_H / 2 }
    })
  })

  const maxDepth = Math.max(0, ...Object.values(depth))
  return {
    positions,
    width: MARGIN * 2 + (maxDepth + 1) * COL_W,
    height: MARGIN * 2 + totalH,
  }
}

function wrapLabel(text, maxChars = 20, maxLines = 2) {
  const words = (text || '').split(' ')
  const allLines = []
  let current = ''
  for (const w of words) {
    const candidate = (current + ' ' + w).trim()
    if (candidate.length > maxChars && current) {
      allLines.push(current)
      current = w
    } else {
      current = candidate
    }
  }
  if (current) allLines.push(current)

  if (allLines.length <= maxLines) return allLines
  const shown = allLines.slice(0, maxLines)
  shown[shown.length - 1] = shown[shown.length - 1].replace(/\s*$/, '') + '…' // clean word boundary, never mid-word
  return shown
}

export default function KnowledgeGraphView({ copy, defaultCategory, defaultJurisdiction }) {
  const [category, setCategory] = useState(defaultCategory || CATEGORIES[0])
  const [jurisdiction, setJurisdiction] = useState(defaultJurisdiction || 'India')
  const [exportIntent, setExportIntent] = useState(false)
  const [graph, setGraph] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  async function run() {
    setLoading(true)
    setError(false)
    try {
      const res = await api.graphReason({ category, jurisdiction, export_intent: exportIntent })
      setGraph(res)
    } catch (e) {
      setError(true)
      setGraph(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { run() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const layout = useMemo(() => (graph ? layoutGraph(graph.nodes, graph.edges) : null), [graph])

  return (
    <div className="animate-in relative">
      <LeafSprig size={130} flip className="pointer-events-none absolute -right-6 -top-6 text-green opacity-[0.07] hidden lg:block" />
      <div className="relative flex items-start gap-3.5 mb-1">
        <span className="inline-flex items-center justify-center w-11 h-11 rounded-lg border border-green/15 bg-gradient-to-br from-green-pale to-green-pale/50 text-green shrink-0 mt-0.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
          <Waypoints size={18} strokeWidth={2.1} />
        </span>
        <div>
          <p className="section-kicker mb-1">{copy.graphKicker}</p>
          <h2 className="font-serif text-2xl sm:text-[1.75rem] text-green-dark leading-tight tracking-tight">{copy.graphTitle}</h2>
          <p className="text-sm text-ink/60 mt-1.5 max-w-[68ch] leading-relaxed">{copy.graphLede}</p>
        </div>
      </div>

      <div className="dossier-panel p-4 sm:p-5 mt-6 mb-6 border-green/20">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[220px]">
            <label className="block text-xs font-semibold text-ink/60 mb-1.5">{copy.graphCategoryLabel}</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full border border-hairline rounded-md px-3 py-2 text-sm bg-paper focus:outline-none focus:ring-1 focus:ring-green"
            >
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <JurisdictionSwitch value={jurisdiction} onChange={setJurisdiction} copy={copy} />
          <label className="inline-flex items-center gap-2 text-sm text-ink/70 select-none pb-2">
            <input type="checkbox" checked={exportIntent} onChange={(e) => setExportIntent(e.target.checked)} className="accent-green w-4 h-4" />
            {copy.graphExportIntentLabel}
          </label>
          <button
            onClick={run}
            disabled={loading}
            className="press inline-flex items-center gap-2 px-5 py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark disabled:opacity-60 shadow-panel"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {loading ? copy.working : copy.graphRunButton}
          </button>
        </div>
      </div>

      {error && (
        <div className="tool-empty mb-6">
          <EmptyPlate className="text-gold-dark opacity-70 shrink-0" />
          <p className="text-sm text-ink/55 max-w-sm leading-relaxed">{copy.graphEmpty}</p>
        </div>
      )}

      {graph && layout && (
        <div className="data-stage p-5 sm:p-6 animate-in">
          <div className="flex items-center gap-2 mb-1">
            <Network size={16} className="text-gold-light" />
            <div>
              <p className="section-kicker">{copy.graphGrounding}</p>
              <h3 className="font-serif text-xl text-green-dark">{graph.category} · {graph.jurisdiction}</h3>
            </div>
          </div>
          <p className="text-xs text-paper/65 mb-5 max-w-xl">{graph.note}</p>

          <div className="overflow-x-auto -mx-2 px-2 graph-scroll-container">
            <svg viewBox={`0 0 ${layout.width} ${layout.height}`} className="w-full h-auto min-w-[640px] drop-shadow-[0_6px_8px_rgba(20,42,31,0.08)]">
              <defs>
                <marker id="graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M0,0 L10,5 L0,10 z" fill="#B8862E" />
                </marker>
                <filter id="graph-node-shadow" x="-30%" y="-60%" width="160%" height="220%">
                  <feDropShadow dx="0" dy="1.5" stdDeviation="1.8" floodColor="#142A1F" floodOpacity="0.16" />
                </filter>
              </defs>

              {graph.edges.map((e, i) => {
                const from = layout.positions[e.from]
                const to = layout.positions[e.to]
                if (!from || !to) return null
                const startX = from.x + NODE_W / 2
                const endX = to.x - NODE_W / 2
                const midX = (startX + endX) / 2
                return (
                  <g key={i}>
                    <path
                      d={`M ${startX} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${endX} ${to.y}`}
                      fill="none" stroke="#B8AA82" strokeWidth="1.8" markerEnd="url(#graph-arrow)"
                    />
                    <path
                      className="graph-flow"
                      d={`M ${startX} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${endX} ${to.y}`}
                      style={{ animationDelay: `${(i % 6) * 0.45}s` }}
                    />
                    <g transform={`translate(${midX}, ${(from.y + to.y) / 2})`}>
                      <rect x={-e.label.length * 2.9 - 4} y={-8} width={e.label.length * 5.8 + 8} height={15} rx={7.5} fill="#FAF7EF" stroke="#EAE0C4" strokeWidth="0.75" />
                      <text fontSize="8.8" fill="#8F6A22" fontFamily="IBM Plex Mono, monospace" textAnchor="middle" dominantBaseline="middle" y={0.5}>
                        {e.label}
                      </text>
                    </g>
                  </g>
                )
              })}

              {graph.nodes.map((n) => {
                const pos = layout.positions[n.id]
                if (!pos) return null
                const lines = wrapLabel(n.label)
                const h = lines.length > 1 ? 48 : 36
                const color = colorFor(n)
                return (
                  <g key={n.id} className="graph-node">
                    <rect x={pos.x - NODE_W / 2} y={pos.y - h / 2} width={NODE_W} height={h} rx="7" fill="#FFFFFE" stroke={color} strokeWidth="1.4" filter="url(#graph-node-shadow)" />
                    <rect x={pos.x - NODE_W / 2} y={pos.y - h / 2} width="4" height={h} rx="2" fill={color} />
                    {lines.map((line, li) => (
                      <text
                        key={li} x={pos.x} y={pos.y - (lines.length - 1) * 6.5 + li * 13}
                        fontSize="10.5" fill="#1F3B2C" textAnchor="middle" dominantBaseline="middle"
                        fontFamily="IBM Plex Sans, sans-serif"
                      >
                        {line}
                      </text>
                    ))}
                  </g>
                )
              })}
            </svg>
          </div>
        </div>
      )}

      {graph && graph.steps?.length > 0 && (
        <div className="dossier-panel p-5 sm:p-6 mt-6 animate-in">
          <div className="flex items-center gap-2 mb-3">
            <GitBranch size={16} className="text-green" />
            <h3 className="font-serif text-lg text-green-dark">{copy.graphStepsTitle}</h3>
          </div>
          <ol className="space-y-2.5">
            {graph.steps.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-ink/80">
                <span className="citation-marker shrink-0 w-5 h-5 rounded-full bg-green-pale text-green text-[10px] flex items-center justify-center mt-0.5">{i + 1}</span>
                <span>{s.replace(/^Step( \d+)? — /, '').replace(/^Step \d+ — /, '')}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
