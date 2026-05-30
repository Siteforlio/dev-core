import { useState } from 'react'
import { useAuthStore } from './store/authStore'
import { useInterviewStore } from './store/interviewStore'
import SplashScreen from './pages/SplashScreen'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import InterviewSession from './components/interview/InterviewSession'
import { useSimulationStore } from './store/simulationStore'
import SimulationSessionPage from './pages/SimulationSessionPage'

type Screen = 'splash' | 'login' | 'register' | 'dashboard'

export default function App() {
  const [screen, setScreen] = useState<Screen>('splash')
  const token          = useAuthStore((s) => s.accessToken)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const sessionId      = useInterviewStore((s) => s.sessionId)
  const activeSimSessionId = useSimulationStore((s) => s.activeSimSessionId)

  // Redirect to login whenever auth is cleared (logout, token expiry)
  if (screen === 'dashboard' && !isAuthenticated) {
    setScreen('login')
  }

  /* Splash → login or dashboard */
  const handleSplashDone = (authenticated: boolean) => {
    // Signal Electron to create the overlay window now that splash is done
    ;(window as any).electronAPI?.splashDone?.()
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
  if (activeSimSessionId) return <SimulationSessionPage />

  return <Dashboard />
}
