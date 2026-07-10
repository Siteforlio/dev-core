import { useState, useCallback, useRef } from 'react'

const API = 'http://localhost:8000/api/v1'

export interface CoachMessage {
  role: 'user' | 'assistant'
  content: string
}

interface UseCoachOptions {
  sessionId: string | null
  token: string
  question: string
  roundType: string
  careerTrack: string
  level: string
}

/**
 * Manages the in-session coach conversation.
 *
 * On open: automatically sends a "decode" request (no user message) so the
 * coach immediately explains what the question is testing and asks 1-2
 * prompting questions.
 *
 * On sendMessage: appends the user's message and streams the next response.
 *
 * All LLM work happens in the backend (§4.2). This hook owns UI state only.
 */
export function useCoach({
  sessionId,
  token,
  question,
  roundType,
  careerTrack,
  level,
}: UseCoachOptions) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<CoachMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const _stream = useCallback(
    async (userMessage: string | null, history: CoachMessage[]) => {
      if (!sessionId) return

      // Cancel any in-flight stream before starting a new one
      abortRef.current?.abort()
      const abort = new AbortController()
      abortRef.current = abort

      setIsStreaming(true)

      // Optimistically append the user message to UI
      if (userMessage) {
        setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
      }

      // Append a blank assistant message that we'll fill in as tokens arrive
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

      try {
        const res = await fetch(`${API}/interview-sessions/${sessionId}/coach`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            question,
            round_type: roundType,
            career_track: careerTrack,
            level,
            message: userMessage,
            conversation_history: history,
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

            // Append token to the last assistant message
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
        // Non-critical — panel stays open, user can retry
      } finally {
        setIsStreaming(false)
      }
    },
    [sessionId, token, question, roundType, careerTrack, level],
  )

  /** Open the panel. Resets conversation and immediately decodes the question. */
  const open = useCallback(() => {
    setMessages([])
    setIsOpen(true)
    _stream(null, [])
  }, [_stream])

  /** Close the panel and cancel any in-flight stream. */
  const close = useCallback(() => {
    abortRef.current?.abort()
    setIsOpen(false)
  }, [])

  /**
   * Send a follow-up message from the user.
   * The current messages (excluding the last streaming assistant turn) are
   * passed as history so the LLM has full context.
   */
  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || isStreaming) return
      // History = all completed exchanges (skip any in-progress blank assistant turn)
      const history = messages.filter((m) => m.content.trim() !== '' || m.role === 'user')
      _stream(text, history)
    },
    [messages, isStreaming, _stream],
  )

  return { isOpen, messages, isStreaming, open, close, sendMessage }
}
