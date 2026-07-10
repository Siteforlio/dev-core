import { useState, useCallback, useEffect, useRef } from 'react'
import { useAuthStore } from '../store/authStore'
import { useTTS } from './useTTS'
import { useVAD } from './useVAD'

export type TurnState = 'idle' | 'interviewer_speaking' | 'user_speaking' | 'processing'

interface UseVoiceOptions {
  sessionId: string | null
  token: string
  /** Called when the user's transcript is confirmed (auto or manual). */
  onTranscriptConfirmed: (transcript: string) => void
}

/**
 * Orchestrates conversational voice for the interview session.
 *
 * Replaces the old push-to-talk useVoice with an always-on pipeline:
 *   Kokoro TTS (WebSocket streaming) ↔ Silero VAD ↔ Deepgram STT
 *
 * Turn management:
 *   idle → interviewer_speaking  (speak() called)
 *   interviewer_speaking → user_speaking  (VAD fires → TTS interrupted)
 *   user_speaking → processing  (VAD silence detected, audio sent to STT)
 *   processing → idle  (transcript confirmed, caller submits answer)
 *
 * Muted mode:
 *   VAD is paused, text input is shown instead. TTS still plays.
 *   The caller reverts to manual answer submission.
 */
export function useVoice({ sessionId, token, onTranscriptConfirmed }: UseVoiceOptions) {
  const languagePref = useAuthStore((s) => s.languagePref)

  const [muted, setMuted] = useState(false)
  const [turnState, setTurnState] = useState<TurnState>('idle')
  const [pendingTranscript, setPendingTranscript] = useState<string | null>(null)
  const [micStream, setMicStream] = useState<MediaStream | null>(null)

  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const micStreamRef = useRef<MediaStream | null>(null)
  const onTranscriptRef = useRef(onTranscriptConfirmed)
  onTranscriptRef.current = onTranscriptConfirmed

  // ── TTS ───────────────────────────────────────────────────────────────────
  const { speak: ttSpeak, interrupt, isSpeaking } = useTTS(sessionId, token)

  // ── VAD callbacks ─────────────────────────────────────────────────────────
  const handleSpeechStart = useCallback(() => {
    interrupt()
    setTurnState('user_speaking')
  }, [interrupt])

  const handleTranscript = useCallback((text: string) => {
    setTurnState('processing')
    setPendingTranscript(text)

    // Auto-confirm after 3 s — gives user time to cancel if VAD misfired
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current)
    confirmTimerRef.current = setTimeout(() => {
      setPendingTranscript(null)
      setTurnState('idle')
      onTranscriptRef.current(text)
    }, 3_000)
  }, [])

  useVAD(muted ? null : micStream, {
    muted,
    onSpeechStart: handleSpeechStart,
    onTranscript: handleTranscript,
    languagePref,
  })

  // ── Public API ─────────────────────────────────────────────────────────────

  /** Speak text via Kokoro TTS. Optionally pass a Kokoro voice ID or hint. */
  const speak = useCallback((text: string, voice?: string) => {
    if (!text.trim()) return
    setTurnState('interviewer_speaking')
    ttSpeak(text, voice)
  }, [ttSpeak])

  const stopSpeaking = useCallback(() => {
    interrupt()
    setTurnState('idle')
  }, [interrupt])

  /** User manually confirms their transcript before the 3 s timer fires. */
  const confirmTranscript = useCallback(() => {
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current)
    const text = pendingTranscript
    setPendingTranscript(null)
    setTurnState('idle')
    if (text) onTranscriptRef.current(text)
  }, [pendingTranscript])

  /** User cancels a VAD-detected transcript (e.g. background noise). */
  const cancelTranscript = useCallback(() => {
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current)
    setPendingTranscript(null)
    setTurnState('idle')
  }, [])

  // ── Mic lifecycle (called by the component on mount/unmount) ───────────────

  const initMic = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      micStreamRef.current = stream
      setMicStream(stream)
    } catch {
      // Mic denied — muted/text mode still fully functional
    }
  }, [])

  const destroyMic = useCallback(() => {
    micStreamRef.current?.getTracks().forEach((t) => t.stop())
    micStreamRef.current = null
    setMicStream(null)
  }, [])

  // Clean up confirmation timer on unmount
  useEffect(() => {
    return () => {
      if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current)
    }
  }, [])

  // ── Legacy compat props (InterviewSession still references these) ──────────
  // isRecording — true while the user is actively speaking (VAD detected speech)
  const isRecording = turnState === 'user_speaking'

  return {
    // TTS
    speak,
    stopSpeaking,
    isSpeaking,
    // VAD / turn
    isRecording,
    turnState,
    // Transcript confirmation
    pendingTranscript,
    confirmTranscript,
    cancelTranscript,
    // Mute
    muted,
    setMuted,
    // Mic stream (shared with FeedbackStrip / camera overlay)
    micStream,
    initMic,
    destroyMic,
  }
}
