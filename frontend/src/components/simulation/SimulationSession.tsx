// frontend/src/components/simulation/SimulationSession.tsx
import { useEffect, useRef, useState } from 'react'
import { useSimulationStore } from '../../store/simulationStore'
import { useAuthStore } from '../../store/authStore'

interface Turn {
  id: string
  speaker: 'user' | 'ai'
  text: string
  toolEvents?: { tool: string; output: string; status: string }[]
}

interface Props {
  onDebrief: (debriefData: any) => void
  onEnd: () => void
}

export default function SimulationSession({ onDebrief, onEnd }: Props) {
  const { activeSimSessionId, timeBudgetSeconds, scenarioType } = useSimulationStore()
  const token = useAuthStore((s) => s.accessToken)
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [remaining, setRemaining] = useState<number | null>(timeBudgetSeconds)
  const [hardCutoff, setHardCutoff] = useState(false)
  const [cutoffMsg, setCutoffMsg] = useState('')
  const [sessionEnded, setSessionEnded] = useState(false)
  const transcriptRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)

  // Scroll transcript to bottom
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [turns])

  useEffect(() => {
    if (!activeSimSessionId || !token) return
    const wsUrl = `ws://localhost:8000/api/v1/sim-sessions/${activeSimSessionId}/ws?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)

      if (msg.type === 'transcript') {
        if (!msg.final) return
        setTurns((prev) => [
          ...prev,
          { id: `${msg.speaker}-${Date.now()}`, speaker: msg.speaker, text: msg.text },
        ])
      }

      if (msg.type === 'timer_update') {
        setRemaining(msg.remaining_seconds)
      }

      if (msg.type === 'hard_cutoff') {
        setHardCutoff(true)
        setCutoffMsg(msg.message)
      }

      if (msg.type === 'tool_event') {
        setTurns((prev) => {
          const last = prev[prev.length - 1]
          if (!last) return prev
          return [
            ...prev.slice(0, -1),
            { ...last, toolEvents: [...(last.toolEvents || []), msg] },
          ]
        })
      }

      if (msg.type === 'session_end') {
        setSessionEnded(true)
        fetch(`/api/v1/sim-sessions/${activeSimSessionId}/debrief?token=${encodeURIComponent(token)}`, {
          method: 'POST',
        })
          .then((r) => r.json())
          .then((j) => {
            if (j.data) onDebrief(j.data)
          })
          .catch(() => {})
      }

      if (msg.type === 'ai_audio') {
        const bytes = Uint8Array.from(atob(msg.data), (c) => c.charCodeAt(0))
        if (!audioCtxRef.current) {
          audioCtxRef.current = new AudioContext()
        }
        audioCtxRef.current.decodeAudioData(bytes.buffer).then((buf) => {
          const src = audioCtxRef.current!.createBufferSource()
          src.buffer = buf
          src.connect(audioCtxRef.current!.destination)
          src.start()
        }).catch(() => {})
      }
    }

    ws.onerror = () => {}
    ws.onclose = () => {}

    return () => { ws.close() }
  }, [activeSimSessionId, token])

  const sendText = () => {
    if (!input.trim() || !wsRef.current) return
    wsRef.current.send(JSON.stringify({ type: 'text_turn', content: input.trim(), elapsed_seconds: 0 }))
    setInput('')
  }

  const handleEnd = () => {
    wsRef.current?.send(JSON.stringify({ type: 'end_session' }))
    onEnd()
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }

  const timerColor = remaining == null ? '#22d3ee'
    : remaining < 10 ? '#ef4444'
    : remaining < (timeBudgetSeconds ?? Infinity) * 0.2 ? '#f59e0b'
    : '#22d3ee'

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr auto 280px', height: '100%',
      background: '#070f1c', color: '#e2e8f0', fontFamily: 'JetBrains Mono, monospace',
      overflow: 'hidden',
    }}>
      {/* Left: Transcript */}
      <div style={{ display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(34,211,238,0.08)', overflow: 'hidden' }}>
        {hardCutoff && (
          <div style={{
            background: '#ef4444', color: '#fff', padding: '12px 20px',
            fontWeight: 700, fontSize: '15px', letterSpacing: '0.1em',
            textTransform: 'uppercase', textAlign: 'center',
          }}>
            TIME — {cutoffMsg}
          </div>
        )}
        <div ref={transcriptRef} style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {turns.map((t) => (
            <div key={t.id}>
              <div style={{ color: t.speaker === 'user' ? '#22d3ee' : '#9b7bff', fontSize: '12px', marginBottom: '4px', letterSpacing: '0.08em' }}>
                {t.speaker === 'user' ? 'YOU' : 'AI'}
              </div>
              <div style={{ fontSize: '14px', lineHeight: 1.6 }}>{t.text}</div>
              {t.toolEvents?.map((te, i) => (
                <div key={i} style={{
                  marginTop: '8px', background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)',
                  borderRadius: '4px', padding: '8px', fontSize: '12px', color: '#fbbf24',
                }}>
                  <div style={{ marginBottom: '4px' }}>[{te.tool}] {te.status}</div>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: '11px' }}>{te.output}</pre>
                </div>
              ))}
            </div>
          ))}
        </div>
        {/* Input */}
        <div style={{ padding: '16px', borderTop: '1px solid rgba(34,211,238,0.08)', display: 'flex', gap: '8px' }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendText())}
            placeholder={sessionEnded ? 'Session ended' : 'Type your response...'}
            disabled={sessionEnded || hardCutoff}
            style={{
              flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(34,211,238,0.15)',
              borderRadius: '6px', padding: '10px 14px', color: '#e2e8f0', fontFamily: 'inherit',
              fontSize: '13px', outline: 'none',
            }}
          />
          <button
            onClick={sendText}
            disabled={sessionEnded || hardCutoff || !input.trim()}
            style={{
              padding: '10px 18px', background: 'rgba(34,211,238,0.12)', border: '1px solid rgba(34,211,238,0.3)',
              borderRadius: '6px', color: '#22d3ee', cursor: 'pointer', fontFamily: 'inherit', fontSize: '12px',
            }}
          >Send</button>
        </div>
      </div>

      {/* Center: Timer */}
      <div style={{
        width: '200px', display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', borderRight: '1px solid rgba(34,211,238,0.08)', padding: '0 20px',
      }}>
        {timeBudgetSeconds != null && (
          <>
            <div style={{
              fontSize: '48px', fontWeight: 700, color: timerColor,
              fontVariantNumeric: 'tabular-nums',
              animation: remaining != null && remaining < 10 ? 'pulse 1s infinite' : 'none',
            }}>
              {remaining != null ? formatTime(remaining) : formatTime(timeBudgetSeconds)}
            </div>
            <div style={{ fontSize: '10px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginTop: '8px' }}>
              {hardCutoff ? 'TIME' : 'REMAINING'}
            </div>
          </>
        )}
        {!sessionEnded && (
          <button
            onClick={handleEnd}
            style={{
              marginTop: '32px', padding: '8px 16px', background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#ef4444',
              cursor: 'pointer', fontFamily: 'inherit', fontSize: '11px', letterSpacing: '0.08em',
            }}
          >End Session</button>
        )}
      </div>

      {/* Right: Context panel */}
      <div style={{ padding: '20px', overflowY: 'auto', fontSize: '12px' }}>
        <div style={{ color: 'rgba(148,163,184,0.5)', letterSpacing: '0.1em', marginBottom: '12px' }}>SCENARIO</div>
        <div style={{ color: '#22d3ee', marginBottom: '20px' }}>{scenarioType}</div>
        <div style={{ color: 'rgba(148,163,184,0.5)', letterSpacing: '0.1em', marginBottom: '8px' }}>SESSION</div>
        <div style={{ color: 'rgba(148,163,184,0.6)' }}>{activeSimSessionId?.slice(0, 8)}</div>
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>
    </div>
  )
}
