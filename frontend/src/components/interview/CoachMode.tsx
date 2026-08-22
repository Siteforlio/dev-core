import { useState, useEffect, useRef } from 'react'
import type { CoachMessage } from '../../hooks/useCoach'

interface SessionInfo {
  company: string
  role: string
  roundType: string
  questionNumber: number
  totalQuestions: number
  /** Seconds remaining in the round when coach mode was entered */
  timeRemaining: number
  currentQuestion: string
}

interface Props {
  messages: CoachMessage[]
  isStreaming: boolean
  sessionInfo: SessionInfo
  onSend: (text: string) => void
  onReturn: () => void
}

function formatTime(secs: number): string {
  const m = Math.floor(Math.max(0, secs) / 60)
  const s = Math.floor(Math.max(0, secs) % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

/**
 * Full-screen coaching mode — takes over the interview UI when the candidate
 * presses "Coach".
 *
 * The interview timer is frozen at the moment coach mode was entered.  The
 * session context strip shows the candidate exactly where they paused so they
 * never lose track of where they are in the interview.
 *
 * Layout (§5.1 — no business logic here):
 *   - Top bar: Return button + Coach label + PAUSED badge with frozen timer
 *   - Context strip: company · role · round · question number + quoted question
 *   - Message area: scrollable conversation (fills remaining height)
 *   - Input bar: textarea + send button
 */
export default function CoachMode({ messages, isStreaming, sessionInfo, onSend, onReturn }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 120)
  }, [])

  const handleSend = () => {
    const text = input.trim()
    if (!text || isStreaming) return
    onSend(text)
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const roundLabel =
    sessionInfo.roundType.charAt(0).toUpperCase() + sessionInfo.roundType.slice(1).replace('_', ' ')

  return (
    <div
      style={{
        height: '100vh',
        background: '#09090f',
        color: 'white',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'inherit',
        overflow: 'hidden',
      }}
    >
      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <div
        style={{
          height: 52,
          flexShrink: 0,
          background: '#0e0f14',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: 12,
        }}
      >
        <button
          onClick={onReturn}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(34,197,94,0.1)',
            border: '1px solid rgba(34,197,94,0.25)',
            borderRadius: 8,
            padding: '6px 14px',
            fontSize: 12,
            fontWeight: 600,
            color: '#4ade80',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          ← Return to Interview
        </button>

        <div style={{ flex: 1 }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c4c9d8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="9" y1="18" x2="15" y2="18"/><line x1="10" y1="22" x2="14" y2="22"/>
            <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/>
          </svg>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#c4c9d8' }}>Coach</span>
          {isStreaming && (
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: '#818cf8',
                animation: 'coachPulse 1s ease-in-out infinite',
                flexShrink: 0,
              }}
            />
          )}
        </div>

        <div
          style={{
            background: 'rgba(245,158,11,0.1)',
            border: '1px solid rgba(245,158,11,0.22)',
            borderRadius: 6,
            padding: '4px 12px',
            fontSize: 11,
            fontWeight: 600,
            color: '#fbbf24',
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          ⏸ PAUSED — {formatTime(sessionInfo.timeRemaining)} left
        </div>
      </div>

      {/* ── Session context strip ────────────────────────────────────────────── */}
      <div
        style={{
          flexShrink: 0,
          background: '#0b0c12',
          borderBottom: '1px solid rgba(255,255,255,0.04)',
          padding: '10px 16px 12px',
        }}
      >
        <div
          style={{
            fontSize: 10,
            color: '#2e3347',
            fontWeight: 700,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            marginBottom: 7,
          }}
        >
          Session Context
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 9 }}>
          {[
            sessionInfo.company,
            sessionInfo.role,
            `${roundLabel} Round`,
            `Q${sessionInfo.questionNumber} of ${sessionInfo.totalQuestions}`,
          ].map((label) => (
            <span
              key={label}
              style={{
                background: '#161822',
                borderRadius: 20,
                padding: '3px 10px',
                fontSize: 11,
                color: '#6b7280',
                border: '1px solid rgba(255,255,255,0.04)',
                whiteSpace: 'nowrap',
              }}
            >
              {label}
            </span>
          ))}
        </div>
        <div
          style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 8,
            padding: '9px 13px',
            fontSize: 13,
            color: '#94a3b8',
            lineHeight: 1.58,
            fontStyle: 'italic',
          }}
        >
          "{sessionInfo.currentQuestion}"
        </div>
      </div>

      {/* ── Messages ────────────────────────────────────────────────────────── */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        {messages.length === 0 && !isStreaming && (
          <div style={{ color: '#2e3347', fontSize: 12, textAlign: 'center', marginTop: 40 }}>
            Coach is thinking…
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            {msg.role === 'assistant' && (
              <div
                style={{
                  fontSize: 10,
                  color: '#3d4459',
                  marginBottom: 4,
                  paddingLeft: 4,
                  fontWeight: 600,
                  letterSpacing: '0.05em',
                }}
              >
                COACH
              </div>
            )}
            <div
              style={{
                maxWidth: '76%',
                background:
                  msg.role === 'user' ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${
                  msg.role === 'user' ? 'rgba(99,102,241,0.28)' : 'rgba(255,255,255,0.07)'
                }`,
                borderRadius:
                  msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                padding: '10px 14px',
                fontSize: 13,
                color: msg.role === 'user' ? '#c7d2fe' : '#d1d5db',
                lineHeight: 1.65,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {msg.content}
              {/* Blinking cursor on the last assistant message while streaming */}
              {msg.role === 'assistant' && i === messages.length - 1 && isStreaming && (
                <span
                  style={{
                    display: 'inline-block',
                    width: 2,
                    height: 13,
                    background: '#818cf8',
                    marginLeft: 2,
                    verticalAlign: 'middle',
                    animation: 'coachCursor 0.8s step-end infinite',
                  }}
                />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ───────────────────────────────────────────────────────── */}
      <div
        style={{
          flexShrink: 0,
          borderTop: '1px solid rgba(255,255,255,0.06)',
          padding: '12px 16px',
          display: 'flex',
          gap: 10,
          alignItems: 'flex-end',
          background: '#0e0f14',
        }}
      >
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder="Ask the coach anything…"
          rows={2}
          style={{
            flex: 1,
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 10,
            padding: '10px 12px',
            fontSize: 13,
            color: '#e2e8f0',
            resize: 'none',
            outline: 'none',
            fontFamily: 'inherit',
            lineHeight: 1.5,
            opacity: isStreaming ? 0.5 : 1,
          }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isStreaming}
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            border: 'none',
            background: !input.trim() || isStreaming ? 'rgba(99,102,241,0.2)' : '#6366f1',
            color: '#fff',
            fontSize: 14,
            cursor: !input.trim() || isStreaming ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
        >
          ↑
        </button>
      </div>

      <style>{`
        @keyframes coachPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes coachCursor { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
      `}</style>
    </div>
  )
}
