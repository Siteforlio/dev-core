import { useState } from 'react'
import { useAuthStore } from './store/authStore'
import { useInterviewStore } from './store/interviewStore'
import SplashScreen from './pages/SplashScreen'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import InterviewSession from './components/interview/InterviewSession'

type Screen = 'splash' | 'login' | 'register' | 'dashboard'

export default function App() {
  const [screen, setScreen] = useState<Screen>('splash')
  const token     = useAuthStore((s) => s.accessToken)
  const sessionId = useInterviewStore((s) => s.sessionId)

  /* Splash → login or dashboard */
  const handleSplashDone = (authenticated: boolean) => {
    setScreen(authenticated ? 'dashboard' : 'login')
  }

  /* Login success → dashboard */
  const handleLoggedIn = () => setScreen('dashboard')

  if (screen === 'splash') {
    return <SplashScreen onDone={handleSplashDone} />
  }

  if (screen === 'login') {
    return (
      <Login
        onGoToRegister={() => setScreen('register')}
        onLoggedIn={handleLoggedIn}
      />
    )
  }

  if (screen === 'register') {
    return (
      <Onboarding
        onGoToLogin={() => setScreen('login')}
        onRegistered={handleLoggedIn}
      />
    )
  }

  if (sessionId) return <InterviewSession token={token ?? ''} />

  return <Dashboard />
}
