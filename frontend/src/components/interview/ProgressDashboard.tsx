// frontend/src/components/interview/ProgressDashboard.tsx
import {
  RadialBarChart, RadialBar, ResponsiveContainer,
} from 'recharts'
import { useProgress } from '../../hooks/useProgress'

const DIMENSION_LABELS: Record<string, string> = {
  domain_knowledge: 'Domain Knowledge',
  communication_clarity: 'Communication',
  quantified_impact: 'Quantified Impact',
  leadership_narrative: 'Leadership',
  culture_alignment: 'Culture Fit',
  executive_presence: 'Executive Presence',
  problem_solving: 'Problem Solving',
}

function barColor(score: number) {
  if (score >= 7) return '#22c55e'
  if (score >= 5) return '#f59e0b'
  return '#ef4444'
}

export default function ProgressDashboard({ onStartNew }: { onStartNew: () => void }) {
  const { data, loading } = useProgress()

  const avgPct = data ? Math.round((data.average_score / 10) * 100) : 0

  const dimensionBars = data
    ? Object.entries(data.dimensions).map(([dim, score]) => ({
        name: DIMENSION_LABELS[dim] ?? dim,
        score: Math.round(score * 10) / 10,
        pct: Math.round((score / 10) * 100),
      }))
    : []

  const donutData = [{ name: 'Score', value: avgPct, fill: '#22d3ee' }]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p style={{ color: 'rgba(34,211,238,0.4)', fontFamily: 'monospace', fontSize: '13px' }}>
          Loading progress…
        </p>
      </div>
    )
  }

  if (!data || data.total_sessions === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p style={{ color: 'rgba(226,232,240,0.4)', fontFamily: 'monospace', fontSize: '13px' }}>
          Complete your first session to see progress
        </p>
        <button
          onClick={onStartNew}
          style={{
            background: 'rgba(34,211,238,0.1)',
            border: '1px solid rgba(34,211,238,0.35)',
            color: '#22d3ee',
            fontFamily: 'monospace',
            fontSize: '11px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.14em',
            padding: '8px 20px',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          Start First Session
        </button>
      </div>
    )
  }

  return (
    <div className="w-full space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        {[
          { label: 'Sessions Taken', value: data.total_sessions },
          { label: 'Average Score', value: `${avgPct}%` },
          {
            label: 'Strongest Skill',
            value: dimensionBars.length
              ? (DIMENSION_LABELS[Object.entries(data.dimensions).sort((a, b) => b[1] - a[1])[0]?.[0]] ?? '—')
              : '—',
          },
          {
            label: 'Needs Work',
            value: dimensionBars.length
              ? (DIMENSION_LABELS[Object.entries(data.dimensions).sort((a, b) => a[1] - b[1])[0]?.[0]] ?? '—')
              : '—',
          },
        ].map((card) => (
          <div
            key={card.label}
            style={{
              background: 'rgba(7,15,28,0.6)',
              border: '1px solid rgba(34,211,238,0.1)',
              borderRadius: '10px',
              padding: '16px',
            }}
          >
            <p style={{ color: 'rgba(34,211,238,0.45)', fontFamily: 'monospace', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '6px' }}>
              {card.label}
            </p>
            <p style={{ color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace', fontSize: '22px', fontWeight: 700 }}>
              {card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Skill Breakdown */}
      <div
        style={{
          background: 'rgba(7,15,28,0.6)',
          border: '1px solid rgba(34,211,238,0.1)',
          borderRadius: '10px',
          padding: '20px',
        }}
      >
        <div className="flex items-start gap-6">
          {/* Donut */}
          <div style={{ width: 120, height: 120, flexShrink: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart innerRadius={32} outerRadius={52} data={donutData} startAngle={90} endAngle={-270}>
                <RadialBar dataKey="value" cornerRadius={6} background={{ fill: 'rgba(34,211,238,0.08)' }} />
              </RadialBarChart>
            </ResponsiveContainer>
            <p style={{ textAlign: 'center', color: 'rgba(226,232,240,0.8)', fontFamily: 'monospace', fontSize: '14px', fontWeight: 700, marginTop: '-64px' }}>
              {avgPct}%
            </p>
          </div>

          {/* Bars */}
          <div className="flex-1 space-y-2">
            <p style={{ color: 'rgba(34,211,238,0.45)', fontFamily: 'monospace', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '10px' }}>
              Skill Breakdown
            </p>
            {dimensionBars.map((d) => (
              <div key={d.name} className="flex items-center gap-3">
                <span style={{ color: 'rgba(226,232,240,0.6)', fontFamily: 'monospace', fontSize: '11px', width: '130px', flexShrink: 0 }}>
                  {d.name}
                </span>
                <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${d.pct}%`, height: '100%', background: barColor(d.score), borderRadius: '3px', transition: 'width 0.6s ease' }} />
                </div>
                <span style={{ color: 'rgba(226,232,240,0.5)', fontFamily: 'monospace', fontSize: '11px', width: '36px', textAlign: 'right' }}>
                  {d.pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CTA */}
      <button
        onClick={onStartNew}
        style={{
          width: '100%',
          background: 'rgba(34,211,238,0.08)',
          border: '1px solid rgba(34,211,238,0.2)',
          color: '#22d3ee',
          fontFamily: 'monospace',
          fontSize: '11px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.14em',
          padding: '12px',
          borderRadius: '8px',
          cursor: 'pointer',
        }}
      >
        + Start New Session
      </button>
    </div>
  )
}
