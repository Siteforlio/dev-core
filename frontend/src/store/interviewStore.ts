import { create } from 'zustand'

interface FeedbackResult {
  what_worked: string
  what_was_missing: string
  stronger_version: string
  passed: boolean
}

interface Round {
  id: string
  type: string
  questions: string[]
  currentQuestionIndex: number
  passed?: boolean
  feedbackResult?: FeedbackResult
  timeBudgetSeconds: number
}

interface InterviewState {
  sessionId: string | null
  company: string
  role: string
  currentRound: Round | null
  remainingRounds: string[]
  persona: string
  careerTrack: string
  level: string
  interviewStage: string
  sessionComplete: boolean
  roundFailed: boolean
  setSession: (
    sessionId: string,
    company: string,
    role: string,
    round: Round,
    remainingRounds: string[],
    persona: string,
    careerTrack: string,
    level: string,
    interviewStage: string
  ) => void
  nextQuestion: () => void
  setRoundResult: (passed: boolean, feedbackResult: FeedbackResult) => void
  advanceRound: (round: Round, persona: string, remainingRounds: string[]) => void
  setRoundFailed: (failed: boolean) => void
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
  careerTrack: '',
  level: '',
  interviewStage: '',
  sessionComplete: false,
  roundFailed: false,
  setSession: (sessionId, company, role, round, remainingRounds, persona, careerTrack, level, interviewStage) =>
    set({ sessionId, company, role, currentRound: round, remainingRounds, persona, careerTrack, level, interviewStage, sessionComplete: false, roundFailed: false }),
  nextQuestion: () =>
    set((s) =>
      s.currentRound
        ? { currentRound: { ...s.currentRound, currentQuestionIndex: s.currentRound.currentQuestionIndex + 1 } }
        : s
    ),
  setRoundResult: (passed, feedbackResult) =>
    set((s) => (s.currentRound ? { currentRound: { ...s.currentRound, passed, feedbackResult } } : s)),
  advanceRound: (round, persona, remainingRounds) =>
    set({ currentRound: round, persona, remainingRounds, roundFailed: false }),
  setRoundFailed: (failed) => set({ roundFailed: failed }),
  completeSession: () => set({ sessionComplete: true }),
  reset: () =>
    set({ sessionId: null, company: '', role: '', currentRound: null, remainingRounds: [], persona: '', careerTrack: '', level: '', interviewStage: '', sessionComplete: false, roundFailed: false }),
}))
