import { useState } from 'react'
import { useAuthStore } from '../store/authStore'

export default function Onboarding() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [lang, setLang] = useState('en')
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState('')
  const setAuth = useAuthStore((s) => s.setAuth)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!consent) { setError('You must agree to data usage to continue.'); return }
    setError('')
    const res = await fetch('http://localhost:8000/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password, language_pref: lang, consent_given: consent }),
    })
    const body = await res.json()
    if (!res.ok) { setError(body.error?.message ?? 'Registration failed'); return }
    const { access_token, user_id, name: userName, language_pref } = body.data
    setAuth(access_token, user_id, userName, language_pref)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 w-80">
        <h1 className="text-2xl font-bold">Create Account</h1>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <input
          className="bg-gray-800 p-2 rounded"
          placeholder="Full name"
          value={name}
          onChange={e => setName(e.target.value)}
        />
        <input
          className="bg-gray-800 p-2 rounded"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
        />
        <input
          className="bg-gray-800 p-2 rounded"
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
        />
        <select className="bg-gray-800 p-2 rounded" value={lang} onChange={e => setLang(e.target.value)}>
          <option value="en">English</option>
          <option value="sw">Swahili</option>
          <option value="es">Spanish</option>
          <option value="fr">French</option>
          <option value="pt">Portuguese</option>
        </select>
        <label className="flex items-start gap-2 text-sm text-gray-300">
          <input
            type="checkbox"
            checked={consent}
            onChange={e => setConsent(e.target.checked)}
            className="mt-1"
          />
          I agree that my anonymized interview data may be used to improve the platform for all users.
        </label>
        <button className="bg-blue-600 p-2 rounded font-semibold" type="submit">Get Started</button>
      </form>
    </div>
  )
}
