import { useState } from 'react'
import { useAuthStore } from './store/authStore'
import { useInterviewStore } from './store/interviewStore'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import InterviewSession from './components/interview/InterviewSession'

export default function App() {
  const [showRegister, setShowRegister] = useState(false)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const token = useAuthStore((s) => s.accessToken)
  const sessionId = useInterviewStore((s) => s.sessionId)

  if (!isAuthenticated) {
    if (showRegister) return <Onboarding onGoToLogin={() => setShowRegister(false)} />
    return <Login onGoToRegister={() => setShowRegister(true)} />
  }

  if (sessionId) return <InterviewSession token={token ?? ''} />

  return <Dashboard />
}
