import { useState, useRef, useEffect } from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import type { ToolEvent } from '../../types/devcore'

// ── Types ─────────────────────────────────────────────────────────────────────
type ToolName = 'terminal' | 'screen' | 'browser' | 'file' | 'search'

interface ToolMeta {
  name: ToolName
  label: string
  icon: React.ReactNode
}

// ── SVG Icons ─────────────────────────────────────────────────────────────────
const IconTerminal = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <polyline points="3,6 7,9 3,12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <line x1="9" y1="12" x2="15" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

const IconScreen = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <rect x="2" y="3" width="14" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
    <line x1="6" y1="15" x2="12" y2="15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <line x1="9" y1="13" x2="9" y2="15" stroke="currentColor" strokeWidth="1.5"/>
  </svg>
)

const IconBrowser = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <circle cx="9" cy="9" r="6.5" stroke="currentColor" strokeWidth="1.5"/>
    <ellipse cx="9" cy="9" rx="3" ry="6.5" stroke="currentColor" strokeWidth="1.5"/>
    <line x1="2.5" y1="6.5" x2="15.5" y2="6.5" stroke="currentColor" strokeWidth="1.5"/>
    <line x1="2.5" y1="11.5" x2="15.5" y2="11.5" stroke="currentColor" strokeWidth="1.5"/>
  </svg>
)

const IconFile = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <path d="M4 2h7l3 3v11H4V2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    <polyline points="11,2 11,5 14,5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    <line x1="7" y1="9" x2="11" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <line x1="7" y1="12" x2="11" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

const IconSearch = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5"/>
    <line x1="12" y1="12" x2="15.5" y2="15.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

// ── Tool Registry ──────────────────────────────────────────────────────────────
const TOOLS: ToolMeta[] = [
  { name: 'terminal', label: 'TERM', icon: <IconTerminal /> },
  { name: 'screen',   label: 'VIEW', icon: <IconScreen />   },
  { name: 'browser',  label: 'WEB',  icon: <IconBrowser />  },
  { name: 'file',     label: 'FILE', icon: <IconFile />     },
  { name: 'search',   label: 'SRCH', icon: <IconSearch />   },
]

// ── Helpers ────────────────────────────────────────────────────────────────────
function eventsFor(events: ToolEvent[], tool: ToolName): ToolEvent[] {
  return events.filter(e => e.tool === tool)
}

function lastEvent(events: ToolEvent[], tool: ToolName): ToolEvent | null {
  const filtered = eventsFor(events, tool)
  return filtered.length > 0 ? filtered[filtered.length - 1] : null
}

// ── Card Components ────────────────────────────────────────────────────────────

