import { useState, useEffect, useRef } from 'react'
import type { CoachMessage } from '../../hooks/useCoach'

interface Props {
  isOpen: boolean
  messages: CoachMessage[]
  isStreaming: boolean
  onClose: () => void
  onSend: (text: string) => void
}

/**
 * In-session coaching panel — slides in from the right edge.
 *
 * Placement (§5.1 — no business logic, layout concerns only):
 *   position: fixed, right: 0, top: 0, bottom: 58px (above ControlsBar)
 *   width: 360px — does NOT reflow any other element
 *   z-index: 40 — sits above all in-session overlays (max z:30) but below
 *              any future modal
 *
 * The panel slides in/out with CSS transform so it never causes layout shifts.
 */
export default function CoachPanel({ isOpen, messages, isStreaming, onClose, onSend }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 280)
  }, [isOpen])

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

  return (
    <>
      {/* Backdrop — subtle darkening of the video behind the panel, non-blocking */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.35)',
          backdropFilter: 'blur(1px)',
          zIndex: 39,
          opacity: isOpen ? 1 : 0,
          pointerEvents: isOpen ? 'auto' : 'none',
          transition: 'opacity 0.25s ease',
        }}
      />

      {/* Panel */}
      <div
        style={{
          position: 'fixed',
          right: 0,
          top: 0,
          bottom: 58,   // sit above ControlsBar
          width: 360,
          background: 'rgba(13,14,20,0.97)',
          backdropFilter: 'blur(12px)',
          borderLeft: '1px solid rgba(255,255,255,0.07)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 40,
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.25s cubic-bezier(0.4,0,0.2,1)',
        }}
      >
        {/* Header */}
        <div style={{
          height: 48,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c4c9d8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="9" y1="18" x2="15" y2="18"/><line x1="10" y1="22" x2="14" y2="22"/>
              <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/>
            </svg>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#c4c9d8', letterSpacing: '0.02em' }}>
              Coach
            </span>
            {isStreaming && (
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#818cf8',
                animation: 'coachPulse 1s ease-in-out infinite',
                flexShrink: 0,
              }} />
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              width: 28, height: 28,
              borderRadius: '50%',
              border: '1px solid rgba(255,255,255,0.08)',
              background: 'transparent',
              color: '#4a5168',
              fontSize: 14,
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ✕
          </button>
        </div>

        {/* Message list */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}>
          {messages.length === 0 && !isStreaming && (
            <div style={{ color: '#3d4459', fontSize: 12, textAlign: 'center', marginTop: 32 }}>
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
              <div style={{
                maxWidth: '88%',
                background: msg.role === 'user'
                  ? 'rgba(99,102,241,0.18)'
                  : 'rgba(255,255,255,0.05)',
                border: `1px solid ${msg.role === 'user' ? 'rgba(99,102,241,0.25)' : 'rgba(255,255,255,0.07)'}`,
                borderRadius: msg.role === 'user' ? '10px 10px 2px 10px' : '10px 10px 10px 2px',
                padding: '9px 12px',
                fontSize: 12.5,
                color: msg.role === 'user' ? '#c7d2fe' : '#d1d5db',
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {msg.content}
                {/* Blinking cursor on streaming assistant message */}
                {msg.role === 'assistant' && i === messages.length - 1 && isStreaming && (
                  <span style={{
                    display: 'inline-block',
                    width: 2, height: 13,
                    background: '#818cf8',
                    marginLeft: 2,
                    verticalAlign: 'middle',
                    animation: 'coachCursor 0.8s step-end infinite',
                  }} />
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{
          flexShrink: 0,
          borderTop: '1px solid rgba(255,255,255,0.06)',
          padding: '10px 12px',
          display: 'flex',
          gap: 8,
          alignItems: 'flex-end',
        }}>
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
              borderRadius: 8,
              padding: '8px 10px',
              fontSize: 12,
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
              width: 32, height: 32,
              borderRadius: '50%',
              border: 'none',
              background: !input.trim() || isStreaming ? 'rgba(99,102,241,0.2)' : '#6366f1',
              color: '#fff',
              fontSize: 13,
              cursor: !input.trim() || isStreaming ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
              transition: 'background 0.15s',
            }}
          >
            ↑
          </button>
        </div>

        <style>{`
          @keyframes coachPulse {
            0%,100% { opacity: 1; }
            50% { opacity: 0.3; }
          }
          @keyframes coachCursor {
            0%,100% { opacity: 1; }
            50% { opacity: 0; }
          }
        `}</style>
      </div>
    </>
  )
}
