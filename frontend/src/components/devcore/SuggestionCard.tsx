import React, { useState, useEffect, useRef } from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import { getFreshToken } from '../../lib/apiFetch'
import { AudioSourcePicker } from './AudioSourcePicker'
import type { AssessmentMode, SessionContext } from '../../types/devcore'

const MODE_HEADER: Record<NonNullable<AssessmentMode> | 'standard', string> = {
  standard: 'bg-white/[0.015] border-white/[0.07]',
  coding:   'bg-amber-400/[0.07]  border-amber-400/[0.15]',
  live:     'bg-emerald-400/[0.07] border-emerald-400/[0.15]',
  ai_model: 'bg-sky-400/[0.07]    border-sky-400/[0.15]',
}

const MODE_ACCENT: Record<NonNullable<AssessmentMode> | 'standard', string> = {
  standard: 'bg-violet-400',
  coding:   'bg-amber-400',
  live:     'bg-emerald-400',
  ai_model: 'bg-sky-400',
}

const MODE_WATERMARK: Record<NonNullable<AssessmentMode> | 'standard', { text: string; color: string } | null> = {
  standard: null,
  coding:   { text: 'CODING',   color: 'text-amber-400/[0.06]'  },
  live:     { text: 'LIVE',     color: 'text-emerald-400/[0.06]' },
  ai_model: { text: 'AI MODEL', color: 'text-sky-400/[0.06]'     },
}

interface ChatMessage {
  id: string
  role: 'user' | 'ai' | 'auto'  // user = manual ask, ai = response, auto = auto-triggered suggestion
  text: string
  pending?: boolean
}

