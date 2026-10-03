/**
 * Sign In page — matching the Sutradhara visual system (paper / green / gold).
 */
import { useState } from 'react'
import { LogIn, Eye, EyeOff } from 'lucide-react'
import Logo from './components/Logo'
import { BotanicalCorner, ManuscriptRule } from './components/Botanical'
import { api } from './api'
import { useAuth } from './AuthContext'

export default function SignIn({ onGoSignUp, onGoAdmin }) {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await api.signIn({ email, password })
      signIn(data)
    } catch (err) {
      setError(err.message || 'Invalid email or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      {/* Decorative corner */}
      <BotanicalCorner
        size={160}
        className="pointer-events-none fixed bottom-0 left-0 text-gold-light opacity-[0.07]"
      />

      <div className="w-full max-w-md">
        {/* Logo + title */}
        <div className="text-center mb-8">
          <span className="inline-flex items-center justify-center w-14 h-14 rounded-xl border border-gold-light/35 bg-green text-gold-light shadow-lg mb-4">
            <Logo size={28} />
          </span>
          <h1 className="font-serif text-3xl text-green-dark">Sutradhara</h1>
          <p className="text-sm text-ink/50 mt-1 tracking-wider uppercase citation-marker">
            IP Intelligence · Sign In
          </p>
        </div>

        <ManuscriptRule className="text-gold max-w-[180px] mx-auto mb-8" />

        {/* Card */}
        <div className="dossier-panel p-8">
          <h2 className="font-serif text-xl text-green-dark mb-6 flex items-center gap-2">
            <LogIn size={18} className="text-green" />
            Welcome back
          </h2>

          {error && (
            <div className="mb-4 px-4 py-3 rounded-md bg-rust/8 border border-rust/30 text-sm text-rust">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-ink/60 mb-1.5 uppercase tracking-wider">
                Email
              </label>
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-ink/60 mb-1.5 uppercase tracking-wider">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPwd ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="research-input w-full border border-hairline rounded-md px-4 py-2.5 pr-10 text-sm focus:outline-none"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPwd((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink/40 hover:text-ink/70"
                >
                  {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !email || !password}
              className="press w-full py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark disabled:opacity-50 shadow-[0_5px_14px_rgba(31,59,44,0.18)]"
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <p className="text-center text-sm text-ink/50 mt-6">
            Don&apos;t have an account?{' '}
            <button
              onClick={onGoSignUp}
              className="text-green underline underline-offset-2 hover:text-green-dark font-medium"
            >
              Create one
            </button>
          </p>
          {onGoAdmin && (
            <p className="text-center text-xs text-ink/35 mt-3">
              Ministry / Regulator?{' '}
              <button
                onClick={onGoAdmin}
                className="text-rust/70 underline underline-offset-2 hover:text-rust font-medium"
              >
                Admin portal →
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
