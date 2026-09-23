// Local dev: Vite proxies /api to FastAPI.
// Production: set VITE_API_URL to the Render backend URL.
const API_ORIGIN = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const BASE = `${API_ORIGIN}/api`

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json()
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json()
}

// Posture PDF returns a binary PDF, not JSON, and triggers a browser
// download rather than returning data to render — kept separate from
// post()/get() above rather than overloading them for one binary case.
async function downloadPosturePdf(body) {
  const res = await fetch(`${BASE}/posture-pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`posture-pdf failed: ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'sutradhara-ip-posture-summary.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  analyze: (payload) => post('/analyze', payload),
  graph: () => get('/graph'),
  graphReason: (payload) => post('/graph/reason', payload),
  escalate: (payload) => post('/escalate', payload),
  feedback: (payload) => post('/feedback', payload),
  evalSummary: () => get('/eval'),
  evalBenchmark: () => get('/eval/benchmark'),
  health: () => get('/health'),
  downloadPosturePdf,
  connectorLink: (payload) => post('/connectors/link', payload),
  connectorRevoke: (payload) => post('/connectors/revoke', payload),
  connectors: () => get('/connectors'),
  connectorUsage: (id) => get(`/connectors/${id}/usage`),
  transcribeAudio: (payload) => post('/asr/transcribe', payload),
  synthesizeSpeech: (payload) => post('/tts/synthesize', payload),
}
