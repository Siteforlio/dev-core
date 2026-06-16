// frontend/src/components/simulation/SimControls.tsx

interface Props {
  remaining: number | null
  timeBudgetSeconds: number | null
  scenarioType: string
  micMuted: boolean
  textOpen: boolean
  faceActive: boolean
  showDevices: boolean
  canSubmit: boolean
  sessionEnded: boolean
  onMicToggle: () => void
  onSubmit: () => void
  onEnd: () => void
  onTextToggle: () => void
  onFaceToggle: () => void
  onDevicesToggle: () => void
}

function formatTime(s: number) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

export default function SimControls({
  remaining, timeBudgetSeconds, scenarioType,
  micMuted, textOpen, faceActive, showDevices, canSubmit, sessionEnded,
  onMicToggle, onSubmit, onEnd, onTextToggle, onFaceToggle, onDevicesToggle,
}: Props) {
  const timerColor = remaining == null ? '#22d3ee'
    : remaining < 10 ? '#ef4444'
    : remaining < (timeBudgetSeconds ?? Infinity) * 0.2 ? '#fbbf24'
    : '#22d3ee'

  const timerBorderColor = remaining == null ? undefined
    : remaining < 10 ? 'rgba(239,68,68,0.2)'
    : remaining < (timeBudgetSeconds ?? Infinity) * 0.2 ? 'rgba(251,191,36,0.15)'
    : undefined

  return (
    <div style={{
      background: 'rgba(5,9,15,0.97)',
      padding: '12px 20px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      borderTop: '1px solid rgba(34,211,238,0.07)',
      flexShrink: 0, gap: 12, zIndex: 10,
      fontFamily: "'DM Mono', monospace",
    }}>
      {/* Left: info chips */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {timeBudgetSeconds != null && (
          <div style={{
            background: 'rgba(255,255,255,0.04)',
            border: `1px solid ${timerBorderColor ?? 'rgba(255,255,255,0.06)'}`,
            borderRadius: 20, padding: '4px 12px',
            fontSize: '0.68rem', fontVariantNumeric: 'tabular-nums',
            letterSpacing: '0.04em', color: timerColor,
            animation: remaining != null && remaining < 10 ? 'sim-pulse-chip 1s ease-in-out infinite' : 'none',
          }}>
            ⏱ {remaining != null ? formatTime(remaining) : formatTime(timeBudgetSeconds)}
          </div>
        )}
        <div style={{
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: 20, padding: '4px 12px',
          fontSize: '0.65rem', color: '#475569', letterSpacing: '0.04em',
        }}>
          {scenarioType || 'simulation'}
        </div>
      </div>

      {/* Center: action buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button
          onClick={onMicToggle}
          title={micMuted ? 'Unmute' : 'Mute'}
          style={{
            width: 38, height: 38, borderRadius: '50%', cursor: 'pointer',
            border: micMuted ? '1px solid rgba(239,68,68,0.2)' : '1px solid rgba(255,255,255,0.08)',
            background: micMuted ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.04)',
            color: micMuted ? '#ef4444' : '#475569',
            fontSize: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.2s',
          }}
        >
          {micMuted ? '🔇' : '🎙'}
        </button>

        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          title="Submit"
          style={{
            width: 48, height: 48, borderRadius: '50%', border: 'none',
            background: canSubmit ? '#22d3ee' : 'rgba(34,211,238,0.3)',
            color: '#050915', fontSize: '1.1rem', fontWeight: 700,
            cursor: canSubmit ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: canSubmit ? '0 0 20px rgba(34,211,238,0.3)' : 'none',
            transition: 'all 0.2s',
          }}
        >
          ✓
        </button>

        <button
          onClick={onEnd}
          disabled={sessionEnded}
          title="End session"
          style={{
            width: 38, height: 38, borderRadius: '50%', cursor: sessionEnded ? 'not-allowed' : 'pointer',
            border: '1px solid rgba(239,68,68,0.15)',
            background: 'rgba(239,68,68,0.07)',
            color: 'rgba(239,68,68,0.65)', fontSize: '0.9rem',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.2s',
          }}
        >
          ■
        </button>
      </div>

      {/* Right: toggles */}
      <div style={{ display: 'flex', gap: 8 }}>
        {[
          { label: 'Type', active: textOpen, activeColor: '#22d3ee', activeBg: 'rgba(34,211,238,0.08)', activeBorder: 'rgba(34,211,238,0.2)', onClick: onTextToggle },
          { label: 'Face AI', active: faceActive, activeColor: '#a78bfa', activeBg: 'rgba(167,139,250,0.08)', activeBorder: 'rgba(167,139,250,0.2)', onClick: onFaceToggle },
          { label: 'Devices', active: showDevices, activeColor: '#fbbf24', activeBg: 'rgba(251,191,36,0.08)', activeBorder: 'rgba(251,191,36,0.2)', onClick: onDevicesToggle },
        ].map(({ label, active, activeColor, activeBg, activeBorder, onClick }) => (
          <button
            key={label}
            onClick={onClick}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: active ? activeBg : 'rgba(255,255,255,0.03)',
              border: `1px solid ${active ? activeBorder : 'rgba(255,255,255,0.07)'}`,
              borderRadius: 8, padding: '6px 12px', cursor: 'pointer',
              fontFamily: "'DM Mono', monospace", fontSize: '0.65rem',
              fontWeight: 500, color: active ? activeColor : '#475569',
              letterSpacing: '0.04em', transition: 'all 0.2s',
            }}
          >
            <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor', flexShrink: 0 }} />
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