function TerminalCard({ events }: { events: ToolEvent[] }) {
  const logRef = useRef<HTMLDivElement>(null)
  const termEvents = eventsFor(events, 'terminal')

  const lines: { stream: string; text: string; ts: number }[] = []
  let cwd = ''
  let cmd = ''

  for (const ev of termEvents) {
    if (ev.data.cwd) cwd = ev.data.cwd as string
    if (ev.data.command) cmd = (ev.data.command as string[]).join(' ')
    if (ev.data.text) {
      lines.push({
        stream: ev.data.stream as string ?? 'stdout',
        text: ev.data.text as string,
        ts: ev.ts,
      })
    }
  }

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [termEvents.length])

  return (
    <div className="tool-card-inner">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06]">
        <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_theme(colors.amber.400)]" />
        <span className="font-mono text-[10px] tracking-widest text-white/40 uppercase flex-1">terminal</span>
        {cwd && <span className="font-mono text-[9px] text-white/25 truncate max-w-[160px]">{cwd}</span>}
      </div>

      {/* Command banner */}
      {cmd && (
        <div className="px-3 py-1.5 bg-amber-400/[0.06] border-b border-amber-400/[0.12]">
          <span className="font-mono text-[10px] text-amber-300/70">$ {cmd}</span>
        </div>
      )}

      {/* Log output */}
      <div
        ref={logRef}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5 terminal-scanlines"
        style={{ maxHeight: '280px' }}
      >
        {lines.length === 0 ? (
          <div className="font-mono text-[10px] text-white/20 italic">awaiting output…</div>
        ) : (
          lines.map((l, i) => (
            <div
              key={i}
              className={`font-mono text-[10px] leading-relaxed whitespace-pre-wrap break-all ${
                l.stream === 'stderr' ? 'text-red-400/80' : 'text-emerald-300/70'
              }`}
            >
              {l.text}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function ScreenCard({ events }: { events: ToolEvent[] }) {
  const last = lastEvent(events, 'screen')
  const b64 = last?.data.image as string | undefined
  const text = last?.data.text as string | undefined

  return (
    <div className="tool-card-inner">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06]">
        <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_theme(colors.amber.400)]" />
        <span className="font-mono text-[10px] tracking-widest text-white/40 uppercase">screen view</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2" style={{ maxHeight: '320px' }}>
        {b64 ? (
          <img
            src={`data:image/png;base64,${b64}`}
            alt="Screen capture"
            className="w-full rounded border border-white/[0.08] object-cover"
          />
        ) : (
          <div className="flex items-center justify-center h-28 border border-dashed border-white/[0.1] rounded text-white/20 font-mono text-[10px] tracking-widest">
            WAITING FOR CAPTURE
          </div>
        )}
        {text && (
          <div className="font-mono text-[10px] text-white/50 leading-relaxed whitespace-pre-wrap break-words">
            {text.slice(0, 400)}{text.length > 400 ? '…' : ''}
          </div>
        )}
      </div>
    </div>
  )
}

function BrowserCard({ events }: { events: ToolEvent[] }) {
  const last = lastEvent(events, 'browser')
  const url = last?.data.url as string | undefined
  const content = last?.data.text as string | undefined
  const problem = last?.data.problem_text as string | undefined

  return (
    <div className="tool-card-inner">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06]">
        <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_theme(colors.amber.400)]" />
        <span className="font-mono text-[10px] tracking-widest text-white/40 uppercase">browser</span>
      </div>

      {url && (
        <div className="px-3 py-1.5 bg-white/[0.03] border-b border-white/[0.06]">
          <span className="font-mono text-[9px] text-violet-300/60 truncate block">{url}</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3" style={{ maxHeight: '300px' }}>
        {!url && !content ? (
          <div className="font-mono text-[10px] text-white/20 italic">no page loaded</div>
        ) : (
          <div className="font-mono text-[10px] text-white/55 leading-relaxed whitespace-pre-wrap break-words">
            {(problem ?? content ?? '').slice(0, 600)}
            {((problem ?? content ?? '').length > 600) ? '…' : ''}
          </div>
        )}
      </div>
    </div>
  )
}

function FileCard({ events }: { events: ToolEvent[] }) {
  const fileEvents = eventsFor(events, 'file')
  const last = fileEvents[fileEvents.length - 1] ?? null

  const filePath = last?.data.path as string | undefined
  const content  = last?.data.content as string | undefined
  const listing  = last?.data.listing as string | undefined
  const diff     = last?.data.diff as string | undefined

  return (
    <div className="tool-card-inner">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06]">
        <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_theme(colors.amber.400)]" />
        <span className="font-mono text-[10px] tracking-widest text-white/40 uppercase">file</span>
      </div>

      {filePath && (
        <div className="px-3 py-1.5 bg-white/[0.03] border-b border-white/[0.06]">
          <span className="font-mono text-[9px] text-amber-300/50 truncate block">{filePath}</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3" style={{ maxHeight: '300px' }}>
        {!last ? (
          <div className="font-mono text-[10px] text-white/20 italic">no file events yet</div>
        ) : diff ? (
          <pre className="font-mono text-[10px] leading-relaxed text-white/60 whitespace-pre-wrap break-all">
            {diff.split('\n').map((line, i) => (
              <span
                key={i}
                className={
                  line.startsWith('+') ? 'text-emerald-400/80 block' :
                  line.startsWith('-') ? 'text-red-400/70 block' :
                  'block'
                }
              >
                {line}
              </span>
            ))}
          </pre>
        ) : (
          <div className="font-mono text-[10px] text-white/55 leading-relaxed whitespace-pre-wrap break-words">
            {(listing ?? content ?? '').slice(0, 600)}
          </div>
        )}
      </div>
    </div>
  )
}

function SearchCard({ events }: { events: ToolEvent[] }) {
  const searchEvents = eventsFor(events, 'search')
  const last = searchEvents[searchEvents.length - 1] ?? null
  const query   = last?.data.query as string | undefined
  const results = last?.data.results as { title: string; snippet: string; url?: string }[] | undefined

  return (
    <div className="tool-card-inner">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06]">
        <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_theme(colors.amber.400)]" />
        <span className="font-mono text-[10px] tracking-widest text-white/40 uppercase">search</span>
      </div>

      {query && (
        <div className="px-3 py-1.5 bg-white/[0.03] border-b border-white/[0.06]">
          <span className="font-mono text-[9px] text-violet-300/60">&ldquo;{query}&rdquo;</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3 space-y-3" style={{ maxHeight: '300px' }}>
        {!last ? (
          <div className="font-mono text-[10px] text-white/20 italic">no searches yet</div>
        ) : results && results.length > 0 ? (
          results.slice(0, 3).map((r, i) => (
            <div key={i} className="border-l-2 border-amber-400/30 pl-2 space-y-0.5">
              <div className="font-mono text-[10px] text-amber-300/70 font-semibold leading-tight">{r.title}</div>
              {r.url && <div className="font-mono text-[8px] text-violet-300/40 truncate">{r.url}</div>}
              <div className="font-mono text-[10px] text-white/45 leading-relaxed">{r.snippet?.slice(0, 180)}</div>
            </div>
          ))
        ) : (
          <div className="font-mono text-[10px] text-white/20 italic">no results</div>
        )}
      </div>
    </div>
  )
}

// ── Card dispatcher ────────────────────────────────────────────────────────────
function ToolCardContent({ tool, events }: { tool: ToolName; events: ToolEvent[] }) {
  switch (tool) {
    case 'terminal': return <TerminalCard events={events} />
    case 'screen':   return <ScreenCard events={events} />
    case 'browser':  return <BrowserCard events={events} />
    case 'file':     return <FileCard events={events} />
    case 'search':   return <SearchCard events={events} />
  }
}

// ── Main ToolDock ──────────────────────────────────────────────────────────────
export function ToolDock() {
  const { assessmentMode, toolEvents, activeTool } = useOverlayStore()
  const [openTool, setOpenTool] = useState<ToolName | null>(null)

  // Only render in assessment mode
  if (!assessmentMode) return null

  const handleIconClick = (name: ToolName) => {
    setOpenTool(prev => prev === name ? null : name)
  }

  return (
    <>
      {/* Inject keyframes + utility styles */}
      <style>{`
        @keyframes dock-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(251,191,36,0); }
          50%       { box-shadow: 0 0 0 4px rgba(251,191,36,0.25); }
        }
        @keyframes card-slide-in {
          from { opacity: 0; transform: translateX(12px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        .dock-icon-active {
          animation: dock-pulse 1.6s ease-in-out infinite;
        }
        .tool-card-enter {
          animation: card-slide-in 0.18s cubic-bezier(0.16,1,0.3,1) forwards;
        }
        .tool-card-inner {
          display: flex;
          flex-direction: column;
          height: 100%;
        }
        .terminal-scanlines {
          background-image: repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(0,0,0,0.08) 2px,
            rgba(0,0,0,0.08) 4px
          );
        }
        /* Thin scrollbar */
        .tool-card-inner ::-webkit-scrollbar { width: 3px; }
        .tool-card-inner ::-webkit-scrollbar-track { background: transparent; }
        .tool-card-inner ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }
      `}</style>

      {/* Outer wrapper — fixed right edge, vertically centered */}
      <div
        className="fixed right-0 top-1/2 -translate-y-1/2 flex items-center z-50"
        style={{ pointerEvents: 'none' }}
      >
        {/* Expanded card panel */}
        {openTool && (
          <div
            className="tool-card-enter mr-1 overflow-hidden rounded-lg"
            style={{
              width: '360px',
              maxHeight: '420px',
              background: 'rgba(9,9,18,0.97)',
              border: '1px solid rgba(255,255,255,0.07)',
              backdropFilter: 'blur(24px)',
              boxShadow: '0 0 0 1px rgba(251,191,36,0.08), 0 24px 48px rgba(0,0,0,0.6)',
              pointerEvents: 'all',
            }}
          >
            {/* Card header row with close */}
            <div className="flex items-center justify-between px-3 pt-2.5 pb-1">
              <span className="font-mono text-[9px] tracking-[0.2em] text-amber-400/60 uppercase">
                {TOOLS.find(t => t.name === openTool)?.label}
              </span>
              <button
                onClick={() => setOpenTool(null)}
                className="font-mono text-[10px] text-white/25 hover:text-white/60 transition-colors leading-none px-1"
                style={{ pointerEvents: 'all' }}
              >
                ✕
              </button>
            </div>

            {/* Tool-specific content */}
            <div style={{ maxHeight: '380px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <ToolCardContent tool={openTool} events={toolEvents} />
            </div>
          </div>
        )}

        {/* Dock strip */}
        <div
          className="flex flex-col items-center py-3 gap-1 rounded-l-xl"
          style={{
            width: '48px',
            background: 'rgba(9,9,18,0.97)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRight: 'none',
            backdropFilter: 'blur(24px)',
            boxShadow: '-8px 0 32px rgba(0,0,0,0.4)',
            pointerEvents: 'all',
          }}
        >
          {/* Decorative top rule */}
          <div className="w-4 h-px bg-amber-400/20 mb-1" />

          {TOOLS.map(tool => {
            const isActive = activeTool === tool.name
            const isOpen   = openTool === tool.name

            return (
              <button
                key={tool.name}
                onClick={() => handleIconClick(tool.name)}
                title={tool.name}
                className={[
                  'relative flex flex-col items-center justify-center gap-0.5',
                  'w-9 h-9 rounded-md transition-all duration-200',
                  isOpen
                    ? 'bg-amber-400/15 text-amber-400'
                    : isActive
                    ? 'text-amber-400 bg-amber-400/10'
                    : 'text-white/25 hover:text-white/55 hover:bg-white/[0.04]',
                  isActive && !isOpen ? 'dock-icon-active' : '',
                ].join(' ')}
                style={{ pointerEvents: 'all' }}
              >
                {/* Active indicator dot */}
                {isActive && (
                  <span
                    className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-amber-400"
                    style={{ boxShadow: '0 0 4px rgba(251,191,36,0.8)' }}
                  />
                )}
                {tool.icon}
                <span className="font-mono text-[7px] tracking-wider leading-none opacity-60">
                  {tool.label}
                </span>
              </button>
            )
          })}

          {/* Decorative bottom rule */}
          <div className="w-4 h-px bg-white/[0.06] mt-1" />

          {/* Event count badge */}
          {toolEvents.length > 0 && (
            <div className="font-mono text-[7px] text-white/20 tracking-wider mt-0.5">
              {toolEvents.length}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
