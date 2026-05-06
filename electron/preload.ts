import { contextBridge, ipcRenderer } from 'electron'
import { authIPC } from './ipc/auth'
import { interviewIPC } from './ipc/interview'

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  auth: authIPC,
  interview: interviewIPC,
  getAccessToken: () => ipcRenderer.invoke('auth:get:token'),
  devcore: {
    getStatus:            () => ipcRenderer.invoke('devcore:session:status'),
    listDevices:          () => ipcRenderer.invoke('devcore:devices:list'),
    updateContentBounds:  (b: { x: number; y: number; width: number; height: number }) =>
      ipcRenderer.send('devcore:content:bounds', b),
    testMic: (payload: { deviceId?: number | null; durationMs?: number }) =>
      ipcRenderer.invoke('devcore:mic:test', payload),
    startSession:     (payload: unknown) => ipcRenderer.invoke('devcore:session:start', payload),
    pauseSession:     ()                 => ipcRenderer.invoke('devcore:session:pause'),
    endSession:       ()                 => ipcRenderer.invoke('devcore:session:end'),
    enableInteract:   ()                 => ipcRenderer.invoke('devcore:interact:enable'),
    disableInteract:  ()                 => ipcRenderer.invoke('devcore:interact:disable'),
    manualAsk:        (payload: unknown) => ipcRenderer.invoke('devcore:manual:ask', payload),
    outcomeAsk:       (payload: { outcome: string }) => ipcRenderer.invoke('devcore:outcome:ask', payload),
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
    onStatus: (cb: (p: { state: 'listening' | 'thinking' | 'paused' | 'idle' | 'reconnecting'; latencyMs: number }) => void): (() => void) => {
      const handler = (_e: unknown, p: { state: 'listening' | 'thinking' | 'paused' | 'idle' | 'reconnecting'; latencyMs: number }) => cb(p)
      ipcRenderer.on('devcore:status', handler)
      return () => ipcRenderer.removeListener('devcore:status', handler)
    },
    onError: (cb: (p: { code: string; message: string }) => void): (() => void) => {
      const handler = (_e: unknown, p: { code: string; message: string }) => cb(p)
      ipcRenderer.on('devcore:error', handler)
      return () => ipcRenderer.removeListener('devcore:error', handler)
    },
    onHotkey: (cb: (p: { action: string }) => void): (() => void) => {
      const handler = (_e: unknown, p: { action: string }) => cb(p)
      ipcRenderer.on('devcore:hotkey', handler)
      return () => ipcRenderer.removeListener('devcore:hotkey', handler)
    },
    onOutcome: (cb: (p: { outcome: string; question: string }) => void): (() => void) => {
      const handler = (_e: unknown, p: { outcome: string; question: string }) => cb(p)
      ipcRenderer.on('devcore:outcome', handler)
      return () => ipcRenderer.removeListener('devcore:outcome', handler)
    },
    onSessionTitle: (cb: (p: { title: string }) => void): (() => void) => {
      const handler = (_e: unknown, p: { title: string }) => cb(p)
      ipcRenderer.on('devcore:session:title', handler)
      return () => ipcRenderer.removeListener('devcore:session:title', handler)
    },
    onDevicesChanged: (cb: (p: { mics: { id: number; name: string }[]; systems: { id: number; name: string }[] }) => void): (() => void) => {
      const handler = (_e: unknown, p: { mics: { id: number; name: string }[]; systems: { id: number; name: string }[] }) => cb(p)
      ipcRenderer.on('devcore:devices:changed', handler)
      return () => ipcRenderer.removeListener('devcore:devices:changed', handler)
    },
    removeAllListeners: () => {
      ;['devcore:suggestion','devcore:transcript','devcore:status','devcore:error','devcore:hotkey','devcore:outcome','devcore:devices:changed','devcore:session:title']
        .forEach(ch => ipcRenderer.removeAllListeners(ch))
    },
  },
})
