import { useState } from 'react'
import { useAuthStore } from '../store/authStore'

export default function Login({ onGoToRegister }: { onGoToRegister: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const setAuth = useAuthStore((s) => s.setAuth)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const res = await fetch('http://localhost:8000/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    const body = await res.json()
    if (!res.ok) { setError(body.error?.message ?? 'Login failed'); return }
    const { access_token, user_id, name, language_pref } = body.data
    setAuth(access_token, user_id, name, language_pref)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 w-80">
        <h1 className="text-2xl font-bold">Developer Core</h1>
        {error && <p className="text-red-400 text-sm">{error}</p>}
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
        <button className="bg-blue-600 p-2 rounded font-semibold" type="submit">Sign In</button>
        <button type="button" className="text-sm text-gray-400 underline" onClick={onGoToRegister}>
          Create account
        </button>
      </form>
    </div>
  )
}
