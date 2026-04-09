import { ipcRenderer } from 'electron'
import type { IPCResponse } from './types'

export const interviewIPC = {
  createSession: (data: { company: string; role: string; roundTypes: string[] }): Promise<IPCResponse<{ sessionId: string; roundId: string; questions: string[]; persona: string }>> =>
    ipcRenderer.invoke('interview:create-session', data),
  submitAnswer: (data: { sessionId: string; roundId: string; question: string; answer: string }): Promise<IPCResponse<{ score: number; passed: boolean; feedback: string }>> =>
    ipcRenderer.invoke('interview:submit-answer', data),
}
