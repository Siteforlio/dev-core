// frontend/src/components/simulation/SimulationDebrief.tsx
import { useSimulationStore } from '../../store/simulationStore'
import { apiFetch } from '../../lib/apiFetch'

interface Props {
  debrief: {
    overall_score: number
    hire_signal: string
    core_scores: Record<string, number>
    scenario_scores: Record<string, number>
    summary: string
    strengths: string[]
    improvements: string[]
    focus_areas: string[]
  }
  onDismiss: () => void
}

const HIRE_COLORS: Record<string, string> = {
  strong_yes: '#22c55e', yes: '#86efac', borderline: '#f59e0b',
  no: '#f87171', strong_no: '#ef4444',
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '12px' }}>
        <span style={{ color: 'rgba(226,232,240,0.8)' }}>{label.replace(/_/g, ' ')}</span>
        <span style={{ color: '#22d3ee', fontVariantNumeric: 'tabular-nums' }}>{score.toFixed(1)}</span>
      </div>
      <div style={{ height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px' }}>
        <div style={{
          height: '100%', borderRadius: '2px',
          width: `${(score / 10) * 100}%`,
          background: score >= 7 ? '#22d3ee' : score >= 5 ? '#f59e0b' : '#ef4444',
          transition: 'width 0.8s ease',
        }} />
      </div>
    </div>
  )
}

export default function SimulationDebrief({ debrief, onDismiss }: Props) {
  const { activeSimSessionId } = useSimulationStore()

  const downloadReport = async () => {
    const res = await apiFetch(`/api/v1/sim-sessions/${activeSimSessionId}/report`)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sim-report-${activeSimSessionId?.slice(0, 8) ?? 'report'}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  const hireColor = HIRE_COLORS[debrief.hire_signal] ?? '#94a3b8'

  return (
    <div style={{
      height: '100%', overflowY: 'auto', padding: '32px 40px',
      background: '#070f1c', color: '#e2e8f0', fontFamily: 'JetBrains Mono, monospace',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px', marginBottom: '32px' }}>
        <div>
          <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginBottom: '6px' }}>
            OVERALL SCORE
          </div>
          <div style={{ fontSize: '56px', fontWeight: 700, color: '#22d3ee', lineHeight: 1 }}>
            {debrief.overall_score.toFixed(1)}
          </div>
          <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.4)', marginTop: '4px' }}>out of 10</div>
        </div>
        <div style={{
          padding: '8px 20px', borderRadius: '20px', border: `1px solid ${hireColor}`,
          color: hireColor, fontSize: '13px', fontWeight: 600, letterSpacing: '0.08em',
          background: `${hireColor}15`,
        }}>
          {debrief.hire_signal.replace(/_/g, ' ').toUpperCase()}
        </div>
        <div style={{ flex: 1 }} />
        <button onClick={downloadReport} style={{
          padding: '10px 20px', background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.25)',
          borderRadius: '6px', color: '#22d3ee', cursor: 'pointer', fontFamily: 'inherit',
          fontSize: '11px', letterSpacing: '0.1em',
        }}>↓ DOWNLOAD PDF</button>
        <button onClick={onDismiss} style={{
          padding: '10px 20px', background: 'rgba(148,163,184,0.06)', border: '1px solid rgba(148,163,184,0.15)',
          borderRadius: '6px', color: 'rgba(148,163,184,0.7)', cursor: 'pointer', fontFamily: 'inherit',
          fontSize: '11px', letterSpacing: '0.1em',
        }}>← BACK</button>
      </div>

      {/* Summary */}
      {debrief.summary && (
        <div style={{
          padding: '16px 20px', background: 'rgba(34,211,238,0.04)',
          border: '1px solid rgba(34,211,238,0.1)', borderRadius: '8px', marginBottom: '28px',
          fontSize: '14px', lineHeight: 1.7, color: 'rgba(226,232,240,0.85)',
        }}>{debrief.summary}</div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '28px', marginBottom: '28px' }}>
        {/* Core scores */}
        <div>
          <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginBottom: '14px' }}>
            CORE DIMENSIONS
          </div>
          {Object.entries(debrief.core_scores || {}).map(([k, v]) => (
            <ScoreBar key={k} label={k} score={v} />
          ))}
        </div>
        {/* Scenario scores */}
        {Object.keys(debrief.scenario_scores || {}).length > 0 && (
          <div>
            <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginBottom: '14px' }}>
              SCENARIO DIMENSIONS
            </div>
            {Object.entries(debrief.scenario_scores || {}).map(([k, v]) => (
              <ScoreBar key={k} label={k} score={v} />
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '28px' }}>
        {/* Strengths */}
        <div>
          <div style={{ fontSize: '11px', color: '#22c55e', letterSpacing: '0.12em', marginBottom: '12px' }}>
            STRENGTHS
          </div>
          {debrief.strengths.map((s, i) => (
            <div key={i} style={{ fontSize: '13px', marginBottom: '8px', paddingLeft: '12px', borderLeft: '2px solid rgba(34,197,94,0.4)' }}>
              {s}
            </div>
          ))}
        </div>
        {/* Improvements */}
        <div>
          <div style={{ fontSize: '11px', color: '#f59e0b', letterSpacing: '0.12em', marginBottom: '12px' }}>
            IMPROVE
          </div>
          {debrief.improvements.map((s, i) => (
            <div key={i} style={{ fontSize: '13px', marginBottom: '8px', paddingLeft: '12px', borderLeft: '2px solid rgba(245,158,11,0.4)' }}>
              {s}
            </div>
          ))}
        </div>
      </div>

      {/* Focus areas */}
      {debrief.focus_areas?.length > 0 && (
        <div>
          <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginBottom: '12px' }}>
            TOP FOCUS AREAS
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {debrief.focus_areas.map((f, i) => (
              <div key={i} style={{
                padding: '8px 16px', background: 'rgba(155,123,255,0.1)',
                border: '1px solid rgba(155,123,255,0.25)', borderRadius: '20px',
                color: '#9b7bff', fontSize: '12px',
              }}>
                {f}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
