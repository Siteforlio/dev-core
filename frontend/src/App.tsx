import { useState } from 'react'
import { useAuthStore } from './store/authStore'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'

export default function App() {
  const [showRegister, setShowRegister] = useState(false)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const name = useAuthStore((s) => s.name)

  if (isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-2">Welcome, {name}</h1>
          <p className="text-gray-400">Dashboard coming in Task 4.</p>
        </div>
      </div>
    )
  }

  if (showRegister) {
    return <Onboarding />
  }

  return <Login onGoToRegister={() => setShowRegister(true)} />
}
