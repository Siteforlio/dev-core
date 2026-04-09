import { useState } from 'react'
import { useAuthStore } from './store/authStore'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'

export default function App() {
  const [showRegister, setShowRegister] = useState(false)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  if (isAuthenticated) {
    return <Dashboard />
  }

  if (showRegister) {
    return <Onboarding />
  }

  return <Login onGoToRegister={() => setShowRegister(true)} />
}
