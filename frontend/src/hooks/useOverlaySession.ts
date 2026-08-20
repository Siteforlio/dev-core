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

    // onSuggestion and onStatus are handled in SuggestionCard to drive the chat UI
    const removeSessionStarted = api.onSessionStarted?.((p: { sessionId: string; startedAt: number }) => {
      store.setSessionId(p.sessionId)
      store.setSessionStartedAt(p.startedAt)
    })
    const removeSessionEnded = api.onSessionEnded?.(() => {
      store.setSessionId(null)
      store.setSessionStartedAt(null)
    })
    const removeSessionMode = api.onSessionMode?.((p: { assessmentMode: string | null }) => {
      store.setAssessmentMode(p.assessmentMode as any)
    })
    const removeTranscript = api.onTranscript(({ speaker, text, seq }: { speaker: 'interviewer' | 'user'; text: string; seq: number }) => {
      store.addTranscript({ speaker, text, seq })
    })
    const removeTranscriptWord = api.onTranscriptWord?.((p: { speaker: 'interviewer' | 'user'; text: string }) => {
      console.log(`[word] [${p.speaker}] ${p.text}`)
    })
    const removeError = api.onError?.((p: { code: string; message: string }) => {
      console.error('[devcore] WS error from main:', p.code, p.message)
      store.setError(p)
    })
    const removeToolEvent = api.onToolEvent?.((p: { tool: string; status: string; data: Record<string, unknown> }) => {
      store.addToolEvent({ ...p, ts: Date.now() } as any)
    })
    const removeAgentThinking = api.onAgentThinking?.((p: { text: string }) => {
      store.setAgentThinking(p.text)
    })
    const removeAgentGuidance = api.onAgentGuidance?.((p: { text: string }) => {
      store.setAgentGuidance(p.text)
    })
    const removeAgentSolution = api.onAgentSolution?.((p: { code: string; language: string; explanation: string }) => {
      store.setAgentSolution(p)
    })
    return () => {
      removeSessionStarted?.()
      removeSessionEnded?.()
      removeSessionMode?.()
      removeTranscript?.()
      removeTranscriptWord?.()
      removeError?.()
      removeToolEvent?.()
      removeAgentThinking?.()
      removeAgentGuidance?.()
      removeAgentSolution?.()
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
    assessmentTrigger: (action: string, text?: string) =>
      window.electronAPI?.devcore.assessmentTrigger({ action, text }),
  }
}
