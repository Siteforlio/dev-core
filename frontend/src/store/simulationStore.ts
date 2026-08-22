// frontend/src/store/simulationStore.ts
import { create } from 'zustand'

interface SimulationState {
  activeSimSessionId: string | null
  persona: string
  timeBudgetSeconds: number | null
  scenarioType: string
  characterId: number
  setSession: (
    sessionId: string,
    persona: string,
    timeBudgetSeconds: number | null,
    scenarioType: string,
    characterId?: number,
  ) => void
  clearSession: () => void
}

export const useSimulationStore = create<SimulationState>((set) => ({
  activeSimSessionId: null,
  persona: '',
  timeBudgetSeconds: null,
  scenarioType: '',
  characterId: 0,
  setSession: (sessionId, persona, timeBudgetSeconds, scenarioType, characterId = 0) =>
    set({ activeSimSessionId: sessionId, persona, timeBudgetSeconds, scenarioType, characterId }),
  clearSession: () =>
    set({ activeSimSessionId: null, persona: '', timeBudgetSeconds: null, scenarioType: '', characterId: 0 }),
}))
