import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import { getFreshToken } from '../../lib/apiFetch'
import { AudioSourcePicker } from './AudioSourcePicker'
import type { SessionContext } from '../../types/devcore'

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

const EMPTY_CONTEXT: SessionContext = {
  jobTitle: '', company: '', resumeText: '', jdText: '', files: [],
}

export function SuggestionCard() {
  const {
    suggestion, latencyMs, transcriptOpen, setTranscriptOpen,
    state, setSessionId, sessionTitle, setSessionTitle, audioSource, micDeviceId, sysDeviceId,
  } = useOverlayStore()
  const api = () => (window as any).electronAPI?.devcore
  const [ask, setAsk] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const askRef = useRef<HTMLInputElement>(null)
  const titleRef = useRef<HTMLInputElement>(null)

  const handleStart = async () => {
    const t = await getFreshToken()
    if (!t) return
    const id = crypto.randomUUID()
    setSessionId(id)
    api()?.startSession({ sessionId: id, context: EMPTY_CONTEXT, audioSource, micDeviceId, sysDeviceId, token: t })
  }
  const handlePause = () => api()?.pauseSession?.()
  const handleEnd   = () => {
    api()?.endSession?.()
    setSessionId(null)
    useOverlayStore.getState().setState('idle')
  }

  const handleAsk = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      askRef.current?.blur()
      api()?.disableInteract?.()
    }
    if (e.key === 'Enter' && ask.trim()) {
      api()?.manualAsk?.({ text: ask.trim(), mode: 'hints' })
      setAsk('')
    }
  }

  // Listen for hotkeys from main process
  useEffect(() => {
    const devcore = api()
    if (!devcore?.onHotkey) return
    const remove = devcore.onHotkey((p: { action: string }) => {
      if (p.action === 'start' && useOverlayStore.getState().state === 'idle') {
        handleStart()
      } else if (p.action === 'ask') {
        askRef.current?.focus()
      }
    })
    return () => remove?.()
  }, [])

  const isActive = state !== 'idle'

  return (
    <div id="overlay-card" className="bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-[13px] overflow-hidden shadow-[0_12px_48px_rgba(0,0,0,0.75)] min-w-[520px] max-w-[85vw]">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.07] bg-white/[0.015]">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 animate-pulse ${isActive ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-white/20'}`} />

        {/* Session title — click to edit */}
        {editingTitle ? (
          <input
            ref={titleRef}
            defaultValue={sessionTitle}
            onBlur={(e) => { setSessionTitle(e.target.value || 'Untitled'); setEditingTitle(false) }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === 'Escape') {
                setSessionTitle((e.target as HTMLInputElement).value || 'Untitled')
                setEditingTitle(false)
              }
            }}
            autoFocus
            className="bg-transparent border-none outline-none font-display text-[13px] font-extrabold tracking-[0.1em] text-white/80 w-40"
          />
        ) : (
          <button
            onClick={() => setEditingTitle(true)}
            className="font-display text-[13px] font-extrabold tracking-[0.1em] text-white/80 hover:text-white transition-colors"
          >
            {sessionTitle}
          </button>
        )}

        {isActive && latencyMs > 0 && (
          <span className="font-mono text-[11px] text-emerald-400 ml-1">{latencyMs}ms</span>
        )}
        <div className="flex-1" />
        {isActive && <AudioSourcePicker />}
        {isActive && (
          <button
            onClick={() => setTranscriptOpen(!transcriptOpen)}
            className={`w-[32px] h-[32px] flex items-center justify-center rounded-md border transition-all ${transcriptOpen ? 'border-violet-400/40 bg-violet-400/10 text-violet-400' : 'border-white/[0.07] bg-white/[0.025] text-white/30 hover:text-white/60'}`}
          >
            <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          </button>
        )}
        {isActive ? (
          <>
            <button onClick={handlePause} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-yellow-300/20 bg-yellow-300/5 text-yellow-300 font-mono text-[11px] hover:bg-yellow-300/10 transition-all">
              <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
              Pause
            </button>
            <button onClick={handleEnd} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-red-400/20 bg-red-400/5 text-red-400 font-mono text-[11px] hover:bg-red-400/10 transition-all">
              <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
              End
            </button>
          </>
        ) : (
          <>
            <MicTestButton micDeviceId={micDeviceId} />
            <button onClick={handleStart} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-emerald-400/30 bg-emerald-400/10 text-emerald-400 font-mono text-[11px] hover:bg-emerald-400/20 transition-all">
              <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Start
            </button>
          </>
        )}
      </div>

      {/* Suggestion */}
      <div className="px-4 pt-3 pb-2.5 border-b border-white/[0.07]">
        <p className="text-[10px] font-mono uppercase tracking-widest text-white/30 mb-1.5">Suggestion</p>
        <div className="flex gap-2.5 items-start max-h-[65vh] overflow-y-auto scrollbar-none [&::-webkit-scrollbar]:hidden">
          <span className="text-violet-400 font-mono text-[13px] flex-shrink-0 mt-0.5">▸</span>
          <p className="text-[14px] text-white/90 leading-relaxed tracking-tight">
            {suggestion || <span className="text-white/20">{isActive ? 'Listening for a question…' : 'Press Start or Ctrl+Shift+Enter'}</span>}
          </p>
        </div>
      </div>

      {/* Ask input */}
      <div className="px-4 py-2.5">
        <div className="flex items-center gap-2 bg-white/[0.03] border border-white/[0.07] rounded-lg px-3 py-2 focus-within:border-violet-400/25 focus-within:bg-violet-400/[0.07] transition-all">
          <span className="font-mono text-[10px] text-white/20 flex-shrink-0">Ctrl+Shift+/</span>
          <input
            ref={askRef}
            value={ask}
            onChange={e => setAsk(e.target.value)}
            onKeyDown={handleAsk}
            placeholder="Ask anything…"
            className="flex-1 bg-transparent border-none outline-none text-[13px] text-white/90 placeholder-white/20 font-sans"
          />
          <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/20 flex-shrink-0"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
        </div>
      </div>
    </div>
  )
}
