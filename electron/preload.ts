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
    onSuggestion:     (cb: (p: { delta: string; done: boolean }) => void) =>
                        ipcRenderer.on('devcore:suggestion', (_e, p) => cb(p)),
    onTranscript:     (cb: (p: { speaker: string; text: string }) => void) =>
                        ipcRenderer.on('devcore:transcript', (_e, p) => cb(p)),
    onStatus:         (cb: (p: { state: string; latencyMs: number }) => void) =>
                        ipcRenderer.on('devcore:status', (_e, p) => cb(p)),
    onError:          (cb: (p: { code: string; message: string }) => void) =>
                        ipcRenderer.on('devcore:error', (_e, p) => cb(p)),
    removeAllListeners: () => {
      ;['devcore:suggestion','devcore:transcript','devcore:status','devcore:error']
        .forEach(ch => ipcRenderer.removeAllListeners(ch))
    },
  },
})
