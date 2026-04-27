import { contextBridge, ipcRenderer } from 'electron'
import { authIPC } from './ipc/auth'
import { interviewIPC } from './ipc/interview'

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  auth: authIPC,
  interview: interviewIPC,
  getAccessToken: () => ipcRenderer.invoke('auth:get:token'),
  devcore: {
    startSession:     (payload: unknown) => ipcRenderer.invoke('devcore:session:start', payload),
    pauseSession:     ()                 => ipcRenderer.invoke('devcore:session:pause'),
    endSession:       ()                 => ipcRenderer.invoke('devcore:session:end'),
    enableInteract:   ()                 => ipcRenderer.invoke('devcore:interact:enable'),
    disableInteract:  ()                 => ipcRenderer.invoke('devcore:interact:disable'),
    manualAsk:        (payload: unknown) => ipcRenderer.invoke('devcore:manual:ask', payload),
    onSuggestion: (cb: (p: { delta: string; done: boolean }) => void): (() => void) => {
      const handler = (_e: unknown, p: { delta: string; done: boolean }) => cb(p)
      ipcRenderer.on('devcore:suggestion', handler)
      return () => ipcRenderer.removeListener('devcore:suggestion', handler)
    },
    onTranscript: (cb: (p: { speaker: 'interviewer' | 'user'; text: string; seq: number }) => void): (() => void) => {
      const handler = (_e: unknown, p: { speaker: 'interviewer' | 'user'; text: string; seq: number }) => cb(p)
      ipcRenderer.on('devcore:transcript', handler)
      return () => ipcRenderer.removeListener('devcore:transcript', handler)
    },
    onStatus: (cb: (p: { state: 'listening' | 'thinking' | 'paused' | 'idle'; latencyMs: number }) => void): (() => void) => {
      const handler = (_e: unknown, p: { state: 'listening' | 'thinking' | 'paused' | 'idle'; latencyMs: number }) => cb(p)
      ipcRenderer.on('devcore:status', handler)
      return () => ipcRenderer.removeListener('devcore:status', handler)
    },
    onError: (cb: (p: { code: string; message: string }) => void): (() => void) => {
      const handler = (_e: unknown, p: { code: string; message: string }) => cb(p)
      ipcRenderer.on('devcore:error', handler)
      return () => ipcRenderer.removeListener('devcore:error', handler)
    },
    removeAllListeners: () => {
      ;['devcore:suggestion','devcore:transcript','devcore:status','devcore:error']
        .forEach(ch => ipcRenderer.removeAllListeners(ch))
    },
  },
})
