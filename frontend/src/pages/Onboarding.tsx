import { useState } from 'react'
import { useAuthStore } from '../store/authStore'

export default function Onboarding({ onGoToLogin }: { onGoToLogin: () => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [lang, setLang] = useState('en')
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const setAuth = useAuthStore((s) => s.setAuth)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!consent) { setError('You must agree to data usage to continue.'); return }
    setError('')
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, language_pref: lang, consent_given: consent }),
      })
      const body = await res.json()
      if (!res.ok) {
        setError(body.error?.message ?? 'Registration failed')
        return
      }
      const { access_token, refresh_token, user_id, name: userName, language_pref } = body.data
      setAuth(access_token, refresh_token, user_id, userName, language_pref)
    } catch {
      setError('Could not reach the server. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 w-80">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onGoToLogin}
            className="text-gray-400 hover:text-white transition-colors"
            aria-label="Back to login"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold">Create Account</h1>
        </div>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <input
          className="bg-gray-800 p-2 rounded"
          placeholder="Full name"
          value={name}
          onChange={e => setName(e.target.value)}
          disabled={loading}
        />
        <input
          className="bg-gray-800 p-2 rounded"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          disabled={loading}
        />
        <input
          className="bg-gray-800 p-2 rounded"
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          disabled={loading}
        />
        <select
          className="bg-gray-800 p-2 rounded"
          value={lang}
          onChange={e => setLang(e.target.value)}
          disabled={loading}
        >
          <option value="en">English</option>
          <option value="sw">Swahili</option>
          <option value="es">Spanish</option>
          <option value="fr">French</option>
          <option value="pt">Portuguese</option>
        </select>
        <label className="flex items-start gap-2 text-sm text-gray-300 cursor-pointer">
          <input
            type="checkbox"
            checked={consent}
            onChange={e => setConsent(e.target.checked)}
            className="mt-1"
            disabled={loading}
          />
          I agree that my anonymized interview data may be used to improve the platform for all users.
        </label>
        <button
          className="bg-blue-600 p-2 rounded font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
          type="submit"
          disabled={loading}
        >
          {loading ? (
            <>
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Creating account…
            </>
          ) : 'Get Started'}
        </button>
        <button type="button" className="text-sm text-gray-400 underline" onClick={onGoToLogin}>
          Already have an account? Sign in
        </button>
      </form>
    </div>
  )
}
