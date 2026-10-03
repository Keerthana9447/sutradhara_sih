/**
 * Sign Up page — matching the Sutradhara visual system (paper / green / gold).
 */
import { useState } from 'react'
import { UserPlus, Eye, EyeOff } from 'lucide-react'
import Logo from './components/Logo'
import { BotanicalCorner, ManuscriptRule } from './components/Botanical'
import { api } from './api'
import { useAuth } from './AuthContext'

export default function SignUp({ onGoSignIn }) {
  const { signIn } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    try {
      const data = await api.signUp({ name, email, password })
      signIn(data)
    } catch (err) {
      setError(err.message || 'Could not create account. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <BotanicalCorner
        size={160}
        className="pointer-events-none fixed bottom-0 right-0 text-gold-light opacity-[0.07]"
      />

      <div className="w-full max-w-md">
        {/* Logo + title */}
        <div className="text-center mb-8">
          <span className="inline-flex items-center justify-center w-14 h-14 rounded-xl border border-gold-light/35 bg-green text-gold-light shadow-lg mb-4">
            <Logo size={28} />
          </span>
          <h1 className="font-serif text-3xl text-green-dark">Sutradhara</h1>
          <p className="text-sm text-ink/50 mt-1 tracking-wider uppercase citation-marker">
            IP Intelligence · Create Account
          </p>
        </div>

        <ManuscriptRule className="text-gold max-w-[180px] mx-auto mb-8" />

        {/* Card */}
        <div className="dossier-panel p-8">
          <h2 className="font-serif text-xl text-green-dark mb-6 flex items-center gap-2">
            <UserPlus size={18} className="text-green" />
            Create your account
          </h2>

          {error && (
            <div className="mb-4 px-4 py-3 rounded-md bg-rust/8 border border-rust/30 text-sm text-rust">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-ink/60 mb-1.5 uppercase tracking-wider">
                Full Name
              </label>
              <input
                type="text"
                autoComplete="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm focus:outline-none"
              />
            </div>

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
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 6 characters"
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

            <div>
              <label className="block text-xs font-semibold text-ink/60 mb-1.5 uppercase tracking-wider">
                Confirm Password
              </label>
              <input
                type={showPwd ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Repeat password"
                className="research-input w-full border border-hairline rounded-md px-4 py-2.5 text-sm focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !name || !email || !password || !confirm}
              className="press w-full py-2.5 bg-green text-paper text-sm font-semibold rounded-md hover:bg-green-dark disabled:opacity-50 shadow-[0_5px_14px_rgba(31,59,44,0.18)]"
            >
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="text-center text-sm text-ink/50 mt-6">
            Already have an account?{' '}
            <button
              onClick={onGoSignIn}
              className="text-green underline underline-offset-2 hover:text-green-dark font-medium"
            >
              Sign in
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
