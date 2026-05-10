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
  // Assessment mode — undefined means standard interview mode
  assessmentMode?: 'coding' | 'live' | 'ai_model'
  projectRoot?: string    // live mode: absolute path to project folder
  filePaths?: string[]    // presentation mode: specific file paths to analyze
}

export type AssessmentMode = 'present' | 'coding' | 'live' | 'ai_model'

export interface ToolEvent {
  tool:   'terminal' | 'screen' | 'browser' | 'file' | 'search'
  status: 'start' | 'data' | 'done' | 'error'
  data:   Record<string, unknown>
  ts:     number
}

export type OverlayState = 'idle' | 'listening' | 'thinking' | 'paused' | 'reconnecting'
