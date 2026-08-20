import { useState, useEffect } from 'react'
import { useOverlayStore } from '../../../store/overlayStore'

interface Props {
  heroKicker: string
  meetingTitle: string
  heroTime: string
  heroRoom: string
  heroAttendees: number
  countdownLabel: string
  countdownText: string
  meetingStarted: boolean
  onStartSession: () => void
  isLive?: boolean  // realtime live badge from now tick
}

function useElapsedTimer(startedAt: number | null): string {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!startedAt) { setElapsed(0); return }
    const tick = () => setElapsed(Math.floor((Date.now() - startedAt) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [startedAt])
  const h = Math.floor(elapsed / 3600)
  const m = Math.floor((elapsed % 3600) / 60)
  const s = elapsed % 60
  return h > 0
    ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export default function DebriefHeroPanel({
  heroKicker,
  meetingTitle,
  heroTime,
  heroRoom,
  heroAttendees,
  countdownLabel,
  countdownText,
  meetingStarted,
  onStartSession,
  isLive,
}: Props) {
  const sessionId = useOverlayStore((s) => s.sessionId)
  const sessionState = useOverlayStore((s) => s.state)
  const sessionStartedAt = useOverlayStore((s) => s.sessionStartedAt)
  const isSessionActive = !!sessionId
  const isConnecting = isSessionActive && sessionState === 'idle'
  const elapsedLabel = useElapsedTimer(isSessionActive && !isConnecting ? sessionStartedAt : null)
  return (
    <div style={{
      position: 'relative',
      overflow: 'hidden',
      padding: '24px 28px',
      borderRadius: '16px',
      background: 'linear-gradient(135deg, #050d18 0%, #0a1628 100%)',
      border: '1px solid rgba(34,211,238,0.15)',
      boxShadow: '0 0 40px rgba(34,211,238,0.04), inset 0 1px 0 rgba(34,211,238,0.08)',
    }}>
      {/* Subtle glow */}
      <div style={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: '300px',
        height: '200px',
        background: 'radial-gradient(ellipse at top right, rgba(34,211,238,0.08), transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div style={{
        position: 'relative',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '24px',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        {/* Left: meeting info */}
        <div style={{ minWidth: '200px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: isLive ? '#f87171' : '#22d3ee',
            marginBottom: '10px',
          }}>
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: isLive ? '#ef4444' : '#22d3ee',
              animation: 'dcPulse 2s ease-in-out infinite',
              flexShrink: 0,
            }} />
            {isLive ? 'Live now' : heroKicker}
          </div>

          <div style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 700,
            fontSize: 'clamp(20px,2.8vw,28px)',
            letterSpacing: '-0.02em',
            color: '#f1f5f9',
            marginBottom: '10px',
            lineHeight: 1.1,
          }}>
            {meetingTitle}
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', fontSize: '12.5px', fontWeight: 500, color: 'rgba(148,163,184,0.65)' }}>
            <MetaItem>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="9" stroke="#22d3ee" strokeWidth="1.8"/>
                <path d="M12 7v5l3 2" stroke="#22d3ee" strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
              {heroTime}
            </MetaItem>
            <MetaItem>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                <path d="M12 21c5-4.5 7-7.6 7-11a7 7 0 1 0-14 0c0 3.4 2 6.5 7 11Z" stroke="#22d3ee" strokeWidth="1.8"/>
                <circle cx="12" cy="10" r="2.4" stroke="#22d3ee" strokeWidth="1.8"/>
              </svg>
              {heroRoom}
            </MetaItem>
            <MetaItem>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                <path d="M16 19v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 17.5V19M9.5 10.5A3.25 3.25 0 1 0 9.5 4a3.25 3.25 0 0 0 0 6.5ZM20 19v-1.5a3.5 3.5 0 0 0-2.6-3.4M15.5 4.2a3.25 3.25 0 0 1 0 6.1" stroke="#22d3ee" strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
              {heroAttendees} attendees
            </MetaItem>
          </div>
        </div>

        {/* Right: elapsed counter (when active) or countdown + action */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
          {isSessionActive ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'rgba(52,211,153,0.6)',
                marginBottom: '4px',
                fontFamily: 'monospace',
              }}>
                Live
              </div>
              <div style={{
                fontFamily: "'Space Grotesk', monospace",
                fontWeight: 700,
                fontSize: 'clamp(34px,5vw,56px)',
                lineHeight: 1,
                letterSpacing: '-0.02em',
                fontVariantNumeric: 'tabular-nums',
                color: '#34d399',
                textShadow: '0 0 30px rgba(52,211,153,0.3)',
              }}>
                {elapsedLabel}
              </div>
            </div>
          ) : meetingStarted ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'rgba(148,163,184,0.45)',
                marginBottom: '4px',
                fontFamily: 'monospace',
              }}>
                {countdownLabel}
              </div>
              <div style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 700,
                fontSize: 'clamp(34px,5vw,56px)',
                lineHeight: 1,
                letterSpacing: '-0.02em',
                fontVariantNumeric: 'tabular-nums',
                color: '#22d3ee',
                textShadow: '0 0 30px rgba(34,211,238,0.3)',
              }}>
                {countdownText}
              </div>
            </div>
          ) : null}

          <button
            onClick={onStartSession}
            disabled={isSessionActive}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '11px 22px',
              border: 'none',
              borderRadius: '10px',
              background: isConnecting
                ? 'rgba(34,211,238,0.06)'
                : isSessionActive
                ? 'rgba(52,211,153,0.06)'
                : 'linear-gradient(180deg, rgba(34,211,238,0.18), rgba(34,211,238,0.1))',
              borderColor: isConnecting ? 'rgba(34,211,238,0.2)' : isSessionActive ? 'rgba(52,211,153,0.15)' : 'rgba(34,211,238,0.35)',
              borderStyle: 'solid',
              borderWidth: '1px',
              color: isConnecting ? 'rgba(34,211,238,0.6)' : isSessionActive ? 'rgba(52,211,153,0.5)' : '#22d3ee',
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700,
              fontSize: '13.5px',
              cursor: isSessionActive ? 'not-allowed' : 'pointer',
              transition: 'all .18s ease',
              outline: 'none',
              letterSpacing: '0.02em',
            } as React.CSSProperties}
            onMouseEnter={e => {
              if (!isSessionActive) {
                e.currentTarget.style.background = 'linear-gradient(180deg, rgba(34,211,238,0.24), rgba(34,211,238,0.14))'
                e.currentTarget.style.boxShadow = '0 0 20px rgba(34,211,238,0.15)'
              }
            }}
            onMouseLeave={e => {
              if (!isSessionActive) {
                e.currentTarget.style.background = 'linear-gradient(180deg, rgba(34,211,238,0.18), rgba(34,211,238,0.1))'
                e.currentTarget.style.boxShadow = 'none'
              }
            }}
          >
            {isConnecting ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ animation: 'spin 1s linear infinite' }}>
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                {isSessionActive
                  ? <path d="M8 6h3v12H8zM13 6h3v12h-3z" fill="currentColor"/>
                  : <path d="M7 5v14l12-7z" fill="currentColor"/>
                }
              </svg>
            )}
            {isConnecting ? 'Starting…' : isSessionActive ? 'Session active' : 'Start meeting'}
          </button>
        </div>
      </div>
    </div>
  )
}

function MetaItem({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
      {children}
    </span>
  )
}
