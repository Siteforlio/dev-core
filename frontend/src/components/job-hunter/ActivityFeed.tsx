import { useEffect, useRef, useState } from 'react'
import type { ActivityMessage } from '../../hooks/useCampaignActivity'
import type { BoardStatus, ScrapePreferences, ScrapeRunStatus } from '../../types/jobHunter'

interface Props {
  feed: ActivityMessage[]
  onTriggerScrape?: () => void
  onStopScrape?: () => void
  onClear?: () => void
  scraping?: boolean
  scrapeError?: string
  prefs?: ScrapePreferences
  onPrefsChange?: (p: ScrapePreferences) => void
  boardStatuses?: Record<string, BoardStatus>
  runStatus?: ScrapeRunStatus | null
}

const COMPANY_TYPE_OPTS = [
  { id: 'faang',      label: 'FAANG' },
  { id: 'enterprise', label: 'Enterprise' },
  { id: 'startup',    label: 'Startup' },
  { id: 'sme',        label: 'SME' },
] as const

const WORK_TYPE_OPTS = [
  { id: 'any',    label: 'Any' },
  { id: 'remote', label: 'Remote' },
  { id: 'hybrid', label: 'Hybrid' },
  { id: 'onsite', label: 'Onsite' },
] as const

const REGION_OPTS = [
  { id: 'global', label: 'Global' },
  { id: 'africa', label: 'Africa' },
  { id: 'kenya',  label: 'Kenya' },
] as const

const BOARD_DISPLAY: Record<string, string> = {
  // JobSpy aggregators
  indeed: 'Indeed', glassdoor: 'Glassdoor', zip_recruiter: 'ZipRecruiter', google: 'Google',
  // ATS
  greenhouse: 'Greenhouse', lever: 'Lever', ashby: 'Ashby',
  // Startup / remote
  wellfound: 'Wellfound', remotive: 'Remotive', remoteok: 'RemoteOK',
  hn_hiring: 'HN Hiring', weworkremotely: 'WWR',
  // Africa
  zindi: 'Zindi', startupdeals_africa: 'SD Africa',
  myjobmag: 'MyJobMag', kuhustle: 'Kuhustle',
  // Browser-automation (stashed)
  fuzu: 'Fuzu', brightermonday: 'BrighterMonday', andela: 'Andela', arc: 'Arc.dev',
  // Global — new boards
  the_muse: 'The Muse', jobicy: 'Jobicy', himalayas: 'Himalayas',
  getonboard: 'GetOnBoard', adzuna: 'Adzuna', reed: 'Reed',
  // Social
  linkedin: 'LinkedIn',
}

/* ── Parse a raw feed message into structured parts ── */
type MsgType = 'match' | 'partial' | 'skip' | 'success' | 'error' | 'warn' | 'info'

function parseMsg(text: string): { type: MsgType; role?: string; company?: string; raw: string } {
  const lower = text.toLowerCase()

  // Job scoring messages have explicit "MATCH —" or "PARTIAL —" pattern with role @ company
  const dashMatch = text.match(/(?:MATCH|PARTIAL|SKIP)\s*[—-]\s*(.+?)\s*@\s*(.+)$/i)
  if (dashMatch) {
    const word = dashMatch[0].split(/\s/)[0].toUpperCase()
    const type: MsgType = word === 'MATCH' ? 'match' : word === 'PARTIAL' ? 'partial' : 'skip'
    return { type, role: dashMatch[1].trim(), company: dashMatch[2].trim(), raw: text }
  }

  let type: MsgType = 'info'
  if (text.startsWith('❌') || lower.includes('error') || lower.includes('failed')) type = 'error'
  else if (text.startsWith('⚠️') || lower.includes('warn')) type = 'warn'
  else if (lower.includes('done') || lower.includes('complete') || lower.includes('saved') || lower.includes('found')) type = 'success'
  else if (text.startsWith('✅') || text.startsWith('💾') || text.startsWith('🏁')) type = 'success'

  return { type, raw: text }
}

