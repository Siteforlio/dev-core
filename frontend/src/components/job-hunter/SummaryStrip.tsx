import type { CampaignSummary } from '../../types/jobHunter'

interface Props {
  summary: CampaignSummary
  compact?: boolean
}

/* ── Circular arc progress ring ── */
function Ring({
  pct, color, size = 56, stroke = 5, label, value,
}: {
  pct: number; color: string; size?: number; stroke?: number; label: string; value: string
}) {
  const r = (size - stroke * 2) / 2
  const circ = 2 * Math.PI * r
  const offset = circ - (Math.min(pct, 100) / 100) * circ
  const cx = size / 2
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          {/* Track */}
          <circle cx={cx} cy={cx} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={stroke} />
          {/* Fill */}
          <circle
            cx={cx} cy={cx} r={r} fill="none"
            stroke={color} strokeWidth={stroke}
            strokeDasharray={circ}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.8s ease', filter: `drop-shadow(0 0 4px ${color}80)` }}
          />
        </svg>
        {/* Center text */}
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontFamily: 'monospace', fontSize: '11px', fontWeight: 700, color: 'rgba(226,232,240,0.9)' }}>{value}</span>
        </div>
      </div>
      <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.6)' }}>{label}</span>
    </div>
  )
}

/* ── Mini bar sparkline ── */
function Sparkline({ bars, color, peak }: { bars: number[]; color: string; peak: number }) {
  const max = Math.max(...bars, peak, 1)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '28px' }}>
      {bars.map((v, i) => {
        const h = Math.max(2, (v / max) * 28)
        const isLast = i === bars.length - 1
        return (
          <div key={i} style={{
            flex: 1,
            height: `${h}px`,
            borderRadius: '2px 2px 0 0',
            background: isLast ? color : `${color}40`,
            boxShadow: isLast ? `0 0 6px ${color}60` : 'none',
            transition: 'height 0.6s ease',
          }} />
        )
      })}
    </div>
  )
}

/* ── Semi-circle gauge ── */
function Gauge({ pct, color }: { pct: number; color: string }) {
  const r = 28, stroke = 5
  const circ = Math.PI * r   // half circle
  const offset = circ - (Math.min(pct, 100) / 100) * circ
  return (
    <svg width="72" height="40" viewBox="0 0 72 40">
      {/* Track */}
      <path d="M 8 36 A 28 28 0 0 1 64 36" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} strokeLinecap="round" />
      {/* Fill */}
      <path
        d="M 8 36 A 28 28 0 0 1 64 36"
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        style={{ filter: `drop-shadow(0 0 4px ${color}80)`, transition: 'stroke-dashoffset 0.8s ease' }}
      />
    </svg>
  )
}

