// frontend/src/pages/SimulationSessionPage.tsx
import { useState } from 'react'
import { useSimulationStore } from '../store/simulationStore'
import SimulationSession from '../components/simulation/SimulationSession'
import SimulationDebrief from '../components/simulation/SimulationDebrief'
import type { SimDebriefData } from '../hooks/useSimulationSession'

type Phase = 'session' | 'debrief'

export default function SimulationSessionPage() {
  const clearSession = useSimulationStore((s) => s.clearSession)
  const [phase, setPhase] = useState<Phase>('session')
  const [debriefData, setDebriefData] = useState<SimDebriefData | null>(null)

  const handleDebrief = (data: SimDebriefData) => {
    setDebriefData(data)
    setPhase('debrief')
  }

  const handleDismiss = () => {
    clearSession()
  }

  return (
    <div style={{ height: '100vh', overflow: 'hidden', background: '#070f1c' }}>
      {phase === 'session' ? (
        <SimulationSession
          onDebrief={handleDebrief}
          onEnd={clearSession}
        />
      ) : debriefData ? (
        <SimulationDebrief
          debrief={debriefData}
          onDismiss={handleDismiss}
        />
      ) : null}
    </div>
  )
}