function MicTestButton({ micDeviceId }: { micDeviceId: number | null }) {
  const [testing, setTesting] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const run = async () => {
    if (testing) return
    setTesting(true)
    setCountdown(5)
    const tick = setInterval(() => setCountdown(c => c - 1), 1000)
    await (window as any).electronAPI?.devcore?.testMic?.({ deviceId: micDeviceId, durationMs: 5000 })
    clearInterval(tick)
    setCountdown(0)
    setTesting(false)
  }
  return (
    <button
      onClick={run}
      disabled={testing}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border font-mono text-[11px] transition-all ${testing ? 'border-amber-400/20 bg-amber-400/5 text-amber-400' : 'border-white/[0.07] bg-white/[0.025] text-white/30 hover:text-white/60 hover:bg-white/[0.04]'}`}
    >
      {testing
        ? <><span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />{countdown}s</>
        : <><svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg>Test Mic</>
      }
    </button>
  )
}

// ---------------------------------------------------------------------------
// Tool strip — inline row of tool icons shown in assessment mode
// ---------------------------------------------------------------------------

const TOOL_ICONS: { name: string; label: string; icon: React.ReactNode }[] = [
  { name: 'terminal', label: 'TERM', icon: (
    <svg width="13" height="13" viewBox="0 0 18 18" fill="none"><polyline points="3,6 7,9 3,12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><line x1="9" y1="12" x2="15" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  )},
  { name: 'screen', label: 'VIEW', icon: (
    <svg width="13" height="13" viewBox="0 0 18 18" fill="none"><rect x="2" y="3" width="14" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><line x1="6" y1="15" x2="12" y2="15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><line x1="9" y1="13" x2="9" y2="15" stroke="currentColor" strokeWidth="1.5"/></svg>
  )},
  { name: 'browser', label: 'WEB', icon: (
    <svg width="13" height="13" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="6.5" stroke="currentColor" strokeWidth="1.5"/><ellipse cx="9" cy="9" rx="3" ry="6.5" stroke="currentColor" strokeWidth="1.5"/><line x1="2.5" y1="6.5" x2="15.5" y2="6.5" stroke="currentColor" strokeWidth="1.5"/><line x1="2.5" y1="11.5" x2="15.5" y2="11.5" stroke="currentColor" strokeWidth="1.5"/></svg>
  )},
  { name: 'file', label: 'FILE', icon: (
    <svg width="13" height="13" viewBox="0 0 18 18" fill="none"><path d="M4 2h7l3 3v11H4V2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><polyline points="11,2 11,5 14,5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><line x1="7" y1="9" x2="11" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><line x1="7" y1="12" x2="11" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  )},
  { name: 'search', label: 'SRCH', icon: (
    <svg width="13" height="13" viewBox="0 0 18 18" fill="none"><circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5"/><line x1="12" y1="12" x2="15.5" y2="15.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  )},
]

function ToolStrip() {
  const { activeTool, toolEvents } = useOverlayStore()
  const [openTool, setOpenTool] = React.useState<string | null>(null)

  // Build latest data per tool from events
  const latestByTool = React.useMemo(() => {
    const map: Record<string, Record<string, unknown>> = {}
    for (const ev of toolEvents) {
      if (!map[ev.tool]) map[ev.tool] = {}
      Object.assign(map[ev.tool], ev.data)
    }
    return map
  }, [toolEvents])

  const termLines = React.useMemo(() =>
    toolEvents.filter(e => e.tool === 'terminal' && e.data.text).map(e => ({
      stream: e.data.stream as string,
      text: e.data.text as string,
    })),
  [toolEvents])

  const termRef = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    if (openTool === 'terminal' && termRef.current) {
      termRef.current.scrollTop = termRef.current.scrollHeight
    }
  }, [termLines.length, openTool])

  return (
    <div className="mt-2">
      {/* Icon row */}
      <div className="flex items-center justify-center gap-1.5">
        <span className="font-mono text-[8px] tracking-widest text-white/20 uppercase mr-1">Tools</span>
        {TOOL_ICONS.map(t => {
          const isActive = activeTool === t.name
          const isOpen   = openTool === t.name
          return (
            <button
              key={t.name}
              onClick={() => setOpenTool(prev => prev === t.name ? null : t.name)}
              className={[
                'relative flex flex-col items-center justify-center gap-0.5 px-2 py-1.5 rounded-md border transition-all',
                isOpen    ? 'border-amber-400/30 bg-amber-400/10 text-amber-400'
                : isActive ? 'border-amber-400/20 bg-amber-400/[0.06] text-amber-400'
                           : 'border-white/[0.06] bg-white/[0.02] text-white/25 hover:text-white/50 hover:border-white/[0.1]',
              ].join(' ')}
              title={t.name}
            >
              {isActive && (
                <span className="absolute top-0.5 right-0.5 w-1 h-1 rounded-full bg-amber-400" style={{ boxShadow: '0 0 4px rgba(251,191,36,0.9)' }} />
              )}
              {t.icon}
              <span className="font-mono text-[7px] leading-none tracking-wider">{t.label}</span>
            </button>
          )
        })}
      </div>

      {/* Expanded panel */}
      {openTool && (
        <div className="mt-1.5 rounded-lg border border-white/[0.07] bg-[rgba(9,9,18,0.80)] overflow-hidden">
          {/* panel header */}
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.06]">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" style={{ boxShadow: '0 0 5px rgba(251,191,36,0.8)' }} />
              <span className="font-mono text-[9px] tracking-widest text-amber-400/70 uppercase">{openTool}</span>
            </div>
            <button onClick={() => setOpenTool(null)} className="font-mono text-[10px] text-white/25 hover:text-white/60 px-1">✕</button>
          </div>

          {/* panel body */}
          <div className="max-h-[160px] overflow-y-auto px-3 py-2 [&::-webkit-scrollbar]:w-[2px] [&::-webkit-scrollbar-thumb]:bg-white/10">
            {openTool === 'terminal' && (
              <div ref={termRef} className="space-y-0.5">
                {termLines.length === 0
                  ? <p className="font-mono text-[10px] text-white/20 italic">awaiting output…</p>
                  : termLines.map((l, i) => (
                    <div key={i} className={`font-mono text-[10px] leading-relaxed whitespace-pre-wrap break-all ${l.stream === 'stderr' ? 'text-red-400/80' : 'text-emerald-300/80'}`}>{l.text}</div>
                  ))
                }
              </div>
            )}
            {openTool === 'screen' && (
              <div className="space-y-1.5">
                {latestByTool.screen?.image
                  ? <img src={`data:image/png;base64,${latestByTool.screen.image}`} className="w-full rounded border border-white/[0.07]" alt="capture" />
                  : <p className="font-mono text-[10px] text-white/20 italic">no capture yet</p>
                }
                {latestByTool.screen?.text && <p className="font-mono text-[10px] text-white/50 leading-relaxed">{(latestByTool.screen.text as string).slice(0, 300)}</p>}
              </div>
            )}
            {openTool === 'browser' && (
              <div className="space-y-1">
                {latestByTool.browser?.url && <p className="font-mono text-[9px] text-violet-300/60 truncate">{latestByTool.browser.url as string}</p>}
                <p className="font-mono text-[10px] text-white/55 leading-relaxed">
                  {(latestByTool.browser?.text as string ?? latestByTool.browser?.problem_text as string ?? 'no page loaded').slice(0, 400)}
                </p>
              </div>
            )}
            {openTool === 'file' && (
              <div className="space-y-1">
                {latestByTool.file?.path && <p className="font-mono text-[9px] text-amber-300/50 truncate">{latestByTool.file.path as string}</p>}
                {latestByTool.file?.diff
                  ? <pre className="font-mono text-[10px] leading-relaxed whitespace-pre-wrap break-all text-white/60">
                      {(latestByTool.file.diff as string).split('\n').map((line, i) => (
                        <span key={i} className={`block ${line.startsWith('+') ? 'text-emerald-400/80' : line.startsWith('-') ? 'text-red-400/70' : ''}`}>{line}</span>
                      ))}
                    </pre>
                  : <p className="font-mono text-[10px] text-white/50 leading-relaxed">{(latestByTool.file?.content as string ?? latestByTool.file?.listing as string ?? 'no file events').slice(0, 400)}</p>
                }
              </div>
            )}
            {openTool === 'search' && (
              <div className="space-y-2">
                {latestByTool.search?.query && <p className="font-mono text-[9px] text-violet-300/60">"{latestByTool.search.query as string}"</p>}
                {((latestByTool.search?.results as any[]) ?? []).slice(0, 3).map((r: any, i: number) => (
                  <div key={i} className="border-l-2 border-amber-400/30 pl-2 space-y-0.5">
                    <p className="font-mono text-[10px] text-amber-300/70 font-semibold">{r.title}</p>
                    <p className="font-mono text-[10px] text-white/45">{r.snippet?.slice(0, 160)}</p>
                  </div>
                ))}
                {!latestByTool.search?.results && <p className="font-mono text-[10px] text-white/20 italic">no searches yet</p>}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const EMPTY_CONTEXT: SessionContext = {
  jobTitle: '', company: '', resumeText: '', jdText: '', files: [],
}

// Module-level token cache — persists across renders in the overlay process
let _overlayToken: string | null = null

const AI_PENDING_ID = '__ai_pending__'

export function SuggestionCard() {
  const {
    latencyMs, transcriptOpen, setTranscriptOpen,
    state, setSessionId, sessionTitle, setSessionTitle,
    audioSource, micDeviceId, sysDeviceId, assessmentMode,
  } = useOverlayStore()

  const modeKey     = assessmentMode ?? 'standard'
  const headerStyle = MODE_HEADER[modeKey]
  const accentDot   = MODE_ACCENT[modeKey]
  const watermark   = MODE_WATERMARK[modeKey]

  const api = () => (window as any).electronAPI?.devcore
  const [authed, setAuthed] = useState<boolean | null>(null)
  const [ask, setAsk] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [aiStreaming, setAiStreaming] = useState(false)
  const [outcome, setOutcome] = useState<{ text: string; question: string } | null>(null)
  const [outcomeExpanded, setOutcomeExpanded] = useState(false)
  const [sessionPickerOpen, setSessionPickerOpen] = useState(false)
  const [recentSessions, setRecentSessions] = useState<any[]>([])
  const askRef = useRef<HTMLInputElement>(null)
  const titleRef = useRef<HTMLInputElement>(null)
  const chatBottomRef = useRef<HTMLDivElement>(null)
  const pickerRef = useRef<HTMLDivElement>(null)
  const lastSessionRef = useRef<{ id: string; title: string; role: string; company: string } | null>(null)

  // Check auth on mount and whenever localStorage changes (e.g. user logs in from main window)
  useEffect(() => {
    const check = async () => {
      const t = _overlayToken ?? await getFreshToken()
      if (!t) {
        try {
          const raw = localStorage.getItem('auth')
          if (raw) {
            const stored = JSON.parse(raw)?.state?.accessToken ?? null
            if (stored) { _overlayToken = stored; setAuthed(true); return }
          }
        } catch {}
      }
      setAuthed(!!t)
    }
    check()

    const onStorage = (e: StorageEvent) => {
      if (e.key === 'auth') check()
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  // Sync UI state with actual WS connection
  useEffect(() => {
    const sync = async () => {
      const s = await api()?.getStatus?.()
      if (!s) return
      const { state: cur } = useOverlayStore.getState()
      if (!s.connected && cur !== 'idle') {
        useOverlayStore.getState().setState('idle')
        useOverlayStore.getState().setSessionId(null)
      }
    }
    sync()
    const interval = setInterval(sync, 3000)
    return () => clearInterval(interval)
  }, [])

  // Handle AI suggestion streaming — map onto chat messages
  useEffect(() => {
    const devcore = api()
    if (!devcore) return

    const removeSuggestion = devcore.onSuggestion(({ delta, done }: { delta: string; done: boolean }) => {
      setMessages(prev => {
        const pending = prev.find(m => m.id === AI_PENDING_ID)
        if (!pending) {
          // First delta — create the pending AI message
          return [...prev, { id: AI_PENDING_ID, role: 'ai', text: delta, pending: true }]
        }
        if (done) {
          // Finalize
          return prev.map(m => m.id === AI_PENDING_ID
            ? { ...m, id: crypto.randomUUID(), pending: false }
            : m
          )
        }
        // Append delta
        return prev.map(m => m.id === AI_PENDING_ID ? { ...m, text: m.text + delta } : m)
      })
      if (done) setAiStreaming(false)
      else setAiStreaming(true)
    })

    const removeStatus = devcore.onStatus(({ state: s }: { state: string }) => {
      if (s === 'thinking') {
        setAiStreaming(true)
        // Add pending bubble immediately so user sees "thinking"
        setMessages(prev => {
          if (prev.find(m => m.id === AI_PENDING_ID)) return prev
          return [...prev, { id: AI_PENDING_ID, role: 'ai', text: '', pending: true }]
        })
      }
      useOverlayStore.getState().setState(s as any)
      useOverlayStore.getState().setLatency(0)
    })

    const removeOutcome = devcore.onOutcome?.(({ outcome: o, question: q }: { outcome: string; question: string }) => {
      setOutcome({ text: o, question: q })
      setOutcomeExpanded(false)
    })

    const removeTitle = devcore.onSessionTitle?.(({ title }: { title: string }) => {
      if (title) setSessionTitle(title)
    })

    return () => {
      removeSuggestion?.()
      removeStatus?.()
      removeOutcome?.()
      removeTitle?.()
    }
  }, [])

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchRecentSessions = async () => {
    // Try cached token, then auth store, then direct localStorage read (overlay file:// origin)
    let t = _overlayToken ?? await getFreshToken()
    if (!t) {
      try {
        const raw = localStorage.getItem('auth')
        if (raw) t = JSON.parse(raw)?.state?.accessToken ?? null
      } catch {}
    }
    if (!t) return
    try {
      const r = await fetch('http://localhost:8000/api/v1/cluely/sessions?limit=10', {
        headers: { Authorization: `Bearer ${t}` },
      })
      const data = r.ok ? await r.json() : null
      if (data?.sessions) setRecentSessions(data.sessions)
    } catch {}
  }

  // Close picker on outside click
  useEffect(() => {
    if (!sessionPickerOpen) return
    const handler = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) setSessionPickerOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [sessionPickerOpen])

  const handleStart = async () => {
    const t = _overlayToken ?? await getFreshToken()
    if (!t) return
    _overlayToken = t

    if (lastSessionRef.current) {
      // Reconnect to the same session — messages + transcript already in state, don't clear them
      const prev = lastSessionRef.current
      setSessionId(prev.id)
      setSessionTitle(prev.title)
      api()?.startSession({
        sessionId: prev.id,
        context: { jobTitle: prev.role, company: prev.company, resumeText: '', jdText: '', files: [] },
        audioSource, micDeviceId, sysDeviceId, token: t,
      })
    } else {
      // Brand new session
      const id = crypto.randomUUID()
      setSessionId(id)
      setSessionTitle('Starting…')
      setMessages([])
      useOverlayStore.getState().setTranscript([])
      api()?.startSession({ sessionId: id, context: EMPTY_CONTEXT, audioSource, micDeviceId, sysDeviceId, token: t })
    }
  }

  const handleResumeSession = async (session: any) => {
    setSessionPickerOpen(false)
    lastSessionRef.current = null  // explicit pick — don't auto-resume on next start
    const t = _overlayToken ?? await getFreshToken()
    if (!t) return
    _overlayToken = t
    setSessionId(session.id)
    setSessionTitle(session.title)

    // Load history from backend
    try {
      const r = await fetch(`http://localhost:8000/api/v1/cluely/sessions/${session.id}`, {
        headers: { Authorization: `Bearer ${t}` },
      })
      const data = r.ok ? await r.json() : null
      if (data) {
        // Rebuild chat messages from interactions (Q+A pairs)
        const history: ChatMessage[] = []
        for (const i of data.interactions ?? []) {
          if (i.question) history.push({ id: crypto.randomUUID(), role: 'user', text: i.question })
          if (i.answer)   history.push({ id: crypto.randomUUID(), role: 'ai',   text: i.answer  })
        }
        setMessages(history)

        // Restore transcript into overlay store
        if (data.transcript?.length) {
          useOverlayStore.getState().setTranscript(data.transcript)
        }
      }
    } catch {}

    api()?.startSession({
      sessionId: session.id,
      context: {
        jobTitle: session.role ?? '',
        company:  session.company ?? '',
        resumeText: '', jdText: '', files: [],
      },
      audioSource, micDeviceId, sysDeviceId, token: t,
    })
  }

  const handlePause = () => api()?.pauseSession?.()
  const handleEnd = () => {
    const { sessionId: sid, sessionTitle: title } = useOverlayStore.getState()
    // Save session ref so Start can reconnect — do NOT clear messages or transcript
    if (sid) lastSessionRef.current = { id: sid, title, role: '', company: '' }
    api()?.endSession?.()
    setSessionId(null)
    setOutcome(null)
    useOverlayStore.getState().setState('idle')
    // messages and transcript intentionally kept in state
  }

  const sendAsk = (text: string) => {
    if (!text.trim() || aiStreaming) return
    // Show user message immediately
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', text: text.trim() }])
    // Send to backend
    const devcore = api()
    console.log('[overlay] sendAsk — api available:', !!devcore, '| manualAsk:', !!devcore?.manualAsk)
    devcore?.manualAsk?.({ text: text.trim(), mode: 'hints' })
    setAsk('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      askRef.current?.blur()
      api()?.disableInteract?.()
    }
    if (e.key === 'Enter') {
      sendAsk(ask)
    }
  }

  const handleInputFocus = () => {
    // Enable interact mode so typing works
    api()?.enableInteract?.()
  }

  const handleInputBlur = () => {
    // Only disable if ask is empty (don't disable mid-typing)
    if (!ask) api()?.disableInteract?.()
  }

  // Hotkeys
  useEffect(() => {
    const devcore = api()
    if (!devcore?.onHotkey) return
    const remove = devcore.onHotkey((p: { action: string }) => {
      if (p.action === 'start' && useOverlayStore.getState().state === 'idle') {
        handleStart()
      } else if (p.action === 'ask') {
        api()?.enableInteract?.()
        askRef.current?.focus()
      } else if (p.action === 'suggest') {
        const { transcript, state: s } = useOverlayStore.getState()
        if (s === 'idle') return
        const lastInterviewer = [...transcript].reverse().find(t => t.speaker === 'interviewer')
        const text = lastInterviewer?.text || 'Please provide interview assistance based on the current context.'
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'auto', text: `↩ Auto: "${text.slice(0, 60)}${text.length > 60 ? '…' : ''}"` }])
        api()?.manualAsk?.({ text, mode: 'hints' })
      }
    })
    return () => remove?.()
  }, [])

  const isActive = state !== 'idle'

  if (authed === false) {
    return (
      <div className="bg-[rgba(9,9,18,0.60)] backdrop-blur-xl border border-white/[0.07] rounded-[13px] shadow-[0_12px_48px_rgba(0,0,0,0.75)] px-6 py-5 flex items-center gap-3" style={{ width: '594px' }}>
        <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-amber-400 flex-shrink-0"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
        <div>
          <p className="font-mono text-[12px] text-white/80">Not logged in</p>
          <p className="font-mono text-[10px] text-white/35 mt-0.5">Open the DevCore app and sign in, then restart the overlay.</p>
        </div>
      </div>
    )
  }

  return (
    <div id="overlay-card" className="relative bg-[rgba(9,9,18,0.60)] backdrop-blur-xl border border-white/[0.07] rounded-[13px] overflow-hidden shadow-[0_12px_48px_rgba(0,0,0,0.75)]" style={{ width: '594px' }}>

      {/* Session type watermark — sits behind all content, pointer-events-none */}
      {watermark && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none overflow-hidden">
          <span
            className={`font-orbitron font-black tracking-[0.25em] uppercase ${watermark.color}`}
            style={{ fontSize: '72px', transform: 'rotate(-12deg)', whiteSpace: 'nowrap' }}
          >
            {watermark.text}
          </span>
        </div>
      )}

      {/* Header */}
      <div className={`flex items-center gap-2 px-4 py-2.5 border-b transition-colors duration-500 ${headerStyle}`}>
        <span className={`w-2 h-2 rounded-full flex-shrink-0 transition-colors duration-500 ${isActive ? `animate-pulse ${accentDot} shadow-[0_0_8px_rgba(52,211,153,0.8)]` : 'bg-white/20'}`} />
        <div className="relative" ref={pickerRef}>
          {editingTitle ? (
            <input
              ref={titleRef}
              defaultValue={sessionTitle}
              onBlur={e => { setSessionTitle(e.target.value || 'Session'); setEditingTitle(false) }}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') { setSessionTitle((e.target as HTMLInputElement).value || 'Session'); setEditingTitle(false) } }}
              autoFocus
              className="bg-transparent border-none outline-none font-display text-[13px] font-extrabold tracking-[0.1em] text-white/80 w-44"
            />
          ) : (
            <button
              onClick={() => { if (!isActive) { setSessionPickerOpen(v => !v); fetchRecentSessions() } }}
              onDoubleClick={() => isActive && setEditingTitle(true)}
              className={`flex items-center gap-1.5 font-display text-[13px] font-extrabold tracking-[0.1em] transition-all ${
                isActive
                  ? 'text-white/80'
                  : 'text-white/80 hover:text-white px-2 py-0.5 rounded-md border border-white/[0.10] hover:border-white/20 bg-white/[0.04] hover:bg-white/[0.07]'
              }`}
              title={isActive ? 'Double-click to rename' : 'Click to switch session'}
            >
              {sessionTitle}
              {!isActive && (
                <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" className="text-white/50 flex-shrink-0">
                  <path d="m6 9 6 6 6-6"/>
                </svg>
              )}
            </button>
          )}

          {/* Session picker dropdown */}
          {sessionPickerOpen && !isActive && (
            <div className="absolute top-full mt-2 left-0 bg-[rgba(12,12,22,0.99)] border border-white/[0.12] rounded-xl shadow-2xl z-50 w-[300px] overflow-hidden">
              <div className="px-3 py-2 border-b border-white/[0.07] flex items-center justify-between">
                <span className="font-mono text-[9px] uppercase tracking-widest text-white/40">Sessions</span>
                <button
                  onClick={() => { setSessionPickerOpen(false); lastSessionRef.current = null; handleStart() }}
                  className="flex items-center gap-1 px-2 py-0.5 rounded-md border border-violet-400/30 bg-violet-400/10 text-violet-400 font-mono text-[9px] hover:bg-violet-400/20 transition-all"
                >
                  <svg width="8" height="8" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                  New
                </button>
              </div>
              <div className="max-h-[45vh] overflow-y-auto [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-white/20">
                {recentSessions.length === 0 && (
                  <p className="font-mono text-[10px] text-white/30 px-3 py-4 text-center">No sessions yet</p>
                )}
                {recentSessions.map(s => {
                  const date = s.started_at ? new Date(s.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''
                  const dur  = s.duration_seconds ? `${Math.round(s.duration_seconds / 60)}m` : ''
                  return (
                    <button
                      key={s.id}
                      onClick={() => handleResumeSession(s)}
                      className="flex items-center gap-2.5 w-full text-left px-3 py-2.5 hover:bg-white/[0.05] transition-all border-b border-white/[0.04] last:border-0 group"
                    >
                      <div className="w-1.5 h-1.5 rounded-full bg-violet-400/40 flex-shrink-0 group-hover:bg-violet-400 transition-colors" />
                      <div className="flex-1 min-w-0">
                        <div className="text-[12px] text-white/80 truncate font-medium group-hover:text-white transition-colors">{s.title}</div>
                        <div className="font-mono text-[9px] text-white/30 mt-0.5">
                          {date}{dur ? ` · ${dur}` : ''}{s.transcript_lines ? ` · ${s.transcript_lines} lines` : ''}
                        </div>
                      </div>
                      <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" className="text-white/20 group-hover:text-violet-400 flex-shrink-0 transition-colors"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
        {isActive && latencyMs > 0 && <span className="font-mono text-[10px] text-emerald-400 ml-1">{latencyMs}ms</span>}
        <div className="flex-1" />
        <AudioSourcePicker />
        {isActive && (
          <button
            onClick={() => setTranscriptOpen(!transcriptOpen)}
            className={`w-[30px] h-[30px] flex items-center justify-center rounded-md border transition-all ${transcriptOpen ? 'border-violet-400/40 bg-violet-400/10 text-violet-400' : 'border-white/[0.07] bg-white/[0.025] text-white/30 hover:text-white/60'}`}
          >
            <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </button>
        )}
        {isActive ? (
          <>
            <button onClick={handlePause} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-yellow-300/20 bg-yellow-300/5 text-yellow-300 font-mono text-[11px] hover:bg-yellow-300/10 transition-all">
              <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
              Pause
            </button>
            <button onClick={handleEnd} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-red-400/20 bg-red-400/5 text-red-400 font-mono text-[11px] hover:bg-red-400/10 transition-all">
              <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
              End
            </button>
          </>
        ) : (
          <>
            <button onClick={handleStart} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-emerald-400/30 bg-emerald-400/10 text-emerald-400 font-mono text-[11px] hover:bg-emerald-400/20 transition-all">
              <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Start
            </button>
          </>
        )}
      </div>

      {/* Outcome pill — shows inferred interview goal, tap for full answer */}
      {isActive && outcome && (
        <div className="px-4 pt-2.5 pb-0">
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] cursor-pointer hover:bg-amber-400/[0.1] transition-all group"
            onClick={() => setOutcomeExpanded(v => !v)}
          >
            <span className="text-amber-400 font-mono text-[10px] flex-shrink-0">▸ Land on:</span>
            <span className="text-amber-300/90 text-[12px] leading-snug flex-1 break-words min-w-0">
              {outcome.text}
            </span>
            <button
              className="flex-shrink-0 px-2 py-0.5 rounded-md border border-amber-400/20 bg-amber-400/10 text-amber-400 font-mono text-[10px] opacity-0 group-hover:opacity-100 transition-opacity hover:bg-amber-400/20"
              onClick={e => {
                e.stopPropagation()
                if (aiStreaming) return
                api()?.outcomeAsk?.({ outcome: outcome.text })
              }}
            >
              Full answer
            </button>
          </div>
          {outcomeExpanded && (
            <div className="mt-1.5 px-3 py-2 rounded-lg border border-white/[0.06] bg-white/[0.02] text-[12px] text-white/50 leading-relaxed">
              <span className="text-white/30 font-mono text-[10px]">Question: </span>
              {outcome.question}
            </div>
          )}
        </div>
      )}

      {/* Chat messages */}
      <div className="flex flex-col gap-2 px-4 py-3 max-h-[55vh] overflow-y-auto scrollbar-none [&::-webkit-scrollbar]:hidden">
        {messages.length === 0 && (
          <p className="text-[12px] text-white/20 text-center py-4">
            {isActive ? 'Listening… press Ctrl+Shift+G or type a question below' : 'Start a session to begin'}
          </p>
        )}
        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' && (
              <div className="max-w-[80%] px-3 py-2 rounded-xl rounded-tr-sm bg-violet-500/20 border border-violet-400/20 text-[13px] text-white/90 leading-relaxed">
                {msg.text}
              </div>
            )}
            {(msg.role === 'ai' || msg.role === 'auto') && (
              <div className="max-w-[90%] flex gap-2 items-start">
                <span className="text-violet-400 font-mono text-[12px] flex-shrink-0 mt-1">▸</span>
                <div className="text-[13px] text-white/90 leading-relaxed">
                  {msg.text
                    ? msg.text
                    : <span className="flex gap-1 items-center text-white/30">
                        <span className="w-1 h-1 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-1 h-1 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-1 h-1 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                      </span>
                  }
                  {msg.pending && msg.text && (
                    <span className="inline-block w-0.5 h-3.5 bg-violet-400 ml-0.5 animate-pulse align-middle" />
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
        <div ref={chatBottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-3">
        <div className={`flex items-center gap-2 bg-white/[0.03] border rounded-xl px-3 py-2.5 transition-all ${ask ? 'border-violet-400/30 bg-violet-400/[0.05]' : 'border-white/[0.07]'}`}>
          <input
            ref={askRef}
            value={ask}
            onChange={e => setAsk(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={handleInputFocus}
            onBlur={handleInputBlur}
            placeholder="Ask anything… (Ctrl+Shift+/ · Ctrl+Shift+G to auto-trigger)"
            disabled={aiStreaming || !isActive}
            className="flex-1 bg-transparent border-none outline-none text-[13px] text-white/90 placeholder-white/25 font-sans disabled:opacity-40"
          />
          <button
            onClick={() => sendAsk(ask)}
            disabled={!ask.trim() || aiStreaming || !isActive}
            className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-lg bg-violet-500/30 border border-violet-400/20 text-violet-400 hover:bg-violet-500/50 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
          >
            <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
          </button>
        </div>

        {/* Tool strip — only in assessment mode */}
        {assessmentMode && <ToolStrip />}
      </div>
    </div>
  )
}
