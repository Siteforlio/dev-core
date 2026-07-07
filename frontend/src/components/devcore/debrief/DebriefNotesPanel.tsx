import type { DebriefTab, ActionItem, Attendee, Decision } from '../../../types/debrief'

interface Props {
  activeTab: DebriefTab
  onTabChange: (tab: DebriefTab) => void
  notesText: string
  onNotesChange: (text: string) => void
  aiSummary: string | null
  aiConfidence: string | null
  aiHighlights: { label: string; value: string }[]
  actionItems: ActionItem[]
  onToggleAction: (i: number) => void
  decisions: Decision[]
  attendees: Attendee[]
}

const TAB_DEFS: { key: DebriefTab; label: string }[] = [
  { key: 'notes',     label: 'Notes'      },
  { key: 'summary',   label: 'AI Summary' },
  { key: 'actions',   label: 'Actions'    },
  { key: 'decisions', label: 'Decisions'  },
  { key: 'people',    label: 'People'     },
]

const NOTE_TAGS = [
  { label: 'Velocity', bg: 'rgba(34,211,238,0.1)',  fg: '#22d3ee' },
  { label: 'Blockers', bg: 'rgba(251,146,60,0.12)', fg: '#fb923c' },
  { label: 'Handoff',  bg: 'rgba(139,92,246,0.12)', fg: '#a78bfa' },
]

const card: React.CSSProperties = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(34,211,238,0.08)',
  borderRadius: '16px',
  padding: '20px',
}

