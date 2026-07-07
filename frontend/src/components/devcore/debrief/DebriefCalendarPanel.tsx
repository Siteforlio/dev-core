import type { CalendarDay, AgendaItem } from '../../../types/debrief'

interface Props {
  monthLabel: string
  calendarDays: CalendarDay[]
  selectedLabel: string
  agenda: AgendaItem[]
  accent: string
  onPrevMonth: () => void
  onNextMonth: () => void
  onSelectEvent?: (event: AgendaItem) => void
  selectedEventUid?: string | null
}

const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

const card: React.CSSProperties = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(34,211,238,0.08)',
  borderRadius: '16px',
  padding: '20px',
}

export default function DebriefCalendarPanel({
  monthLabel,
  calendarDays,
  selectedLabel,
  agenda,
  accent,
  onPrevMonth,
  onNextMonth,
  onSelectEvent,
  selectedEventUid,
}: Props) {
  return (
    <div style={{ flex: '1 1 280px', minWidth: '260px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Calendar card */}
      <div style={card}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '15px', color: '#f1f5f9' }}>
            {monthLabel}
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <NavBtn onClick={onPrevMonth} aria-label="Previous month">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M15 5l-7 7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </NavBtn>
            <NavBtn onClick={onNextMonth} aria-label="Next month">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </NavBtn>
          </div>
        </div>

        {/* Weekday headers */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: '3px', marginBottom: '6px' }}>
          {WEEKDAYS.map((w, i) => (
            <div key={i} style={{ textAlign: 'center', fontSize: '11px', fontWeight: 700, color: 'rgba(148,163,184,0.4)', letterSpacing: '0.04em' }}>
              {w}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: '3px' }}>
          {calendarDays.map((d, i) => {
            let bg     = 'transparent'
            let color  = d.inMonth ? 'rgba(226,232,240,0.8)' : 'rgba(148,163,184,0.2)'
            let border = '1px solid transparent'
            let weight = d.inMonth ? 500 : 400

            if (d.isSelected) {
              bg     = 'rgba(34,211,238,0.15)'
              color  = '#22d3ee'
              border = '1px solid rgba(34,211,238,0.4)'
              weight = 700
            } else if (d.isToday) {
              bg     = 'rgba(34,211,238,0.06)'
              border = '1px solid rgba(34,211,238,0.2)'
              color  = '#22d3ee'
              weight = 700
            }

            return (
              <button
                key={i}
                onClick={d.onClick}
                style={{
                  position: 'relative',
                  height: '34px',
                  border,
                  borderRadius: '8px',
                  background: bg,
                  color,
                  fontWeight: weight,
                  fontSize: '12.5px',
                  cursor: d.inMonth ? 'pointer' : 'default',
                  display: 'grid',
                  placeItems: 'center',
                  fontFamily: "'Manrope', sans-serif",
                  transition: 'background .15s ease',
                  outline: 'none',
                }}
              >
                {d.label}
                {d.hasEvent && (
                  <span style={{
                    position: 'absolute',
                    bottom: '3px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    width: '3px',
                    height: '3px',
                    borderRadius: '50%',
                    background: d.isSelected ? '#22d3ee' : 'rgba(34,211,238,0.5)',
                  }} />
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Agenda card */}
      <div style={{ ...card, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '14px', color: '#f1f5f9' }}>
            Agenda
          </div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'rgba(148,163,184,0.5)', fontFamily: 'monospace' }}>
            {selectedLabel}
          </div>
        </div>

        {agenda.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '320px', overflowY: 'auto', paddingRight: '2px' }}>
            {agenda.map((m, i) => (
              <div
                key={i}
                onClick={() => onSelectEvent?.(m)}
                style={{
                  display: 'flex',
                  gap: '12px',
                  padding: '11px 12px',
                  borderRadius: '12px',
                  background: selectedEventUid && m.uid === selectedEventUid
                    ? 'rgba(34,211,238,0.08)'
                    : 'rgba(255,255,255,0.03)',
                  border: selectedEventUid && m.uid === selectedEventUid
                    ? '1px solid rgba(34,211,238,0.25)'
                    : '1px solid rgba(34,211,238,0.07)',
                  cursor: onSelectEvent ? 'pointer' : 'default',
                  transition: 'background .15s ease, border-color .15s ease',
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', minWidth: '48px' }}>
                  <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '13px', color: '#e2e8f0' }}>
                    {m.time}
                  </div>
                  <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', fontWeight: 600 }}>{m.dur}</div>
                </div>
                <div style={{ width: '2px', borderRadius: '2px', background: m.color, flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '13px', color: '#e2e8f0', lineHeight: 1.3 }}>{m.title}</div>
                  <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', fontWeight: 500, marginTop: '2px' }}>{m.tag}</div>
                </div>
                {m.live && (
                  <span style={{
                    alignSelf: 'flex-start',
                    fontSize: '9px',
                    fontWeight: 800,
                    letterSpacing: '0.08em',
                    color: '#22d3ee',
                    background: 'rgba(34,211,238,0.12)',
                    border: '1px solid rgba(34,211,238,0.25)',
                    padding: '2px 6px',
                    borderRadius: '5px',
                    textTransform: 'uppercase',
                  }}>
                    NOW
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{
            padding: '20px',
            textAlign: 'center',
            color: 'rgba(148,163,184,0.35)',
            fontWeight: 500,
            fontSize: '13px',
            border: '1px dashed rgba(34,211,238,0.1)',
            borderRadius: '10px',
          }}>
            No meetings scheduled
          </div>
        )}
      </div>
    </div>
  )
}

function NavBtn({ onClick, children, 'aria-label': ariaLabel }: {
  onClick: () => void
  children: React.ReactNode
  'aria-label': string
}) {
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel}
      style={{
        width: '28px',
        height: '28px',
        borderRadius: '8px',
        border: '1px solid rgba(34,211,238,0.12)',
        background: 'rgba(34,211,238,0.05)',
        display: 'grid',
        placeItems: 'center',
        cursor: 'pointer',
        color: 'rgba(148,163,184,0.7)',
        outline: 'none',
        transition: 'background .15s ease, color .15s ease',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.12)'; e.currentTarget.style.color = '#22d3ee' }}
      onMouseLeave={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.05)'; e.currentTarget.style.color = 'rgba(148,163,184,0.7)' }}
    >
      {children}
    </button>
  )
}
