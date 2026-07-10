export interface User {
  id: string
  name: string
  email: string
  languagePref: string
}

export interface InterviewSession {
  sessionId: string
  company: string
  role: string
  currentRound: string
  questions: string[]
  persona: string
}

export interface Round {
  id: string
  type: 'HR' | 'behavioral' | 'technical' | 'leetcode' | 'sysdesign'
  grade?: number
  passed?: boolean
}

export interface ApiResponse<T> {
  data: T | null
  error: { code: string; message: string } | null
}

export interface SubmitAnswerResponse {
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
