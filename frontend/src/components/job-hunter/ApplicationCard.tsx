import StatusBadge from './StatusBadge'
import type { Application } from '../../types/jobHunter'

interface Props {
  application: Application
  onStartInterviewPrep: (applicationId: string) => void
  onApply: (applicationId: string) => void
  onViewTracking: (applicationId: string) => void
}

const MATCH_BAR: Record<string, { fill: string; glow: string; pct: number }> = {
  MATCH:   { fill: '#34d399', glow: 'rgba(52,211,153,0.5)',  pct: 95 },
  PARTIAL: { fill: '#fbbf24', glow: 'rgba(251,191,36,0.5)',  pct: 55 },
  SKIP:    { fill: '#6b7280', glow: 'rgba(107,114,128,0.3)', pct: 15 },
}

function MatchBar({ score }: { score: string | null }) {
  const cfg = score ? (MATCH_BAR[score] ?? MATCH_BAR.SKIP) : MATCH_BAR.SKIP
  return (
    <div className="flex items-center gap-2 min-w-0" style={{ width: '140px' }}>
      <div
        className="flex-1 rounded-full overflow-hidden"
        style={{ height: '4px', background: 'rgba(255,255,255,0.06)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${cfg.pct}%`,
            background: cfg.fill,
            boxShadow: `0 0 6px ${cfg.glow}`,
          }}
        />
      </div>
      <span
        className="text-[10px] font-mono flex-shrink-0"
        style={{ color: cfg.fill, minWidth: '44px' }}
      >
        {score ?? 'SKIP'}
      </span>
    </div>
  )
}

export default function ApplicationCard({ application, onStartInterviewPrep, onApply, onViewTracking }: Props) {
  const { id, company, title, location, appliedAt, status, matchScore, source, appliedElsewhere } = application
  const isApplied = status === 'applied' || status === 'interview' || status === 'offer' || status === 'responded'
  const showInterviewPrep = status === 'interview'
  const appliedDate = appliedAt ? new Date(appliedAt).toLocaleDateString('en-GB') : '—'

  return (
    <div
      className="grid items-center transition-all duration-150 cursor-default group"
      style={{
        gridTemplateColumns: '1fr 1fr 160px 100px 90px 100px',
        padding: '10px 16px',
        borderBottom: appliedElsewhere
          ? '1px solid rgba(251,191,36,0.12)'
          : '1px solid rgba(34,211,238,0.05)',
        background: appliedElsewhere ? 'rgba(251,191,36,0.03)' : 'transparent',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = appliedElsewhere ? 'rgba(251,191,36,0.06)' : 'rgba(34,211,238,0.03)')}
      onMouseLeave={e => (e.currentTarget.style.background = appliedElsewhere ? 'rgba(251,191,36,0.03)' : 'transparent')}
    >
      {/* Company */}
      <div className="min-w-0 pr-3">
        <div className="flex items-center gap-2">
          <p
            className="text-sm font-semibold truncate"
            style={{ color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace' }}
          >
            {company}
          </p>
          {appliedElsewhere && (
            <span
              title="You've already applied to this role in another campaign"
              style={{
                fontSize: 9,
                fontFamily: 'monospace',
                letterSpacing: '0.06em',
                padding: '2px 6px',
                borderRadius: 3,
                background: 'rgba(251,191,36,0.12)',
                border: '1px solid rgba(251,191,36,0.3)',
                color: '#fbbf24',
                flexShrink: 0,
                whiteSpace: 'nowrap',
              }}
            >
              APPLIED
            </span>
          )}
        </div>
      </div>

      {/* Role */}
      <div className="min-w-0 pr-3">
        <p
          className="text-xs truncate"
          style={{ color: 'rgba(148,163,184,0.7)', fontFamily: 'monospace' }}
        >
          {title}
        </p>
        {location && (
          <p
            className="text-[10px] truncate mt-0.5"
            style={{ color: 'rgba(100,116,139,0.6)', fontFamily: 'monospace' }}
          >
            {location}
          </p>
        )}
        {source && (
          <span
            className="inline-block text-[9px] font-mono px-1.5 py-px rounded mt-1"
            style={{
              background: 'rgba(34,211,238,0.07)',
              border: '1px solid rgba(34,211,238,0.15)',
              color: 'rgba(34,211,238,0.5)',
            }}
          >
            {source}
          </span>
        )}
      </div>

      {/* Match bar */}
      <MatchBar score={matchScore ?? null} />

      {/* Status badge */}
      <div>
        <StatusBadge variant="status" value={status} />
      </div>

      {/* Date */}
      <span
        className="text-[11px] font-mono"
        style={{ color: 'rgba(100,116,139,0.7)' }}
      >
        {appliedDate}
      </span>

      {/* Actions */}
      <div className="flex items-center gap-1.5 justify-end">
        {showInterviewPrep && (
          <button
            onClick={() => onStartInterviewPrep(id)}
            aria-label="Interview Prep"
            className="flex items-center justify-center rounded transition-all duration-150"
            style={{
              width: '28px', height: '28px',
              color: 'rgba(167,139,250,0.7)',
              background: 'rgba(167,139,250,0.08)',
              border: '1px solid rgba(167,139,250,0.2)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = '#a78bfa'
              e.currentTarget.style.background = 'rgba(167,139,250,0.15)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'rgba(167,139,250,0.7)'
              e.currentTarget.style.background = 'rgba(167,139,250,0.08)'
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </button>
        )}
        {isApplied ? (
          <button
            onClick={() => onViewTracking(id)}
            aria-label="Track"
            className="flex items-center justify-center rounded transition-all duration-150"
            style={{
              width: '28px', height: '28px',
              color: 'rgba(148,163,184,0.5)',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.07)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = '#22d3ee'
              e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'rgba(148,163,184,0.5)'
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </button>
        ) : (
          <button
            onClick={() => onApply(id)}
            aria-label="Apply"
            className="flex items-center justify-center rounded transition-all duration-150"
            style={{
              width: '28px', height: '28px',
              color: 'rgba(34,211,238,0.6)',
              background: 'rgba(34,211,238,0.06)',
              border: '1px solid rgba(34,211,238,0.15)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = '#22d3ee'
              e.currentTarget.style.background = 'rgba(34,211,238,0.12)'
              e.currentTarget.style.borderColor = 'rgba(34,211,238,0.35)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'rgba(34,211,238,0.6)'
              e.currentTarget.style.background = 'rgba(34,211,238,0.06)'
              e.currentTarget.style.borderColor = 'rgba(34,211,238,0.15)'
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}
