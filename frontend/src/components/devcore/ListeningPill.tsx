import React from 'react'

export function ListeningPill() {
  return (
    <div className="flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-[rgba(9,9,18,0.97)] border border-white/[0.07] shadow-lg">
      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)] animate-pulse" />
      <span className="font-display text-[10.5px] font-extrabold tracking-[0.15em] text-violet-400">DEVCORE</span>
      <div className="w-px h-3.5 bg-white/[0.07]" />
      <div className="flex items-end gap-[2.5px] h-4">
        {[6, 12, 8, 14, 6, 10].map((h, i) => (
          <span
            key={i}
            className="w-0.5 bg-emerald-400 rounded-sm shadow-[0_0_4px_rgba(52,211,153,0.8)]"
            style={{ height: h, animation: `wave 1.1s ease-in-out ${i * 0.05}s infinite` }}
          />
        ))}
      </div>
      <span className="font-mono text-[9px] text-white/30 tracking-wider">listening...</span>
    </div>
  )
}
