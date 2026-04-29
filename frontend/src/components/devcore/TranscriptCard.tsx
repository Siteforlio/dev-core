import React from 'react'
import { useOverlayStore } from '../../store/overlayStore'

export function TranscriptCard() {
  const { transcript, setTranscriptOpen } = useOverlayStore()
  return (
    <div className="bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-[11px] overflow-hidden min-w-[288px] max-w-[50vw] shadow-[0_12px_48px_rgba(0,0,0,0.75)]">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.07] bg-white/[0.015]">
        <span className="font-mono text-[11px] uppercase tracking-widest text-white/30">Transcript</span>
        <button onClick={() => setTranscriptOpen(false)} className="w-[18px] h-[18px] flex items-center justify-center rounded text-white/30 hover:text-white/60 hover:bg-white/5 transition-all">
          <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div className="px-3 py-2.5 flex flex-col gap-2 max-h-[75vh] overflow-y-auto scrollbar-none [&::-webkit-scrollbar]:hidden">
        {transcript.map((e) => (
          <div key={e.seq} className="flex gap-2 items-start">
            <span className={`font-mono text-[10px] w-[30px] flex-shrink-0 pt-0.5 ${e.speaker === 'user' ? 'text-violet-400' : 'text-white/30'}`}>
              {e.speaker === 'user' ? 'you' : 'them'}
            </span>
            <span className="text-[13px] text-white/60 leading-relaxed tracking-tight">{e.text}</span>
          </div>
        ))}
        {transcript.length === 0 && (
          <span className="text-[12px] text-white/20 font-mono">No transcript yet…</span>
        )}
      </div>
    </div>
  )
}
