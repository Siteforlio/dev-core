import React, { useState, useEffect, useRef } from 'react'
import { useOverlayStore } from '../../store/overlayStore'

const OPTIONS = [
  { value: 'both',   label: 'Mic + System' },
  { value: 'mic',    label: 'Mic only' },
  { value: 'system', label: 'System only' },
] as const

export function AudioSourcePicker() {
  const { audioSource, setAudioSource } = useOverlayStore()
  const [open, setOpen] = useState(false)
  const selected = OPTIONS.find(o => o.value === audioSource)!
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-2 py-1 rounded-md border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.055] transition-all"
      >
        <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/50"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
        <span className="font-mono text-[9px] text-white/60 whitespace-nowrap">{selected.label}</span>
        <svg width="9" height="9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/30"><path d="m6 9 6 6 6-6"/></svg>
      </button>
      {open && (
        <div className="absolute top-full mt-1 right-0 bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-lg overflow-hidden shadow-xl z-50">
          {OPTIONS.map(o => (
            <button
              key={o.value}
              onClick={() => { setAudioSource(o.value); setOpen(false) }}
              className={`block w-full text-left px-3 py-2 font-mono text-[9px] whitespace-nowrap transition-all ${audioSource === o.value ? 'text-violet-400 bg-violet-400/10' : 'text-white/60 hover:bg-white/5'}`}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
