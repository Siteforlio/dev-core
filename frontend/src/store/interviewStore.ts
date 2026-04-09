import { create } from 'zustand'

interface Round {
  id: string
  type: string
  questions: string[]
  currentQuestionIndex: number
  passed?: boolean
  feedback?: string
}

interface InterviewState {
  sessionId: string | null
  company: string
  role: string
  currentRound: Round | null
  remainingRounds: string[]
  persona: string
  sessionComplete: boolean
  setSession: (
    sessionId: string,
    company: string,
    role: string,
    round: Round,
    remainingRounds: string[],
    persona: string
  ) => void
  nextQuestion: () => void
  setRoundResult: (passed: boolean, feedback: string) => void
  completeSession: () => void
  reset: () => void
}

export const useInterviewStore = create<InterviewState>((set) => ({
  sessionId: null,
  company: '',
  role: '',
  currentRound: null,
  remainingRounds: [],
  persona: '',
  sessionComplete: false,
  setSession: (sessionId, company, role, round, remainingRounds, persona) =>
    set({ sessionId, company, role, currentRound: round, remainingRounds, persona, sessionComplete: false }),
  nextQuestion: () =>
    set((s) =>
      s.currentRound
        ? { currentRound: { ...s.currentRound, currentQuestionIndex: s.currentRound.currentQuestionIndex + 1 } }
        : s
    ),
  setRoundResult: (passed, feedback) =>
    set((s) => (s.currentRound ? { currentRound: { ...s.currentRound, passed, feedback } } : s)),
  completeSession: () => set({ sessionComplete: true }),
  reset: () =>
    set({ sessionId: null, company: '', role: '', currentRound: null, remainingRounds: [], persona: '', sessionComplete: false }),
}))
