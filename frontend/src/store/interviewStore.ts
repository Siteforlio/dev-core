import { create } from 'zustand'

interface FeedbackResult {
  what_worked: string
  what_was_missing: string
  stronger_version: string
  passed: boolean
}

export interface SkillsTask {
  title: string
  brief: string
  input_type: 'code' | 'text'
  language: string | null
  starter_code: string | null
  evaluation_criteria: string[]
  time_hint: string
}

interface Round {
  id: string
  type: string
  questions: string[]
  currentQuestionIndex: number
  passed?: boolean
  feedbackResult?: FeedbackResult
  timeBudgetSeconds: number
  task?: SkillsTask | null
  /** Phase for skills_task rounds: 'task' (Phase 1) or 'followup' (Phase 2) */
  skillsPhase?: 'task' | 'followup'
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
  /** Transition a skills_task round from Phase 1 to Phase 2 follow-ups */
  setSkillsPhase: (phase: 'task' | 'followup', followupQuestion?: string) => void
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
  setSkillsPhase: (phase, followupQuestion) =>
    set((s) => {
      if (!s.currentRound) return s
      const updated: Round = { ...s.currentRound, skillsPhase: phase }
      if (phase === 'followup' && followupQuestion) {
        updated.questions = [followupQuestion]
        updated.currentQuestionIndex = 0
      }
      return { currentRound: updated }
    }),
  reset: () =>
    set({ sessionId: null, company: '', role: '', currentRound: null, remainingRounds: [], persona: '', careerTrack: '', level: '', interviewStage: '', sessionComplete: false, roundFailed: false }),
}))
