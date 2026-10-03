import { useState } from "react"
import { Shield, Lock, Mail, ArrowRight, AlertTriangle } from "lucide-react"
import { useAuth } from "./AuthContext"
import { api } from "./api"
import Logo from "./components/Logo"

const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "")

export default function AdminSignIn({ onGoAdmin, onGoBack }) {
  const { signIn } = useAuth()
  const [mode, setMode] = useState("signin") // signin | signup
  const [form, setForm] = useState({ email: "", password: "", name: "", invite_code: "" })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSignIn(e) {
    e.preventDefault()
    setLoading(true); setError(null)
    try {
      const data = await api.signIn({ email: form.email, password: form.password })
      // Verify admin role
      const me = await fetch(`${API_ORIGIN}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${data.token}` }
      }).then(r => r.json())
      if (me.role !== "admin") {
        setError("This account does not have admin/ministry privileges.")
        return
      }
      signIn(data)
    } catch (e) {
      setError("Invalid credentials or not an admin account.")
    } finally {
      setLoading(false)
    }
  }

  async function handleSignUp(e) {
    e.preventDefault()
    setLoading(true); setError(null)
    try {
      const res = await fetch(`${API_ORIGIN}/api/v1/auth/admin-signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.email, name: form.name, password: form.password, invite_code: form.invite_code }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Sign-up failed")
      }
      const data = await res.json()
      signIn(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <span className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-gold-light/35 bg-green/10 text-gold-light shadow-inner">
            <Logo size={22} />
          </span>
          <div className="text-center">
            <h1 className="font-serif text-2xl text-green-dark">Sutradhara</h1>
            <p className="text-[11px] text-ink/40 tracking-[0.12em] uppercase">Ministry / Admin Portal</p>
          </div>
        </div>

        <div className="dossier-panel overflow-hidden">
          {/* Admin badge */}
          <div className="bg-rust/10 border-b border-rust/20 px-5 py-3 flex items-center gap-2.5">
            <Shield size={15} className="text-rust shrink-0" />
            <p className="text-sm text-rust font-medium">Ministry / Regulatory Admin Access</p>
          </div>

          {/* Tab toggle */}
          <div className="flex border-b border-hairline">
            {["signin", "signup"].map(m => (
              <button key={m} onClick={() => { setMode(m); setError(null) }}
                className={`flex-1 py-3 text-sm font-semibold ${mode === m ? "border-b-2 border-rust text-rust" : "text-ink/50 hover:text-ink"}`}>
                {m === "signin" ? "Sign In" : "Register Admin"}
              </button>
            ))}
          </div>

          <form onSubmit={mode === "signin" ? handleSignIn : handleSignUp} className="p-6 space-y-4">
            {mode === "signup" && (
              <div>
                <label className="block text-xs font-semibold text-ink/60 mb-1.5">Full Name</label>
                <input type="text" required value={form.name}
                  onChange={e => setForm(f => ({...f, name: e.target.value}))}
                  className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm"
                  placeholder="Ministry official name" />
              </div>
            )}
            <div>
              <label className="block text-xs font-semibold text-ink/60 mb-1.5">
                <Mail size={12} className="inline mr-1" />Email
              </label>
              <input type="email" required value={form.email}
                onChange={e => setForm(f => ({...f, email: e.target.value}))}
                className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm"
                placeholder="admin@ministry.gov.in" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink/60 mb-1.5">
                <Lock size={12} className="inline mr-1" />Password
              </label>
              <input type="password" required minLength={6} value={form.password}
                onChange={e => setForm(f => ({...f, password: e.target.value}))}
                className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm" />
            </div>
            {mode === "signup" && (
              <div>
                <label className="block text-xs font-semibold text-ink/60 mb-1.5">Admin Invite Code</label>
                <input type="password" required value={form.invite_code}
                  onChange={e => setForm(f => ({...f, invite_code: e.target.value}))}
                  className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm"
                  placeholder="Provided by ministry IT" />
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 p-3 bg-rust/5 border border-rust/30 rounded-md">
                <AlertTriangle size={14} className="text-rust shrink-0 mt-0.5" />
                <p className="text-sm text-rust">{error}</p>
              </div>
            )}

            <button type="submit" disabled={loading}
              className="press w-full inline-flex items-center justify-center gap-2 py-2.5 bg-rust text-paper font-semibold rounded-md hover:bg-rust/90 disabled:opacity-50 shadow-[0_5px_14px_rgba(160,62,42,0.2)]">
              {loading ? "Please wait..." : mode === "signin" ? "Sign In as Admin" : "Register Admin Account"}
              {!loading && <ArrowRight size={16} />}
            </button>

            <div className="text-center">
              <button type="button" onClick={onGoBack}
                className="text-xs text-ink/50 hover:text-ink underline underline-offset-2">
                ? Back to citizen portal
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
