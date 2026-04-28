export interface TranscriptEntry {
  speaker: 'interviewer' | 'user'
  text: string
  seq: number
}

export type OverlayPosition = 'top-center' | 'top-left' | 'top-right' | 'bottom-center' | 'bottom-right'

export interface SessionContext {
  jobTitle: string
  company: string
  resumeText: string
  jdText: string
  files: string[]
}

export type OverlayState = 'idle' | 'listening' | 'thinking' | 'paused'
