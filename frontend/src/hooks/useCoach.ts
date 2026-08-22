import { useState, useCallback, useRef } from 'react'
import { API_BASE } from '../lib/apiBase'
import { apiFetch } from '../lib/apiFetch'

export interface CoachMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface SessionContext {
  company: string
  role: string
  round_type: string
  level: string
  career_track: string
  current_question: string
  question_number: number
  total_questions: number
  time_remaining_seconds: number
  last_feedback?: { what_worked?: string; what_was_missing?: string } | null
}

interface UseCoachOptions {
  sessionId: string | null
  question: string
  roundType: string
  careerTrack: string
  level: string
}

/**
 * Manages the coach conversation for full-screen coach mode.
 *
 * Key behaviours (per new UX):
 * - Conversation persists across open/close within the same session (no reset on open).
 * - open(ctx) captures a session context snapshot sent only on the first API call.
 * - Subsequent sendMessage() calls carry conversation history but no context (backend ignores it).
 * - [ERROR] SSE token replaces the blank assistant placeholder with an error notice.
 */
export function useCoach({
  sessionId,
  question,
  roundType,
  careerTrack,
  level,
}: UseCoachOptions) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<CoachMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  // Session context snapshot — set by open(), cleared after first stream completes
  const sessionContextRef = useRef<SessionContext | null>(null)

  const _stream = useCallback(
    async (userMessage: string | null, history: CoachMessage[]) => {
      if (!sessionId) return

      abortRef.current?.abort()
      const abort = new AbortController()
      abortRef.current = abort

      setIsStreaming(true)

      if (userMessage) {
        setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
      }
      // Append blank assistant placeholder — filled in token by token
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

      try {
        const res = await apiFetch(`${API_BASE()}/interview-sessions/${sessionId}/coach`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question,
            round_type: roundType,
            career_track: careerTrack,
            level,
            message: userMessage,
            conversation_history: history,
            session_context: sessionContextRef.current,
          }),
          signal: abort.signal,
        })

        if (!res.body) return

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const payload = line.slice(6)
            if (payload === '[DONE]') break
            if (payload === '[ERROR]') {
              // Replace blank placeholder with a user-visible error message
              setMessages((prev) => {
                const next = [...prev]
                const last = next[next.length - 1]
                if (last?.role === 'assistant' && last.content === '') {
                  next[next.length - 1] = {
                    ...last,
                    content: 'Something went wrong. Try asking again.',
                  }
                }
                return next
              })
              break
            }
            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last?.role === 'assistant') {
                next[next.length - 1] = { ...last, content: last.content + payload }
              }
              return next
            })
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return
        // Show error in the placeholder so the user knows something failed
        setMessages((prev) => {
          const next = [...prev]
          const last = next[next.length - 1]
          if (last?.role === 'assistant' && last.content === '') {
            next[next.length - 1] = { ...last, content: 'Something went wrong. Try asking again.' }
          }
          return next
        })
      } finally {
        setIsStreaming(false)
        // Context is only relevant for the first call — clear it so follow-ups don't resend it
        sessionContextRef.current = null
      }
    },
    [sessionId, question, roundType, careerTrack, level],
  )

  /**
   * Enter coach mode.
   *
   * Captures a session context snapshot used only on the very first API call
   * so the coach understands exactly where the candidate is and what they're
   * struggling with.  If the conversation already has messages (user re-entered
   * coach mode), just opens without re-triggering the decode stream.
   */
  const open = useCallback(
    (ctx?: SessionContext) => {
      sessionContextRef.current = ctx ?? null
      setIsOpen(true)
      setMessages((prev) => {
        if (prev.length === 0) {
          // Kick off the initial decode on the next tick so state is set first
          setTimeout(() => _stream(null, []), 0)
        }
        return prev
      })
    },
    [_stream],
  )

  /** Exit coach mode and cancel any in-flight stream. */
  const close = useCallback(() => {
    abortRef.current?.abort()
    setIsOpen(false)
  }, [])

  /**
   * Send a follow-up message from the candidate.
   * Passes completed exchanges as history so the LLM has full context.
   */
  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || isStreaming) return
      // Exclude any blank in-progress assistant placeholder from history
      const history = messages.filter((m) => m.content.trim() !== '' || m.role === 'user')
      _stream(text, history)
    },
    [messages, isStreaming, _stream],
  )

  return { isOpen, messages, isStreaming, open, close, sendMessage }
}
