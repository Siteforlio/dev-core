import type { MeetingDebrief } from '../../../types/debrief'

interface Stat {
  label: string
  value: string
}

interface Props {
  onOpenEmail: () => void
  stats: Stat[]
  completionPct: number
  doneCount: number
  totalCount: number
  // meeting context
  hasMeeting: boolean           // true when a debrief is loaded (either via calendar or picker)
  meetingTitle: string
  recentDebriefs: MeetingDebrief[]
  recentLoading: boolean
  onSelectDebrief: (d: MeetingDebrief) => void
}

const card: React.CSSProperties = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(34,211,238,0.08)',
  borderRadius: '16px',
  padding: '20px',
}

export default function DebriefFollowUpPanel({
  onOpenEmail, stats, completionPct, doneCount, totalCount,
  hasMeeting, meetingTitle, recentDebriefs, recentLoading, onSelectDebrief,
}: Props) {
  const ringRadius = 35
  const ringCirc   = 2 * Math.PI * ringRadius
  const ringOffset = ringCirc - (ringCirc * completionPct) / 100

  return (
    <div style={{ flex: '1 1 260px', minWidth: '240px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Follow-up card */}
      <div style={card}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '15px', color: '#f1f5f9', marginBottom: '6px' }}>
          Follow-up
        </div>

        {hasMeeting ? (
          /* ── Meeting is in view: show compose button ── */
          <>
            <p style={{ margin: '0 0 4px', fontSize: '11.5px', fontWeight: 600, color: 'rgba(148,163,184,0.45)', fontFamily: 'monospace', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {meetingTitle}
            </p>
            <p style={{ margin: '0 0 16px', fontSize: '12.5px', lineHeight: 1.6, fontWeight: 500, color: 'rgba(148,163,184,0.55)' }}>
              Send the recap and action items to all attendees.
            </p>
            <button
              onClick={onOpenEmail}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '9px',
                padding: '12px',
                border: '1px solid rgba(34,211,238,0.35)',
                borderRadius: '12px',
                background: 'linear-gradient(180deg, rgba(34,211,238,0.14), rgba(34,211,238,0.08))',
                color: '#22d3ee',
                fontWeight: 700,
                fontSize: '13.5px',
                cursor: 'pointer',
                transition: 'all .18s ease',
                outline: 'none',
                fontFamily: "'Manrope', sans-serif",
                letterSpacing: '0.01em',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'linear-gradient(180deg, rgba(34,211,238,0.22), rgba(34,211,238,0.14))'
                e.currentTarget.style.boxShadow = '0 0 20px rgba(34,211,238,0.1)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'linear-gradient(180deg, rgba(34,211,238,0.14), rgba(34,211,238,0.08))'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="5" width="18" height="14" rx="3" stroke="currentColor" strokeWidth="1.8"/>
                <path d="m4 7 8 6 8-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Compose follow-up
            </button>

            <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
              <SecondaryBtn icon={
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              }>Export</SecondaryBtn>
              <SecondaryBtn icon={
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              }>Share</SecondaryBtn>
            </div>
          </>
        ) : (
          /* ── No meeting in view: show meeting picker ── */
          <>
            <p style={{ margin: '0 0 12px', fontSize: '12.5px', lineHeight: 1.6, fontWeight: 500, color: 'rgba(148,163,184,0.55)' }}>
              Select a meeting to compose a follow-up email.
            </p>

            {recentLoading ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0', gap: '8px', color: 'rgba(148,163,184,0.4)', fontSize: '12px' }}>
                <div style={{ width: '14px', height: '14px', border: '2px solid rgba(34,211,238,0.2)', borderTopColor: '#22d3ee', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                Loading meetings…
              </div>
            ) : recentDebriefs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '16px 0', fontSize: '12px', fontWeight: 500, color: 'rgba(148,163,184,0.35)' }}>
                No meetings found yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', maxHeight: '220px', overflowY: 'auto' }}>
                {recentDebriefs.map(d => (
                  <button
                    key={d.id}
                    onClick={() => onSelectDebrief(d)}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      gap: '2px',
                      padding: '9px 11px',
                      borderRadius: '10px',
                      border: '1px solid rgba(34,211,238,0.07)',
                      background: 'rgba(255,255,255,0.02)',
                      cursor: 'pointer',
                      width: '100%',
                      textAlign: 'left',
                      outline: 'none',
                      transition: 'background .15s ease',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.06)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                  >
                    <span style={{ fontSize: '12.5px', fontWeight: 600, color: '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }}>
                      {d.title}
                    </span>
                    <span style={{ fontSize: '10.5px', fontWeight: 500, color: 'rgba(148,163,184,0.4)', fontFamily: 'monospace' }}>
                      {d.date ?? '—'}{d.start_time ? ` · ${d.start_time}` : ''}{(d.attendees?.length ?? 0) > 0 ? ` · ${d.attendees.length} attendee${d.attendees.length > 1 ? 's' : ''}` : ''}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Session Summary card */}
      <div style={card}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '15px', color: '#f1f5f9', marginBottom: '16px' }}>
          Session Summary
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
          {/* Ring */}
          <div style={{ position: 'relative', width: '80px', height: '80px', flexShrink: 0 }}>
            <svg width="80" height="80" viewBox="0 0 84 84">
              <circle cx="42" cy="42" r={ringRadius} fill="none" stroke="rgba(34,211,238,0.08)" strokeWidth="8"/>
              <circle
                cx="42" cy="42" r={ringRadius}
                fill="none"
                stroke="#22d3ee"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${ringCirc}`}
                strokeDashoffset={ringOffset}
                transform="rotate(-90 42 42)"
                style={{ transition: 'stroke-dashoffset 1s ease', filter: 'drop-shadow(0 0 6px rgba(34,211,238,0.4))' }}
              />
            </svg>
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'grid',
              placeItems: 'center',
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700,
              fontSize: '17px',
              color: '#22d3ee',
            }}>
              {completionPct}%
            </div>
          </div>

          {/* Stats list */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '9px' }}>
            {stats.map(s => (
              <div key={s.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: 500, color: 'rgba(148,163,184,0.5)' }}>{s.label}</span>
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '14px', color: '#e2e8f0' }}>
                  {s.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function SecondaryBtn({ children, icon }: { children: React.ReactNode; icon: React.ReactNode }) {
  return (
    <button
      style={{
        flex: 1,
        padding: '10px',
        borderRadius: '10px',
        border: '1px solid rgba(34,211,238,0.1)',
        background: 'rgba(255,255,255,0.02)',
        fontWeight: 600,
        fontSize: '12px',
        cursor: 'pointer',
        color: 'rgba(148,163,184,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '6px',
        outline: 'none',
        fontFamily: "'Manrope', sans-serif",
        transition: 'all .15s ease',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'rgba(34,211,238,0.06)'
        e.currentTarget.style.color = '#22d3ee'
        e.currentTarget.style.borderColor = 'rgba(34,211,238,0.2)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.02)'
        e.currentTarget.style.color = 'rgba(148,163,184,0.6)'
        e.currentTarget.style.borderColor = 'rgba(34,211,238,0.1)'
      }}
    >
      {icon}
      {children}
    </button>
  )
}
