import { useCallback, useEffect, useRef } from 'react'
import { useInterviewSession } from './useInterviewSession'

export interface AntiCheatStats {
  pasteCount: number
  largePasteCount: number    // pastes > 80 chars
  focusLostCount: number
  focusLostSeconds: number
  velocitySpikes: number     // bursts > 8 chars/sec
}

interface Options {
  sessionId: string
  roundId: string
  /** Minimum paste char length to count as suspicious (default 80) */
  largePasteThreshold?: number
  /** Chars-per-second rate to flag as velocity spike (default 8) */
  velocityThreshold?: number
  /** Whether to attach document-level paste listener (set false for Monaco, which fires its own) */
  listenDocumentPaste?: boolean
}

/**
 * Tracks anti-cheat signals and reports them to the backend.
 * Returns stats for local display and a `onPaste` handler to pass to Monaco.
 */
export function useAntiCheat({
  sessionId,
  roundId,
  largePasteThreshold = 80,
  velocityThreshold = 8,
  listenDocumentPaste = true,
}: Options) {
  const { reportCheatSignal } = useInterviewSession()

  const stats = useRef<AntiCheatStats>({
    pasteCount: 0,
    largePasteCount: 0,
    focusLostCount: 0,
    focusLostSeconds: 0,
    velocitySpikes: 0,
  })

  // Velocity tracking — rolling window
  const keyTimestamps = useRef<number[]>([])
  const focusLostAt = useRef<number | null>(null)

  // ── Paste detection ────────────────────────────────────────────────────────
  const handlePaste = useCallback(
    (pastedText: string) => {
      const chars = pastedText.length
      if (chars === 0) return
      stats.current.pasteCount++
      const isLarge = chars >= largePasteThreshold
      if (isLarge) stats.current.largePasteCount++
      reportCheatSignal(sessionId, roundId, isLarge ? 'paste' : 'paste_small', {
        pasteChars: chars,
      })
    },
    [sessionId, roundId, largePasteThreshold, reportCheatSignal],
  )

  // Handler for <textarea> / native paste events
  const onNativePaste = useCallback(
    (e: ClipboardEvent) => {
      const text = e.clipboardData?.getData('text') ?? ''
      handlePaste(text)
    },
    [handlePaste],
  )

  // Handler for Monaco editor onDidPaste — pass text directly
  const onMonacoPaste = useCallback(
    (pastedText: string) => {
      handlePaste(pastedText)
    },
    [handlePaste],
  )

  // ── Focus / visibility tracking ────────────────────────────────────────────
  const handleVisibilityChange = useCallback(() => {
    if (document.visibilityState === 'hidden') {
      focusLostAt.current = Date.now()
      stats.current.focusLostCount++
      reportCheatSignal(sessionId, roundId, 'tab_switch')
    } else if (focusLostAt.current !== null) {
      const duration = (Date.now() - focusLostAt.current) / 1000
      stats.current.focusLostSeconds += duration
      focusLostAt.current = null
      reportCheatSignal(sessionId, roundId, 'focus_returned', { durationSeconds: duration })
    }
  }, [sessionId, roundId, reportCheatSignal])

  const handleBlur = useCallback(() => {
    if (focusLostAt.current === null) {
      focusLostAt.current = Date.now()
      stats.current.focusLostCount++
      reportCheatSignal(sessionId, roundId, 'focus_lost')
    }
  }, [sessionId, roundId, reportCheatSignal])

  const handleFocus = useCallback(() => {
    if (focusLostAt.current !== null) {
      const duration = (Date.now() - focusLostAt.current) / 1000
      stats.current.focusLostSeconds += duration
      focusLostAt.current = null
      reportCheatSignal(sessionId, roundId, 'focus_returned', { durationSeconds: duration })
    }
  }, [sessionId, roundId, reportCheatSignal])

  // ── Keystroke velocity tracking ────────────────────────────────────────────
  const onKeyDown = useCallback(() => {
    const now = Date.now()
    keyTimestamps.current.push(now)
    // Keep last 2s of keystrokes
    const cutoff = now - 2000
    keyTimestamps.current = keyTimestamps.current.filter((t) => t >= cutoff)
    const cps = keyTimestamps.current.length / 2
    if (cps >= velocityThreshold) {
      // Only report once per spike (debounce: clear buffer after report)
      if (keyTimestamps.current.length >= velocityThreshold * 2) {
        stats.current.velocitySpikes++
        keyTimestamps.current = []
        reportCheatSignal(sessionId, roundId, 'velocity_spike', { charsPerSecond: cps })
      }
    }
  }, [sessionId, roundId, velocityThreshold, reportCheatSignal])

  // ── Mount / unmount effects ────────────────────────────────────────────────
  useEffect(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('blur', handleBlur)
    window.addEventListener('focus', handleFocus)
    if (listenDocumentPaste) {
      document.addEventListener('paste', onNativePaste)
    }
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('blur', handleBlur)
      window.removeEventListener('focus', handleFocus)
      if (listenDocumentPaste) {
        document.removeEventListener('paste', onNativePaste)
      }
    }
  }, [handleVisibilityChange, handleBlur, handleFocus, onNativePaste, listenDocumentPaste])

  const getStats = useCallback((): AntiCheatStats => ({ ...stats.current }), [])

  return {
    onMonacoPaste,
    onKeyDown,
    getStats,
  }
}
