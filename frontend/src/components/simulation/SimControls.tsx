// frontend/src/components/simulation/SimControls.tsx

const _ip = { width: 15, height: 15, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

const IconMic     = () => <svg {..._ip}><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
const IconMicOff  = () => <svg {..._ip}><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
const IconSquare  = () => <svg {..._ip}><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
const IconBulb    = () => <svg {..._ip}><line x1="9" y1="18" x2="15" y2="18"/><line x1="10" y1="22" x2="14" y2="22"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/></svg>
const IconClock   = () => <svg {..._ip}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
const IconCheck   = () => <svg {..._ip}><polyline points="20 6 9 17 4 12"/></svg>

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
  onCoachToggle: () => void
}

function formatTime(s: number) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

export default function SimControls({
  remaining, timeBudgetSeconds, scenarioType,
  micMuted, textOpen, faceActive, showDevices, canSubmit, sessionEnded,
  onMicToggle, onSubmit, onEnd, onTextToggle, onFaceToggle, onDevicesToggle, onCoachToggle,
}: Props) {
  const timerColor = remaining == null ? '#22d3ee'
    : remaining < 10 ? '#ef4444'
    : remaining < (timeBudgetSeconds ?? Infinity) * 0.2 ? '#fbbf24'
    : '#22d3ee'

  const timerBorderColor = remaining == null ? undefined
    : remaining < 10 ? 'rgba(239,68,68,0.2)'
    : remaining < (timeBudgetSeconds ?? Infinity) * 0.2 ? 'rgba(251,191,36,0.15)'
    : undefined

  const ctrlBtn = (extraStyle?: React.CSSProperties): React.CSSProperties => ({
    width: 38, height: 38, borderRadius: '50%', cursor: 'pointer',
    border: '1px solid rgba(255,255,255,0.12)',
    background: 'rgba(255,255,255,0.05)',
    color: '#94a3b8',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'all 0.2s',
    ...extraStyle,
  })

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
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {timeBudgetSeconds != null && (
          <div style={{
            background: 'rgba(255,255,255,0.04)',
            border: `1px solid ${timerBorderColor ?? 'rgba(255,255,255,0.06)'}`,
            borderRadius: 20, padding: '4px 12px',
            fontSize: '0.68rem', fontVariantNumeric: 'tabular-nums',
            letterSpacing: '0.04em', color: timerColor,
            animation: remaining != null && remaining < 10 ? 'sim-pulse-chip 1s ease-in-out infinite' : 'none',
          }}>
            <IconClock /> {remaining != null ? formatTime(remaining) : formatTime(timeBudgetSeconds)}
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
        {/* Mic */}
        <button
          onClick={onMicToggle}
          title={micMuted ? 'Unmute' : 'Mute'}
          style={ctrlBtn(micMuted ? {
            border: '1px solid rgba(239,68,68,0.3)',
            background: 'rgba(239,68,68,0.12)',
            color: '#ef4444',
          } : {})}
        >
          {micMuted ? <IconMicOff /> : <IconMic />}
        </button>

        {/* Coach */}
        <button
          onClick={onCoachToggle}
          title="Open coach"
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(99,102,241,0.18)',
            border: '1px solid rgba(99,102,241,0.5)',
            borderRadius: 8, padding: '0 14px', height: 36,
            color: '#a5b4fc', fontSize: '0.72rem', fontWeight: 600,
            cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
            fontFamily: "'DM Mono', monospace",
          }}
        >
          <IconBulb />
          Coach
        </button>

        {/* Submit */}
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
          <IconCheck />
        </button>

        {/* End */}
        <button
          onClick={onEnd}
          disabled={sessionEnded}
          title="End session"
          style={ctrlBtn({
            border: '1px solid rgba(239,68,68,0.3)',
            background: 'rgba(239,68,68,0.1)',
            color: '#f87171',
            cursor: sessionEnded ? 'not-allowed' : 'pointer',
            opacity: sessionEnded ? 0.4 : 1,
          })}
        >
          <IconSquare />
        </button>
      </div>

      {/* Right: toggles */}
      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
        {[
          { label: 'Type',    active: textOpen,    activeColor: '#22d3ee', activeBg: 'rgba(34,211,238,0.08)',  activeBorder: 'rgba(34,211,238,0.2)',  onClick: onTextToggle },
          { label: 'Face AI', active: faceActive,  activeColor: '#a78bfa', activeBg: 'rgba(167,139,250,0.08)', activeBorder: 'rgba(167,139,250,0.2)', onClick: onFaceToggle },
          { label: 'Devices', active: showDevices, activeColor: '#fbbf24', activeBg: 'rgba(251,191,36,0.08)',  activeBorder: 'rgba(251,191,36,0.2)',  onClick: onDevicesToggle },
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