const TYPE_CONFIG: Record<MsgType, { bar: string; badge: string; badgeBg: string; label: string }> = {
  match:   { bar: '#22d3ee', badge: '#22d3ee', badgeBg: 'rgba(34,211,238,0.12)',  label: 'MATCH'   },
  partial: { bar: '#fbbf24', badge: '#fbbf24', badgeBg: 'rgba(251,191,36,0.12)',  label: 'PARTIAL' },
  skip:    { bar: '#6b7280', badge: '#6b7280', badgeBg: 'rgba(107,114,128,0.1)',  label: 'SKIP'    },
  success: { bar: '#34d399', badge: '#34d399', badgeBg: 'rgba(52,211,153,0.12)',  label: 'OK'      },
  error:   { bar: '#f87171', badge: '#f87171', badgeBg: 'rgba(248,113,113,0.12)', label: 'ERR'     },
  warn:    { bar: '#fb923c', badge: '#fb923c', badgeBg: 'rgba(251,146,60,0.12)',  label: 'WARN'    },
  info:    { bar: 'rgba(34,211,238,0.2)', badge: 'rgba(148,163,184,0.5)', badgeBg: 'rgba(148,163,184,0.06)', label: 'LOG' },
}

function ToggleChip({
  label, active, onClick,
}: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 10px',
        borderRadius: '6px',
        border: `1px solid ${active ? 'rgba(34,211,238,0.4)' : 'rgba(255,255,255,0.07)'}`,
        background: active ? 'rgba(34,211,238,0.1)' : 'transparent',
        color: active ? '#22d3ee' : 'rgba(100,116,139,0.6)',
        fontFamily: 'monospace',
        fontSize: '10px',
        fontWeight: 700,
        letterSpacing: '0.1em',
        cursor: 'pointer',
        transition: 'all 0.15s',
      }}
    >
      {label}
    </button>
  )
}

