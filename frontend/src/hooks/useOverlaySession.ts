import { useEffect } from 'react'
import { useOverlayStore } from '../store/overlayStore'
import type { OverlayState, SessionContext } from '../types/devcore'

declare global {
  interface Window {
    electronAPI: any
  }
}

export function useOverlaySession() {
  const store = useOverlayStore()

  useEffect(() => {
    const api = window.electronAPI?.devcore
    if (!api) return

    // Sync UI with actual WS state on mount (after hot reload / restart)
    api.getStatus?.().then((s: { connected: boolean }) => {
      if (s.connected && store.state === 'idle') {
        store.setState('listening')
      } else if (!s.connected && store.state !== 'idle') {
        store.setState('idle')
      }
    })

    const removeSuggestion = api.onSuggestion(({ delta, done }: { delta: string; done: boolean }) => {
      store.appendSuggestion(delta)
    })
    const removeTranscript = api.onTranscript(({ speaker, text, seq }: { speaker: 'interviewer' | 'user'; text: string; seq: number }) => {
      store.addTranscript({ speaker, text, seq })
    })
    const removeStatus = api.onStatus(({ state, latencyMs }: { state: OverlayState; latencyMs: number }) => {
      store.setState(state)
      store.setLatency(latencyMs)
      if (state === 'thinking') store.clearSuggestion()
    })
    const removeError = api.onError?.((p: { code: string; message: string }) => {
      store.setError(p)
    })
    return () => {
      removeSuggestion?.()
      removeTranscript?.()
      removeStatus?.()
      removeError?.()
    }
  }, [])

  return {
    startSession:   (payload: { sessionId: string; context: SessionContext; audioSource: string; micDeviceId?: number | null; sysDeviceId?: number | null; token: string }) =>
      window.electronAPI?.devcore.startSession(payload),
    pauseSession:   () => window.electronAPI?.devcore.pauseSession(),
    endSession:     () => window.electronAPI?.devcore.endSession(),
    enableInteract: () => window.electronAPI?.devcore.enableInteract(),
    manualAsk: (text: string, mode: 'hints' | 'solve' | 'ultra', language?: string) =>
      window.electronAPI?.devcore.manualAsk({ text, mode, language }),
  }
}
