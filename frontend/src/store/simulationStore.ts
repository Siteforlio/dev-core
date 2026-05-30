// frontend/src/store/simulationStore.ts
import { create } from 'zustand'

interface SimulationState {
  activeSimSessionId: string | null
  persona: string
  timeBudgetSeconds: number | null
  scenarioType: string
  setSession: (
    sessionId: string,
    persona: string,
    timeBudgetSeconds: number | null,
    scenarioType: string
  ) => void
  clearSession: () => void
}

export const useSimulationStore = create<SimulationState>((set) => ({
  activeSimSessionId: null,
  persona: '',
  timeBudgetSeconds: null,
  scenarioType: '',
  setSession: (sessionId, persona, timeBudgetSeconds, scenarioType) =>
    set({ activeSimSessionId: sessionId, persona, timeBudgetSeconds, scenarioType }),
  clearSession: () =>
    set({ activeSimSessionId: null, persona: '', timeBudgetSeconds: null, scenarioType: '' }),
}))