/* ── Funnel stage ── */
function FunnelStage({ label, count, total, color, isLast }: { label: string; count: number; total: number; color: string; isLast?: boolean }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  const barW = total > 0 ? Math.max(4, (count / total) * 100) : 4
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px', position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)' }}>{label}</span>
        <span style={{ fontFamily: 'monospace', fontSize: '9px', color: `${color}aa` }}>{pct}%</span>
      </div>
      {/* Bar track */}
      <div style={{ height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${barW}%`, background: color, borderRadius: '2px', boxShadow: `0 0 6px ${color}60`, transition: 'width 0.8s ease' }} />
      </div>
      <span style={{ fontFamily: 'monospace', fontSize: '20px', fontWeight: 700, color: 'rgba(226,232,240,0.9)', lineHeight: 1 }}>{count}</span>
      {/* Connector arrow */}
      {!isLast && (
        <div style={{ position: 'absolute', right: '-10px', top: '50%', transform: 'translateY(-50%)', zIndex: 2 }}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <polyline points="2,2 8,5 2,8" stroke="rgba(34,211,238,0.2)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      )}
    </div>
  )
}

export default function SummaryStrip({ summary, compact }: Props) {
  const {
    totalApplications: total,
    todayApplications: today,
    weekApplications: week,
    responses,
    interviews,
    offers,
    rejectionRate,
  } = summary

  const responsePct  = total > 0 ? Math.round((responses  / total) * 100) : 0
  const interviewPct = total > 0 ? Math.round((interviews / total) * 100) : 0
  const offerPct     = total > 0 ? Math.round((offers     / total) * 100) : 0

  // Synthetic 7-day sparkline distributed from weekApplications
  const genBars = (peak: number) => {
    if (peak === 0) return [0, 0, 0, 0, 0, 0, 0]
    const rough = [0.08, 0.12, 0.18, 0.14, 0.20, 0.16, 0.12]
    const sum = rough.reduce((a, b) => a + b, 0)
    return rough.map((r) => Math.round((r / sum) * peak))
  }
  const weekBars = genBars(week)
  weekBars[weekBars.length - 1] = today  // today is the last bar

  /* ── COMPACT MODE (narrow sidebar) ── */
  if (compact) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
        {[
          { label: 'Sent',       value: total },
          { label: 'Responses',  value: responses },
          { label: 'Interviews', value: interviews },
          { label: 'Offers',     value: offers },
          { label: 'This Week',  value: week },
          { label: 'Rejection',  value: `${rejectionRate}%` },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: 'rgba(34,211,238,0.03)', border: '1px solid rgba(34,211,238,0.07)', borderRadius: '8px', padding: '8px 10px' }}>
            <span style={{ display: 'block', fontFamily: 'monospace', fontSize: '8px', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)', marginBottom: '2px' }}>{label}</span>
            <span style={{ fontFamily: 'monospace', fontSize: '16px', fontWeight: 700, color: 'rgba(226,232,240,0.9)' }}>{value}</span>
          </div>
        ))}
      </div>
    )
  }

  /* ── FULL MODE ── */
  return (
    <>
    <style>{`
      .ss-grid {
        display: grid;
        grid-template-columns: 1fr 1.6fr 1fr;
        gap: 24px;
        align-items: start;
      }
      .ss-col2 {
        border-left: 1px solid rgba(34,211,238,0.06);
        border-right: 1px solid rgba(34,211,238,0.06);
        border-top: none;
        border-bottom: none;
        padding: 0 24px;
      }
      /* Medium: 2 columns — rings + weekly side by side, funnel spans full width below */
      @media (max-width: 860px) {
        .ss-grid {
          grid-template-columns: 1fr 1fr;
          gap: 18px;
        }
        .ss-col2 {
          grid-column: 1 / -1;
          border-left: none;
          border-right: none;
          border-top: 1px solid rgba(34,211,238,0.06);
          border-bottom: 1px solid rgba(34,211,238,0.06);
          padding: 16px 0;
        }
      }
      /* Small: single column stack */
      @media (max-width: 540px) {
        .ss-grid {
          grid-template-columns: 1fr;
          gap: 16px;
        }
        .ss-col2 {
          grid-column: 1;
          border-top: 1px solid rgba(34,211,238,0.06);
          border-bottom: 1px solid rgba(34,211,238,0.06);
          padding: 16px 0;
        }
        .ss-rings-row {
          justify-content: space-evenly !important;
        }
        .ss-funnel-row {
          flex-wrap: wrap;
          gap: 14px !important;
        }
        .ss-funnel-row > * {
          min-width: calc(50% - 8px);
        }
        .ss-weekly-gauge {
          flex-direction: row !important;
          gap: 20px !important;
          align-items: flex-start;
        }
        .ss-weekly-gauge > * {
          flex: 1;
        }
      }
    `}</style>
    <div className="ss-grid" style={{
      background: 'rgba(7,15,28,0.7)',
      border: '1px solid rgba(34,211,238,0.08)',
      borderRadius: '14px',
      padding: '20px 24px',
    }}>

      {/* ── Col 1: Rings ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div>
          <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.45)' }}>
            Conversion Rates
          </span>
        </div>
        <div className="ss-rings-row" style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'flex-start' }}>
          <Ring pct={responsePct}  color="#22d3ee" label="Response"  value={`${responsePct}%`}  />
          <Ring pct={interviewPct} color="#34d399" label="Interview" value={`${interviewPct}%`} />
          <Ring pct={offerPct}     color="#fbbf24" label="Offer"     value={`${offerPct}%`}     />
        </div>
      </div>

      {/* ── Col 2: Pipeline funnel ── */}
      <div className="ss-col2" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.45)' }}>
          Application Pipeline
        </span>
        <div className="ss-funnel-row" style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
          <FunnelStage label="Sent"      count={total}      total={total}  color="#22d3ee" />
          <FunnelStage label="Responses" count={responses}  total={total}  color="#38bdf8" />
          <FunnelStage label="Interview" count={interviews} total={total}  color="#34d399" />
          <FunnelStage label="Offers"    count={offers}     total={total}  color="#fbbf24" isLast />
        </div>

        {/* Tiny stacked progress track */}
        <div style={{ height: '3px', borderRadius: '2px', background: 'rgba(255,255,255,0.04)', position: 'relative', overflow: 'hidden', marginTop: '4px' }}>
          {total > 0 && [
            { pct: (offers / total) * 100,     color: '#fbbf24' },
            { pct: (interviews / total) * 100, color: '#34d399' },
            { pct: (responses / total) * 100,  color: '#38bdf8' },
            { pct: 100,                        color: 'rgba(34,211,238,0.15)' },
          ].map(({ pct, color }, i) => (
            <div key={i} style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pct}%`, background: color, transition: 'width 0.8s ease' }} />
          ))}
        </div>
      </div>

      {/* ── Col 3: Weekly bars + gauge ── */}
      <div className="ss-weekly-gauge" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Weekly activity */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
            <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.45)' }}>
              Weekly Activity
            </span>
            <span style={{ fontFamily: 'monospace', fontSize: '10px', color: '#22d3ee', fontWeight: 700 }}>
              {week} <span style={{ fontSize: '9px', color: 'rgba(100,116,139,0.5)', fontWeight: 400 }}>this wk</span>
            </span>
          </div>
          <Sparkline bars={weekBars} color="#22d3ee" peak={week} />
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            {['M','T','W','T','F','S','S'].map((d, i) => (
              <span key={i} style={{ flex: 1, textAlign: 'center', fontFamily: 'monospace', fontSize: '8px', color: 'rgba(100,116,139,0.3)' }}>{d}</span>
            ))}
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: '1px', background: 'rgba(255,255,255,0.04)' }} />

        {/* Rejection gauge */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0px' }}>
          <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.45)', alignSelf: 'flex-start' }}>
            Rejection Rate
          </span>
          <div style={{ position: 'relative', marginTop: '4px' }}>
            <Gauge pct={rejectionRate} color={rejectionRate > 60 ? '#f87171' : rejectionRate > 30 ? '#fbbf24' : '#34d399'} />
            <div style={{ position: 'absolute', bottom: '0px', left: '50%', transform: 'translateX(-50%)', textAlign: 'center' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '14px', fontWeight: 700, color: 'rgba(226,232,240,0.9)' }}>{rejectionRate}%</span>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '72px' }}>
            <span style={{ fontFamily: 'monospace', fontSize: '8px', color: 'rgba(100,116,139,0.3)' }}>0</span>
            <span style={{ fontFamily: 'monospace', fontSize: '8px', color: 'rgba(100,116,139,0.3)' }}>100</span>
          </div>
        </div>

        {/* Today badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(34,211,238,0.04)', border: '1px solid rgba(34,211,238,0.08)', borderRadius: '8px', padding: '7px 10px' }}>
          <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#22d3ee', boxShadow: '0 0 6px rgba(34,211,238,0.8)', animation: 'pulse-dot 2s ease-in-out infinite', flexShrink: 0 }} />
          <span style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(148,163,184,0.6)' }}>
            <span style={{ color: '#22d3ee', fontWeight: 700 }}>{today}</span> sent today
          </span>
        </div>
      </div>
    </div>
    </>
  )
}
