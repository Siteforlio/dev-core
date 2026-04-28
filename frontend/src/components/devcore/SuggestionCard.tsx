import React, { useState } from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import { AudioSourcePicker } from './AudioSourcePicker'

export function SuggestionCard() {
  const { suggestion, latencyMs, transcriptOpen, setTranscriptOpen } = useOverlayStore()
  const pauseSession = () => window.electronAPI?.devcore?.pauseSession?.()
  const endSession   = () => window.electronAPI?.devcore?.endSession?.()
  const manualAsk    = (text: string, mode: 'hints' | 'solve', language?: string) =>
    window.electronAPI?.devcore?.manualAsk?.({ text, mode, language })
  const [ask, setAsk] = useState('')

  const handleAsk = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && ask.trim()) {
      manualAsk(ask.trim(), 'hints')
      setAsk('')
    }
  }

  return (
    <div className="bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-[11px] overflow-hidden shadow-[0_12px_48px_rgba(0,0,0,0.75)] w-[480px]">
      {/* Header */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-white/[0.07] bg-white/[0.015]">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)] animate-pulse flex-shrink-0" />
        <span className="font-display text-[10.5px] font-extrabold tracking-[0.15em] text-violet-400">DEVCORE</span>
        <div className="flex items-center gap-1 ml-1">
          <span className="w-1 h-1 rounded-full bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,0.8)]" />
          <span className="font-mono text-[9px] text-emerald-400">{latencyMs > 0 ? `${latencyMs}ms` : '—'}</span>
        </div>
        <div className="flex-1" />
        <AudioSourcePicker />
        <button
          onClick={() => setTranscriptOpen(!transcriptOpen)}
          className={`w-[27px] h-[27px] flex items-center justify-center rounded-md border transition-all ${transcriptOpen ? 'border-violet-400/40 bg-violet-400/10 text-violet-400' : 'border-white/[0.07] bg-white/[0.025] text-white/30 hover:text-white/60'}`}
        >
          <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        </button>
        <button onClick={pauseSession} className="flex items-center gap-1 px-2 py-1 rounded-md border border-yellow-300/20 bg-yellow-300/5 text-yellow-300 font-mono text-[9px] hover:bg-yellow-300/10 transition-all">
          <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
          Pause
        </button>
        <button onClick={endSession} className="flex items-center gap-1 px-2 py-1 rounded-md border border-red-400/20 bg-red-400/5 text-red-400 font-mono text-[9px] hover:bg-red-400/10 transition-all">
          <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
          End
        </button>
      </div>
      {/* Suggestion */}
      <div className="px-3 pt-2.5 pb-2 border-b border-white/[0.07]">
        <p className="text-[8px] font-mono uppercase tracking-widest text-white/30 mb-1">Suggestion</p>
        <div className="flex gap-2 items-start">
          <span className="text-violet-400 font-mono text-[10px] flex-shrink-0 mt-0.5">▸</span>
          <p className="text-[12px] text-white/90 leading-relaxed tracking-tight">
            {suggestion || <span className="text-white/20">Listening for a question…</span>}
          </p>
        </div>
      </div>
      {/* Input */}
      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5 bg-white/[0.03] border border-white/[0.07] rounded-lg px-2.5 py-1.5 focus-within:border-violet-400/25 focus-within:bg-violet-400/[0.07] transition-all">
          <span className="font-mono text-[8px] text-white/20 flex-shrink-0">⌘/</span>
          <input
            value={ask}
            onChange={e => setAsk(e.target.value)}
            onKeyDown={handleAsk}
            placeholder="Ask anything…"
            className="flex-1 bg-transparent border-none outline-none text-[11.5px] text-white/90 placeholder-white/20 font-sans"
          />
          <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/20 flex-shrink-0"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
        </div>
      </div>
    </div>
  )
}
