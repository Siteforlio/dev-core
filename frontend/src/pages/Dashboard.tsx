import { useState } from 'react'
import { useAuthStore } from '../store/authStore'
import CompanySelector from '../components/interview/CompanySelector'

interface SessionContext {
  company: string
  role: string
  rounds: string[]
}

export default function Dashboard() {
  const name = useAuthStore((s) => s.name)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const [session, setSession] = useState<SessionContext | null>(null)

  if (session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
        <div className="text-center max-w-md">
          <h1 className="text-2xl font-bold mb-2">Session Ready</h1>
          <p className="text-gray-400 mb-1">
            <span className="text-white font-semibold">{session.company}</span> · {session.role}
          </p>
          <p className="text-sm text-gray-500 mb-6">
            Rounds: {session.rounds.join(', ') || 'HR, behavioral, technical'}
          </p>
          <p className="text-gray-500 text-sm">Interview engine coming in Task 5.</p>
          <button
            className="mt-6 text-sm text-gray-400 underline"
            onClick={() => setSession(null)}
          >
            ← Back
          </button>
        </div>
      </div>
    )
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
        <CompanySelector
          onSelect={(company, role, rounds) => setSession({ company, role, rounds })}
        />
      </main>
    </div>
  )
}