export default function ActivityFeed({
  feed, onTriggerScrape, onStopScrape, onClear, scraping,
  scrapeError, prefs, onPrefsChange, boardStatuses = {}, runStatus,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [showPrefs, setShowPrefs] = useState(false)

  const activeBoardIds = Object.keys(boardStatuses)
  const hasStatus = activeBoardIds.length > 0

  // Only count actual job-match messages (have "MATCH —" pattern with role @ company)
  const matchCount   = feed.filter(m => /MATCH\s*[—-]\s*.+@/i.test(m.text)).length
  const partialCount = feed.filter(m => /PARTIAL\s*[—-]\s*.+@/i.test(m.text)).length

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    // Only auto-scroll if user is within 120px of the bottom
    if (distFromBottom < 120) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [feed])

  function toggleCompanyType(id: string) {
    if (!prefs || !onPrefsChange) return
    const ct = prefs.companyTypes as string[]
    onPrefsChange({
      ...prefs,
      companyTypes: ct.includes(id)
        ? ct.filter(x => x !== id)
        : [...ct, id] as ScrapePreferences['companyTypes'],
    })
  }

  function toggleRegion(id: string) {
    if (!prefs || !onPrefsChange) return
    const rs = prefs.regions as string[]
    onPrefsChange({
      ...prefs,
      regions: rs.includes(id)
        ? rs.filter(x => x !== id)
        : [...rs, id] as ScrapePreferences['regions'],
    })
  }

  return (
    <>
    <style>{`
      .af-scroll::-webkit-scrollbar { display: none; }
      .af-scroll { scrollbar-width: none; }
      .af-feed-row { transition: background 0.1s; }
      .af-feed-row:hover { background: rgba(255,255,255,0.025) !important; }
      @keyframes af-spin { to { transform: rotate(360deg); } }
      @keyframes af-rec { 0%,100%{opacity:1} 50%{opacity:0.2} }
    `}</style>

    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, gap: 0 }}>

      {/* ── Header ── */}
      <div style={{ padding: '14px 16px 10px', flexShrink: 0, borderBottom: '1px solid rgba(34,211,238,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Recording dot */}
            <div style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: scraping ? '#f87171' : 'rgba(34,211,238,0.5)',
              boxShadow: scraping ? '0 0 8px #f87171' : '0 0 6px rgba(34,211,238,0.5)',
              animation: scraping ? 'af-rec 1s step-end infinite' : 'pulse-dot 3s ease-in-out infinite',
              flexShrink: 0,
            }} />
            <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.22em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.55)' }}>
              Live Feed
            </span>
            {feed.length > 0 && (
              <span style={{ fontFamily: 'monospace', fontSize: '9px', background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.15)', color: 'rgba(34,211,238,0.6)', padding: '1px 6px', borderRadius: '10px' }}>
                {feed.length}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {onClear && feed.length > 0 && (
              <button
                onClick={onClear}
                style={{ background: 'transparent', border: 'none', color: 'rgba(100,116,139,0.4)', fontFamily: 'monospace', fontSize: '10px', cursor: 'pointer', padding: '4px 6px', borderRadius: '4px', transition: 'color 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'rgba(226,232,240,0.6)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.4)')}
              >
                Clear
              </button>
            )}
            {onPrefsChange && (
              <button
                onClick={() => setShowPrefs(v => !v)}
                style={{
                  background: showPrefs ? 'rgba(34,211,238,0.1)' : 'transparent',
                  border: `1px solid ${showPrefs ? 'rgba(34,211,238,0.25)' : 'rgba(255,255,255,0.07)'}`,
                  color: showPrefs ? '#22d3ee' : 'rgba(100,116,139,0.5)',
                  borderRadius: '6px', padding: '4px 7px', cursor: 'pointer', transition: 'all 0.15s', display: 'flex', alignItems: 'center',
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                </svg>
              </button>
            )}
            {scraping && onStopScrape ? (
              <button
                onClick={onStopScrape}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  background: 'rgba(248,113,113,0.1)',
                  border: '1px solid rgba(248,113,113,0.35)',
                  color: '#f87171',
                  fontFamily: 'monospace', fontSize: '10px', fontWeight: 700,
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                  padding: '5px 12px', borderRadius: '7px',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(248,113,113,0.18)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(248,113,113,0.1)' }}
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
                Stop
              </button>
            ) : onTriggerScrape ? (
              <button
                onClick={onTriggerScrape}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  background: 'rgba(34,211,238,0.1)',
                  border: '1px solid rgba(34,211,238,0.35)',
                  color: '#22d3ee',
                  fontFamily: 'monospace', fontSize: '10px', fontWeight: 700,
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                  padding: '5px 12px', borderRadius: '7px',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  boxShadow: '0 0 12px rgba(34,211,238,0.1)',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.18)'; e.currentTarget.style.boxShadow = '0 0 18px rgba(34,211,238,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.1)'; e.currentTarget.style.boxShadow = '0 0 12px rgba(34,211,238,0.1)' }}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                Run Scrape
              </button>
            ) : null}
          </div>
        </div>

        {/* Mini stats row */}
        {feed.length > 0 && (
          <div style={{ display: 'flex', gap: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.1)', borderRadius: '5px', padding: '3px 8px' }}>
              <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#22d3ee' }} />
              <span style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(34,211,238,0.7)', fontWeight: 700 }}>{matchCount} match</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.1)', borderRadius: '5px', padding: '3px 8px' }}>
              <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#fbbf24' }} />
              <span style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(251,191,36,0.7)', fontWeight: 700 }}>{partialCount} partial</span>
            </div>
          </div>
        )}
      </div>

      {/* ── Preferences panel ── */}
      {showPrefs && prefs && onPrefsChange && (
        <div style={{ flexShrink: 0, padding: '12px 16px', borderBottom: '1px solid rgba(34,211,238,0.06)', display: 'flex', flexDirection: 'column', gap: '14px', background: 'rgba(34,211,238,0.02)' }}>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)' }}>Company Type</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
              {COMPANY_TYPE_OPTS.map(({ id, label }) => (
                <ToggleChip key={id} label={label} active={(prefs.companyTypes as string[]).includes(id)} onClick={() => toggleCompanyType(id)} />
              ))}
              {prefs.companyTypes.length > 0 && (
                <button onClick={() => onPrefsChange({ ...prefs, companyTypes: [] })} style={{ background: 'none', border: 'none', color: 'rgba(100,116,139,0.4)', fontFamily: 'monospace', fontSize: '10px', cursor: 'pointer' }}>clear</button>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)' }}>Work Type</span>
            <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
              {WORK_TYPE_OPTS.map(({ id, label }) => (
                <ToggleChip key={id} label={label} active={prefs.workType === id} onClick={() => onPrefsChange({ ...prefs, workType: id })} />
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)' }}>Region</span>
            <div style={{ display: 'flex', gap: '5px' }}>
              {REGION_OPTS.map(({ id, label }) => (
                <ToggleChip key={id} label={label} active={(prefs.regions as string[]).includes(id)} onClick={() => toggleRegion(id)} />
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)' }}>Daily Target</span>
              <span style={{ fontFamily: 'monospace', fontSize: '12px', fontWeight: 700, color: '#22d3ee' }}>{prefs.dailyTarget}</span>
            </div>
            <div style={{ position: 'relative', height: '3px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px' }}>
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${((prefs.dailyTarget - 10) / 90) * 100}%`, background: 'linear-gradient(90deg, rgba(34,211,238,0.5), #22d3ee)', borderRadius: '2px', boxShadow: '0 0 6px rgba(34,211,238,0.4)' }} />
            </div>
            <input
              type="range" min={10} max={100} step={10}
              value={prefs.dailyTarget}
              onChange={e => onPrefsChange({ ...prefs, dailyTarget: Number(e.target.value) })}
              style={{ width: '100%', opacity: 0, position: 'absolute', height: '20px', cursor: 'pointer', marginTop: '-14px' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '8px', color: 'rgba(100,116,139,0.3)' }}>10</span>
              <span style={{ fontFamily: 'monospace', fontSize: '8px', color: 'rgba(100,116,139,0.3)' }}>100</span>
            </div>
            {/* Actual range input overlaid */}
            <input
              type="range" min={10} max={100} step={10}
              value={prefs.dailyTarget}
              onChange={e => onPrefsChange({ ...prefs, dailyTarget: Number(e.target.value) })}
              style={{ width: '100%', accentColor: '#22d3ee', height: '2px', cursor: 'pointer', marginTop: '-8px' }}
            />
          </div>
        </div>
      )}

      {/* ── Board status grid ── */}
      {hasStatus && (
        <div style={{ flexShrink: 0, padding: '10px 16px', borderBottom: '1px solid rgba(34,211,238,0.06)' }}>
          {runStatus && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.45)' }}>
                Round {runStatus.round}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, color: '#34d399' }}>{matchCount || runStatus.matches}</span>
                <span style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(100,116,139,0.5)' }}>matches</span>
                {runStatus.status === 'running' && (
                  <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#22d3ee', animation: 'pulse-dot 1s ease-in-out infinite' }} />
                )}
              </div>
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
            {activeBoardIds.map(boardId => {
              const bs = boardStatuses[boardId]
              const colors: Record<BoardStatus['status'], string> = {
                idle:    'rgba(107,114,128,0.5)',
                queued:  '#fbbf24',
                running: '#22d3ee',
                done:    '#34d399',
                failed:  '#f87171',
              }
              const c = colors[bs.status]
              return (
                <div key={boardId} style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.05)',
                  borderRadius: '6px', padding: '5px 8px',
                  borderLeft: `2px solid ${c}`,
                }} title={bs.error ?? undefined}>
                  {bs.status === 'running' && (
                    <div style={{ width: '8px', height: '8px', border: `1.5px solid rgba(34,211,238,0.3)`, borderTopColor: '#22d3ee', borderRadius: '50%', animation: 'af-spin 0.7s linear infinite', flexShrink: 0 }} />
                  )}
                  {bs.status !== 'running' && (
                    <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: c, flexShrink: 0, boxShadow: `0 0 5px ${c}80` }} />
                  )}
                  <span style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(148,163,184,0.7)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {BOARD_DISPLAY[boardId] ?? boardId}
                  </span>
                  {bs.status === 'done' && bs.count != null && (
                    <span style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, color: '#34d399', flexShrink: 0 }}>{bs.count}</span>
                  )}
                  {bs.status === 'failed' && (
                    <span
                      style={{ fontFamily: 'monospace', fontSize: '9px', color: '#f87171', flexShrink: 0, maxWidth: '60px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={bs.error ?? 'Failed'}
                    >
                      {bs.error?.includes('API key') ? 'no key' : '!'}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {scrapeError && (
        <div style={{ flexShrink: 0, margin: '0 16px', borderRadius: '7px', padding: '8px 12px', background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.2)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span style={{ fontFamily: 'monospace', fontSize: '10px', color: '#f87171' }}>{scrapeError}</span>
        </div>
      )}

      {/* ── Feed log ── */}
      <div ref={scrollRef} className="af-scroll" style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {feed.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '12px', padding: '40px 20px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '50%', border: '1px solid rgba(34,211,238,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.3)" strokeWidth="1.5" strokeLinecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </div>
            <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.4)', textAlign: 'center', lineHeight: 1.7, letterSpacing: '0.04em' }}>
              {scraping ? 'Scanning job boards…' : 'No activity yet.\nRun Scrape to start scanning.'}
            </p>
          </div>
        ) : (
          <div>
            {feed.map((msg) => {
              const { type, role, company } = parseMsg(msg.text)
              const cfg = TYPE_CONFIG[type]
              const time = msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

              return (
                <div
                  key={msg.id}
                  className="af-feed-row"
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0',
                    padding: '6px 16px 6px 0',
                    borderBottom: '1px solid rgba(255,255,255,0.025)',
                    cursor: 'default',
                    position: 'relative',
                  }}
                >
                  {/* Left accent bar */}
                  <div style={{ width: '2px', flexShrink: 0, alignSelf: 'stretch', background: cfg.bar, marginRight: '10px', opacity: 0.6 }} />

                  {/* Time */}
                  <span style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(100,116,139,0.35)', flexShrink: 0, marginTop: '2px', minWidth: '52px', letterSpacing: '0.03em' }}>
                    {time}
                  </span>

                  {/* Badge */}
                  <span style={{
                    flexShrink: 0,
                    fontFamily: 'monospace', fontSize: '8px', fontWeight: 700, letterSpacing: '0.1em',
                    color: cfg.badge,
                    background: cfg.badgeBg,
                    border: `1px solid ${cfg.badge}30`,
                    borderRadius: '4px',
                    padding: '1px 5px',
                    marginRight: '7px',
                    marginTop: '1px',
                    lineHeight: '14px',
                  }}>
                    {cfg.label}
                  </span>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {role && company ? (
                      <>
                        <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(226,232,240,0.75)', lineHeight: 1.4, wordBreak: 'break-word' }}>{role}</p>
                        <p style={{ fontFamily: 'monospace', fontSize: '9px', color: cfg.badge, opacity: 0.7, marginTop: '1px' }}>@ {company}</p>
                      </>
                    ) : (
                      <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(148,163,184,0.55)', lineHeight: 1.5, wordBreak: 'break-word' }}>
                        {msg.text.replace(/^[🟡✅❌⚠️]\s*/, '')}
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
    </div>
    </>
  )
}
