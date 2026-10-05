import { useState } from "react"
import { Shield, Lock, Mail, ArrowRight, AlertTriangle } from "lucide-react"
import { useAuth } from "./AuthContext"
import { api } from "./api"
import Logo from "./components/Logo"
import { ADMIN_LANGUAGES, getAdminCopy } from "./adminCopy"

const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "")

export default function AdminSignIn({ onGoAdmin, onGoBack, language = "en", onLanguageChange = () => {} }) {
  const { signIn } = useAuth()
  const copy = getAdminCopy(language)
  const languageLabels = {
    en: copy.languageEnglish,
    te: copy.languageTelugu,
    hi: copy.languageHindi,
    ta: copy.languageTamil,
    ml: copy.languageMalayalam,
    sa: copy.languageSanskrit,
  }
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
      const meResponse = await fetch(`${API_ORIGIN}/api/v1/auth/me`, {
        headers: {
          Authorization: `Bearer ${data.token}`,
        },
      })
      if (!meResponse.ok) throw new Error("Could not verify admin role.")
      const me = await meResponse.json()
      if (me.role !== "admin") {
        setError(copy.notAdmin)
        return
      }
      signIn(data)
    } catch (e) {
      setError(copy.signInFailed)
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
        setError(res.status === 503 ? copy.signupDisabled : copy.signupFailed)
        return
      }
      const data = await res.json()
      signIn(data)
    } catch {
      setError(copy.requestFailed)
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
            <p className="text-[11px] text-ink/40 tracking-[0.12em] uppercase">{copy.ministryPortal}</p>
          </div>
        </div>

        <div role="group" className="flex flex-wrap justify-center gap-1 mb-4" aria-label={copy.languageLabel}>
          {ADMIN_LANGUAGES.map(code => (
            <button key={code} type="button" aria-pressed={language === code}
              onClick={() => onLanguageChange(code)}
              className={`press rounded px-2 py-1 text-xs ${language === code ? "bg-green text-paper" : "text-ink/60 hover:bg-green/10"}`}>
              {languageLabels[code]}
            </button>
          ))}
        </div>

        <div className="dossier-panel overflow-hidden">
          {/* Admin badge */}
          <div className="bg-rust/10 border-b border-rust/20 px-5 py-3 flex items-center gap-2.5">
            <Shield size={15} className="text-rust shrink-0" />
            <p className="text-sm text-rust font-medium">{copy.accessTitle}</p>
          </div>

          {/* Tab toggle */}
          <div className="flex border-b border-hairline">
            {["signin", "signup"].map(m => (
              <button key={m} onClick={() => { setMode(m); setError(null) }}
                className={`flex-1 py-3 text-sm font-semibold ${mode === m ? "border-b-2 border-rust text-rust" : "text-ink/50 hover:text-ink"}`}>
              {m === "signin" ? copy.signIn : copy.registerAdmin}
              </button>
            ))}
          </div>

          <form onSubmit={mode === "signin" ? handleSignIn : handleSignUp} className="p-6 space-y-4">
            {mode === "signup" && (
              <div>
                <label className="block text-xs font-semibold text-ink/60 mb-1.5">{copy.fullName}</label>
                <input type="text" required value={form.name}
                  onChange={e => setForm(f => ({...f, name: e.target.value}))}
                  className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm"
                  placeholder={copy.namePlaceholder} />
              </div>
            )}
            <div>
              <label className="block text-xs font-semibold text-ink/60 mb-1.5">
                <Mail size={12} className="inline mr-1" />{copy.email}
              </label>
              <input type="email" required value={form.email}
                onChange={e => setForm(f => ({...f, email: e.target.value}))}
                className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm"
                placeholder={copy.emailPlaceholder} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink/60 mb-1.5">
                <Lock size={12} className="inline mr-1" />{copy.password}
              </label>
              <input type="password" required minLength={6} value={form.password}
                onChange={e => setForm(f => ({...f, password: e.target.value}))}
                className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm" />
            </div>
            {mode === "signup" && (
              <div>
                <label className="block text-xs font-semibold text-ink/60 mb-1.5">{copy.inviteCode}</label>
                <input type="password" required value={form.invite_code}
                  onChange={e => setForm(f => ({...f, invite_code: e.target.value}))}
                  className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm"
                  placeholder={copy.invitePlaceholder} />
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
              {loading ? copy.pleaseWait : mode === "signin" ? copy.signInAsAdmin : copy.registerAdminAccount}
              {!loading && <ArrowRight size={16} />}
            </button>

            <div className="text-center">
              <button type="button" onClick={onGoBack}
                className="text-xs text-ink/50 hover:text-ink underline underline-offset-2">
                {copy.backToCitizen}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
