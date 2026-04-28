export interface SessionStartPayload {
  sessionId: string
  context: {
    jobTitle: string
    company: string
    resumeText: string
    jdText: string
    files: string[]
  }
}

export interface ManualAskPayload {
  text: string
  mode: 'hints' | 'solve'
  language?: string
}

export type DevCoreRendererToMain =
  | { channel: 'devcore:session:start'; payload: SessionStartPayload }
  | { channel: 'devcore:session:pause'; payload: void }
  | { channel: 'devcore:session:end'; payload: void }
  | { channel: 'devcore:interact:enable'; payload: void }
  | { channel: 'devcore:interact:disable'; payload: void }
  | { channel: 'devcore:manual:ask'; payload: ManualAskPayload }

export type DevCoreMainToRenderer =
  | { channel: 'devcore:suggestion'; payload: { delta: string; done: boolean } }
  | { channel: 'devcore:transcript'; payload: { speaker: 'interviewer' | 'user'; text: string } }
  | { channel: 'devcore:status'; payload: { state: 'listening' | 'thinking' | 'paused'; latencyMs: number } }
  | { channel: 'devcore:error'; payload: { code: string; message: string } }
