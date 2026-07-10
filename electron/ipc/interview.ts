import { ipcRenderer } from 'electron'
import type { IPCResponse } from './types'

interface SkillsTask {
  title: string
  brief: string
  input_type: 'code' | 'text'
  language: string | null
  starter_code: string | null
  evaluation_criteria: string[]
  time_hint: string
}

interface CreateSessionResult {
  session_id: string
  round_id: string
  company: string
  role: string
  career_track: string
  level: string
  current_round: string
  remaining_rounds: string[]
  questions: string[]
  task: SkillsTask | null
  persona: string
  time_budget_seconds: number
}

interface SubmitAnswerResult {
  score: number
  passed: boolean
  what_worked: string
  what_was_missing: string
  stronger_version: string
  follow_up: string | null
  confidence_signal: string
  factual_errors: string[]
  round_complete: boolean
  round_passed: boolean | null
  evaluation: Record<string, unknown> | null
  time_remaining_seconds: number
  phase?: 'task' | 'followup'
}

interface AdvanceRoundResult {
  round_id: string
  current_round: string
  questions: string[]
  task: SkillsTask | null
  persona: string
  time_budget_seconds: number
}

export const interviewIPC = {
  createSession: (data: {
    company: string
    role: string
    roundTypes: string[]
    careerTrack?: string
    level?: string
    interviewStage?: string
    jdText?: string | null
    managerName?: string | null
  }): Promise<IPCResponse<CreateSessionResult>> =>
    ipcRenderer.invoke('interview:create-session', data),

  submitAnswer: (data: {
    sessionId: string
    roundId: string
    question: string
    answer: string
    totalQuestions?: number
    emotionState?: string | null
    timeTakenSeconds?: number | null
    rewriteCount?: number
    isFollowup?: boolean
  }): Promise<IPCResponse<SubmitAnswerResult>> =>
    ipcRenderer.invoke('interview:submit-answer', data),

  advanceRound: (data: {
    sessionId: string
    nextRoundType: string
  }): Promise<IPCResponse<AdvanceRoundResult>> =>
    ipcRenderer.invoke('interview:advance-round', data),

  behavioralSignal: (data: {
    sessionId: string
    rewriteCount: number
  }): Promise<IPCResponse<{ reaction: string | null }>> =>
    ipcRenderer.invoke('interview:behavioral-signal', data),

  cheatSignal: (data: {
    sessionId: string
    roundId: string
    signalType: string
    pasteChars?: number | null
    durationSeconds?: number | null
    charsPerSecond?: number | null
  }): Promise<IPCResponse<null>> =>
    ipcRenderer.invoke('interview:cheat-signal', data),
}
