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
