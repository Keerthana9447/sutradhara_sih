/**
 * ChatHistory sidebar — shows past chat sessions for the signed-in user,
 * lets them switch sessions, rename, delete, and start a new one.
 */
import { useEffect, useState, useCallback } from 'react'
import {
  MessageSquare,
  Plus,
  Trash2,
  Pencil,
  Check,
  X,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { api } from '../api'

export default function ChatHistory({
  userId,
  activeSessionId,
  onSelectSession,
  onNewSession,
}) {
  const [sessions, setSessions] = useState([])
  const [collapsed, setCollapsed] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')

  const load = useCallback(async () => {
    if (!userId) return
    try {
      const data = await api.getChatSessions(userId)
      setSessions(data)
    } catch {
      /* ignore */
    }
  }, [userId])

  useEffect(() => {
    load()
  }, [load, activeSessionId])

  async function handleDelete(e, sessionId) {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return
    try {
      await api.deleteChatSession(sessionId, userId)
      if (activeSessionId === sessionId) onNewSession()
      load()
    } catch {
      alert('Could not delete session.')
    }
  }

  async function handleRename(sessionId) {
    if (!editTitle.trim()) {
      setEditingId(null)
      return
    }
    try {
      await api.renameChatSession(sessionId, userId, editTitle.trim())
      load()
    } catch {
      /* ignore */
    }
    setEditingId(null)
  }

  function startEdit(e, session) {
    e.stopPropagation()
    setEditingId(session.id)
    setEditTitle(session.title)
  }

  function formatDate(iso) {
    const d = new Date(iso)
    const now = new Date()
    const diffDays = Math.floor((now - d) / 86400000)
    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
  }

  // Group sessions by relative date label
  const grouped = sessions.reduce((acc, s) => {
    const label = formatDate(s.updated_at)
    if (!acc[label]) acc[label] = []
    acc[label].push(s)
    return acc
  }, {})

  return (
    <aside
      className={`chat-history relative flex-shrink-0 h-full transition-all duration-300 ${
        collapsed ? 'w-10 chat-history--collapsed' : 'w-64 chat-history--expanded'
      } border-r border-hairline bg-paper/60 flex flex-col`}
      style={{ minHeight: 0 }}
    >
      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand history' : 'Collapse history'}
        className="absolute -right-3 top-5 z-10 w-6 h-6 rounded-full border border-hairline bg-paper shadow flex items-center justify-center text-ink/40 hover:text-green hover:border-green"
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>

      {!collapsed && (
        <>
          {/* Header */}
          <div className="px-4 py-4 border-b border-hairline flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm font-semibold text-green-dark">
              <MessageSquare size={14} className="text-green" />
              History
            </span>
            <button
              onClick={onNewSession}
              title="New conversation"
              className="press p-1.5 rounded-md border border-green/30 text-green hover:bg-green hover:text-paper text-xs flex items-center gap-1"
            >
              <Plus size={13} />
            </button>
          </div>

          {/* Session list */}
          <div className="flex-1 overflow-y-auto py-2">
            {sessions.length === 0 && (
              <p className="text-xs text-ink/40 text-center mt-8 px-4">
                No conversations yet.
                <br />
                Start a new analysis!
              </p>
            )}

            {Object.entries(grouped).map(([label, group]) => (
              <div key={label}>
                <p className="citation-marker text-[10px] text-ink/35 px-4 pt-3 pb-1 uppercase tracking-widest">
                  {label}
                </p>
                {group.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => onSelectSession(session.id)}
                    className={`group cursor-pointer mx-2 mb-0.5 rounded-md px-3 py-2.5 flex items-start gap-2 transition-colors ${
                      activeSessionId === session.id
                        ? 'bg-green text-paper'
                        : 'hover:bg-green-pale text-ink/75 hover:text-ink'
                    }`}
                  >
                    <MessageSquare
                      size={13}
                      className={`mt-0.5 shrink-0 ${
                        activeSessionId === session.id
                          ? 'text-gold-light'
                          : 'text-green/60'
                      }`}
                    />

                    <div className="flex-1 min-w-0">
                      {editingId === session.id ? (
                        <div
                          className="flex items-center gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            autoFocus
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleRename(session.id)
                              if (e.key === 'Escape') setEditingId(null)
                            }}
                            className="w-full text-xs bg-paper text-ink border border-green/40 rounded px-1.5 py-0.5 focus:outline-none"
                          />
                          <button
                            onClick={() => handleRename(session.id)}
                            className="text-green hover:text-green-dark"
                          >
                            <Check size={12} />
                          </button>
                          <button
                            onClick={() => setEditingId(null)}
                            className="text-ink/40"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ) : (
                        <p className="text-xs font-medium truncate leading-snug">
                          {session.title}
                        </p>
                      )}
                    </div>

                    {editingId !== session.id && (
                      <span className="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => startEdit(e, session)}
                          title="Rename"
                          className={`p-0.5 rounded hover:text-green ${
                            activeSessionId === session.id
                              ? 'text-paper/60'
                              : 'text-ink/30'
                          }`}
                        >
                          <Pencil size={11} />
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, session.id)}
                          title="Delete"
                          className={`p-0.5 rounded hover:text-rust ${
                            activeSessionId === session.id
                              ? 'text-paper/60'
                              : 'text-ink/30'
                          }`}
                        >
                          <Trash2 size={11} />
                        </button>
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  )
}
