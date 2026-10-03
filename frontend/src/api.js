// Local dev: Vite proxies /api to FastAPI.
// Production: set VITE_API_URL to the Render backend URL.
const API_ORIGIN = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const BASE = `${API_ORIGIN}/api`

// The backend derives who you are from this Bearer token, never from a
// user_id in the request. Attached ONLY to the account-scoped routes, so
// unrelated calls (translation, speech, retrieval) are sent exactly as before.
const AUTH_PATHS = ['/auth/signout', '/chat/', '/analyze/session', '/privacy/account', '/privacy/consent/', '/v1/']
function authHeaders(path) {
  if (!AUTH_PATHS.some((p) => path.startsWith(p))) return {}
  try {
    const raw = localStorage.getItem('sutradhara_auth')
    const token = raw ? JSON.parse(raw).token : null
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}

async function jsonOrThrow(res, path) {
  if (!res.ok) { const data = await res.json().catch(() => ({})); throw new Error(data.detail || `${path} failed: ${res.status}`) }
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(path) },
    body: JSON.stringify(body),
  })
  if (!res.ok) { const data = await res.json().catch(() => ({})); throw new Error(data.detail || `${path} failed: ${res.status}`) }
  return res.json()
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders(path) })
  if (!res.ok) { const data = await res.json().catch(() => ({})); throw new Error(data.detail || `${path} failed: ${res.status}`) }
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
  translateTexts: (texts, target_language, external_processing_consent) => post('/translate', { texts, target_language, external_processing_consent }),
  analyzeSession: (payload) => post('/analyze/session', payload),
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
  consentAccess: (id) => post(`/privacy/consent/${encodeURIComponent(id)}/access`, {}),
  transcribeAudio: (payload) => post('/asr/transcribe', payload),
  synthesizeSpeech: (payload) => post('/tts/synthesize', payload),

  // ── Auth ──────────────────────────────────────────────────────────────────
  signUp: (payload) => post('/auth/signup', payload),
  signIn: (payload) => post('/auth/signin', payload),
  signOut: () => post('/auth/signout', {}),

  // ── Chat history ──────────────────────────────────────────────────────────
  createChatSession: (userId, title) =>
    post('/chat/sessions', { user_id: userId, title }),
  getChatSessions: (userId) => get(`/chat/sessions/${userId}`),
  getChatMessages: (sessionId, userId) =>
    get(`/chat/sessions/${sessionId}/messages?user_id=${userId}`),
  renameChatSession: (sessionId, userId, title) =>
    fetch(`${BASE}/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders('/chat/') },
      body: JSON.stringify({ user_id: userId, title }),
    }).then((r) => jsonOrThrow(r, '/chat/sessions')),
  deleteChatSession: (sessionId, userId) =>
    fetch(`${BASE}/chat/sessions/${sessionId}?user_id=${userId}`, {
      method: 'DELETE',
      headers: authHeaders('/chat/'),
    }).then((r) => jsonOrThrow(r, '/chat/sessions')),

  // ── DPDP rights over your own account data ────────────────────────────────
  exportAccount: () => get('/privacy/account/export'),
  deleteAccount: () =>
    fetch(`${BASE}/privacy/account`, {
      method: 'DELETE',
      headers: authHeaders('/privacy/account'),
    }).then((r) => jsonOrThrow(r, '/privacy/account')),

  // ── New features ─────────────────────────────────────────────────────────
  // Auth me (includes role)
  getMe: () => get('/v1/auth/me'),

  // Claims workflow
  submitClaim: (payload) => post('/v1/claims', payload),
  listClaims: (status) => get(`/v1/claims${status ? `?status=${status}` : ''}`),
  getClaim: (id) => get(`/v1/claims/${encodeURIComponent(id)}`),
  verifyClaim: (id) => post(`/v1/claims/${id}/verify`, {}),
  anchorClaim: (id) => post(`/v1/claims/${id}/anchor`, {}),

  // OCR
  digitiseManuscript: (payload) => post('/v1/ocr', payload),

  // Patent Registry
  browseRegistry: (params) => {
    const q = new URLSearchParams(params).toString()
    return get(`/v1/patents${q ? `?${q}` : ''}`)
  },

  // Radar (admin)
  runRadar: (payload) => post('/v1/radar', payload),

  // Formulation dossiers (citizen)
  createDossier: (payload) => post('/v1/dossiers', payload),
  listDossiers: () => get('/v1/dossiers'),
  updateDossier: (id, payload) => fetch(`${BASE}/v1/dossiers/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders('/v1/') },
    body: JSON.stringify(payload),
  }).then((r) => jsonOrThrow(r, '/v1/dossiers')),
  classifyDossier: (id, payload = {}) => post(`/v1/dossiers/${encodeURIComponent(id)}/classify`, payload),
  mapDossier: (id) => post(`/v1/dossiers/${encodeURIComponent(id)}/map`, {}),
  reviewDossier: (id, payload = {}) => post(`/v1/dossiers/${encodeURIComponent(id)}/review`, payload),
  deleteDossier: (id) => fetch(`${BASE}/v1/dossiers/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: authHeaders('/v1/'),
  }).then((r) => jsonOrThrow(r, '/v1/dossiers')),

  // Prahari patent watchlist (citizen)
  createPrahariAlert: (payload) => post('/v1/prahari', payload),
  listPrahariAlerts: () => get('/v1/prahari'),
  deletePrahariAlert: (id) => fetch(`${BASE}/v1/prahari/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: authHeaders('/v1/'),
  }).then((r) => jsonOrThrow(r, '/v1/prahari')),

  // Admin signup
  adminSignUp: (payload) => post('/v1/auth/admin-signup', payload),

  // Legal pages
  legalRti: () => get('/v1/legal/rti'),
  legalTerms: () => get('/v1/legal/terms'),
  legalCopyright: () => get('/v1/legal/copyright'),
}
