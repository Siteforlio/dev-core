import { useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { useInterviewSession } from '../hooks/useInterviewSession'
import CompanySelector from '../components/interview/CompanySelector'

export default function Dashboard() {
  const name = useAuthStore((s) => s.name)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const { startSession } = useInterviewSession()
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')

  const handleSelect = async (company: string, role: string, rounds: string[]) => {
    setStarting(true)
    setError('')
    try {
      await startSession(company, role, rounds.length > 0 ? rounds : ['HR', 'behavioral', 'technical'])
    } catch {
      setError('Failed to start session. Is the backend running?')
      setStarting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      <header className="flex items-center justify-between px-8 py-4 border-b border-gray-800">
        <span className="font-bold text-lg">Developer Core</span>
        <div className="flex items-center gap-4">
          <span className="text-gray-400 text-sm">{name}</span>
          <button
            className="text-sm text-gray-500 hover:text-white underline"
            onClick={clearAuth}
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex flex-1 items-center justify-center">
        {starting ? (
          <div className="text-gray-400 flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <span>Generating your interview session…</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <CompanySelector onSelect={handleSelect} />
          </div>
        )}
      </main>
    </div>
  )
}