export default function DebriefNotesPanel({
  activeTab, onTabChange,
  notesText, onNotesChange,
  aiSummary, aiConfidence, aiHighlights,
  actionItems, onToggleAction,
  decisions, attendees,
}: Props) {
  const wordCount = notesText.trim().split(/\s+/).filter(Boolean).length

  return (
    <div style={card}>
      {/* Header + tabs */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '15px', color: '#f1f5f9' }}>
          Debrief Notes
        </div>
        <div style={{
          display: 'flex',
          gap: '3px',
          padding: '3px',
          borderRadius: '10px',
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(34,211,238,0.07)',
          flexWrap: 'wrap',
        }}>
          {TAB_DEFS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => onTabChange(key)}
              style={{
                padding: '6px 12px',
                border: activeTab === key ? '1px solid rgba(34,211,238,0.25)' : '1px solid transparent',
                borderRadius: '7px',
                fontFamily: "'Manrope', sans-serif",
                fontWeight: 700,
                fontSize: '12px',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all .15s ease',
                background: activeTab === key ? 'rgba(34,211,238,0.1)' : 'transparent',
                color: activeTab === key ? '#22d3ee' : 'rgba(148,163,184,0.5)',
                outline: 'none',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Notes tab */}
      {activeTab === 'notes' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', animation: 'dcFade .25s ease both' }}>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {NOTE_TAGS.map(nt => (
              <span key={nt.label} style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '6px',
                background: nt.bg,
                color: nt.fg,
                letterSpacing: '0.02em',
              }}>
                {nt.label}
              </span>
            ))}
          </div>
          <textarea
            value={notesText}
            onChange={e => onNotesChange(e.target.value)}
            placeholder="Capture notes from the session…"
            style={{
              width: '100%',
              minHeight: '180px',
              resize: 'vertical',
              border: '1px solid rgba(34,211,238,0.1)',
              borderRadius: '12px',
              padding: '14px',
              fontSize: '13.5px',
              lineHeight: 1.7,
              color: '#e2e8f0',
              background: 'rgba(255,255,255,0.03)',
              outline: 'none',
              fontFamily: "'Manrope', sans-serif",
            }}
          />
          <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'rgba(148,163,184,0.35)', fontFamily: 'monospace' }}>
            auto-saved · {wordCount} words
          </div>
        </div>
      )}

      {/* AI Summary tab */}
      {activeTab === 'summary' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', animation: 'dcFade .25s ease both' }}>
          {aiSummary ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', fontWeight: 700, color: '#22d3ee' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M12 3l1.9 4.9L19 9.8l-4.1 2.1L13 17l-1-4.9L7 10l4.1-2.1L12 3Z" fill="#22d3ee"/>
                </svg>
                Generated by Dev Core AI · {aiConfidence ?? 'High'} confidence
              </div>
              <div style={{
                height: '2px',
                borderRadius: '2px',
                background: 'linear-gradient(90deg, rgba(34,211,238,0.05) 0%, rgba(34,211,238,0.4) 50%, rgba(34,211,238,0.05) 100%)',
                backgroundSize: '200% 100%',
                animation: 'dcShimmer 2.4s linear infinite',
              }} />
              <p style={{ margin: 0, fontSize: '13.5px', lineHeight: 1.75, color: 'rgba(226,232,240,0.75)' }}>
                {aiSummary}
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(110px,1fr))', gap: '10px' }}>
                {aiHighlights.map(h => (
                  <div key={h.label} style={{
                    padding: '12px 14px',
                    borderRadius: '12px',
                    background: 'rgba(34,211,238,0.06)',
                    border: '1px solid rgba(34,211,238,0.12)',
                  }}>
                    <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'rgba(34,211,238,0.7)', marginBottom: '4px' }}>
                      {h.label}
                    </div>
                    <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '20px', color: '#f1f5f9' }}>
                      {h.value}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : aiConfidence === 'Generating…' ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', padding: '32px 0', color: 'rgba(148,163,184,0.5)' }}>
              <div style={{ width: '24px', height: '24px', border: '2px solid rgba(34,211,238,0.3)', borderTopColor: '#22d3ee', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              <span style={{ fontSize: '13px', fontWeight: 500 }}>Generating AI summary…</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', padding: '32px 0' }}>
              <div style={{ width: '20px', height: '20px', border: '2px solid rgba(34,211,238,0.2)', borderTopColor: '#22d3ee', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              <div style={{ fontSize: '13px', fontWeight: 500, color: 'rgba(148,163,184,0.5)', textAlign: 'center' }}>
                Generating summary…
              </div>
            </div>
          )}
        </div>
      )}

      {/* Actions tab */}
      {activeTab === 'actions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '7px', animation: 'dcFade .25s ease both' }}>
          {actionItems.map((it, i) => (
            <button
              key={i}
              onClick={() => onToggleAction(i)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                textAlign: 'left',
                padding: '12px 14px',
                borderRadius: '12px',
                border: '1px solid rgba(34,211,238,0.07)',
                background: 'rgba(255,255,255,0.02)',
                cursor: 'pointer',
                width: '100%',
                outline: 'none',
                transition: 'background .15s ease',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.04)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
            >
              <span style={{
                flexShrink: 0,
                width: '20px',
                height: '20px',
                borderRadius: '6px',
                display: 'grid',
                placeItems: 'center',
                background: it.done ? 'rgba(34,211,238,0.15)' : 'transparent',
                border: it.done ? '1px solid rgba(34,211,238,0.4)' : '1px solid rgba(148,163,184,0.2)',
                transition: 'all .15s ease',
              }}>
                {it.done && (
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
                    <path d="M5 12l5 5 9-11" stroke="#22d3ee" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </span>
              <span style={{ flex: 1 }}>
                <span style={{
                  display: 'block',
                  fontWeight: 600,
                  fontSize: '13px',
                  color: it.done ? 'rgba(148,163,184,0.35)' : '#e2e8f0',
                  textDecoration: it.done ? 'line-through' : 'none',
                  transition: 'all .15s ease',
                }}>
                  {it.text}
                </span>
                <span style={{ display: 'block', fontSize: '11px', fontWeight: 500, color: 'rgba(148,163,184,0.4)', marginTop: '2px', fontFamily: 'monospace' }}>
                  {it.owner} · {it.due}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Decisions tab */}
      {activeTab === 'decisions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '9px', animation: 'dcFade .25s ease both' }}>
          {decisions.map((dc, i) => (
            <div key={i} style={{
              display: 'flex',
              gap: '12px',
              padding: '13px 14px',
              borderRadius: '12px',
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(34,211,238,0.07)',
            }}>
              <div style={{
                flexShrink: 0,
                width: '24px',
                height: '24px',
                borderRadius: '7px',
                background: 'rgba(34,211,238,0.1)',
                border: '1px solid rgba(34,211,238,0.2)',
                display: 'grid',
                placeItems: 'center',
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                  <path d="M5 12l5 5 9-11" stroke="#22d3ee" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: '13px', color: '#e2e8f0', lineHeight: 1.4 }}>{dc.text}</div>
                <div style={{ fontSize: '11px', fontWeight: 500, color: 'rgba(148,163,184,0.4)', marginTop: '3px', fontFamily: 'monospace' }}>
                  {dc.meta}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* People tab */}
      {activeTab === 'people' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: '9px', animation: 'dcFade .25s ease both' }}>
          {attendees.map((p, i) => (
            <div key={i} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '11px',
              padding: '11px 13px',
              borderRadius: '12px',
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(34,211,238,0.07)',
            }}>
              <div style={{
                flexShrink: 0,
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: p.color,
                color: '#f1f5f9',
                display: 'grid',
                placeItems: 'center',
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 800,
                fontSize: '13px',
              }}>
                {p.initials}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: '13px', color: '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {p.name}
                </div>
                <div style={{ fontSize: '11px', fontWeight: 500, color: 'rgba(148,163,184,0.45)' }}>{p.role}</div>
              </div>
              <span
                title={p.status}
                style={{
                  flexShrink: 0,
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: p.status === 'present' ? '#22d3ee' : 'rgba(148,163,184,0.2)',
                  boxShadow: p.status === 'present' ? '0 0 6px rgba(34,211,238,0.6)' : 'none',
                }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
