import React, { useState, useEffect, useRef } from 'react'
import { useOverlayStore, type AudioDevice } from '../../store/overlayStore'

const SOURCE_OPTIONS = [
  { value: 'both',   label: 'Mic + System' },
  { value: 'mic',    label: 'Mic only' },
  { value: 'system', label: 'System only' },
] as const

export function AudioSourcePicker() {
  const { audioSource, setAudioSource, micDeviceId, setMicDeviceId, sysDeviceId, setSysDeviceId } = useOverlayStore()
  const [open, setOpen] = useState(false)
  const [mics, setMics] = useState<AudioDevice[]>([])
  const [systems, setSystems] = useState<AudioDevice[]>([])
  const [testing, setTesting] = useState(false)
  const [testCountdown, setTestCountdown] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  // Fetch available devices when dropdown opens
  useEffect(() => {
    if (!open) return
    const api = (window as any).electronAPI?.devcore
    api?.listDevices?.().then((result: { mics: AudioDevice[]; systems: AudioDevice[] }) => {
      if (!result) return
      setMics(result.mics ?? [])
      setSystems(result.systems ?? [])
      // Auto-select first device if none selected yet
      if (micDeviceId === null && result.mics.length > 0) setMicDeviceId(result.mics[0].id)
      if (sysDeviceId === null && result.systems.length > 0) setSysDeviceId(result.systems[0].id)
    })
  }, [open])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleTestMic = async () => {
    if (testing) return
    setTesting(true)
    const DURATION = 5
    setTestCountdown(DURATION)
    const tick = setInterval(() => setTestCountdown(c => c - 1), 1000)
    const api = (window as any).electronAPI?.devcore
    await api?.testMic?.({ deviceId: micDeviceId, durationMs: DURATION * 1000 })
    clearInterval(tick)
    setTestCountdown(0)
    setTesting(false)
  }

  const selectedSource = SOURCE_OPTIONS.find(o => o.value === audioSource)!
  const selectedMicName = mics.find(m => m.id === micDeviceId)?.name ?? 'Default mic'
  const selectedSysName = systems.find(s => s.id === sysDeviceId)?.name ?? 'Default system'

  const showMics    = audioSource === 'mic'    || audioSource === 'both'
  const showSystems = audioSource === 'system' || audioSource === 'both'

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-2 py-1 rounded-md border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.055] transition-all"
      >
        <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/50"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
        <span className="font-mono text-[9px] text-white/60 whitespace-nowrap">{selectedSource.label}</span>
        <svg width="9" height="9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/30"><path d="m6 9 6 6 6-6"/></svg>
      </button>

      {open && (
        <div className="absolute top-full mt-1 right-0 bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-lg overflow-y-auto max-h-[60vh] shadow-xl z-50 w-[168px]">
          {/* Source type */}
          <div className="px-2 pt-1.5 pb-1">
            <p className="font-mono text-[7px] uppercase tracking-widest text-white/25 mb-0.5">Source</p>
            {SOURCE_OPTIONS.map(o => (
              <button
                key={o.value}
                onClick={() => setAudioSource(o.value)}
                className={`flex items-center gap-1.5 w-full text-left px-1.5 py-1 rounded font-mono text-[9px] transition-all ${audioSource === o.value ? 'text-violet-400 bg-violet-400/10' : 'text-white/50 hover:bg-white/5'}`}
              >
                <span className={`w-1 h-1 rounded-full flex-shrink-0 ${audioSource === o.value ? 'bg-violet-400' : 'bg-transparent'}`} />
                {o.label}
              </button>
            ))}
          </div>

          {/* Mic device picker */}
          {showMics && mics.length > 0 && (
            <>
              <div className="mx-2 my-0.5 h-px bg-white/[0.07]" />
              <div className="px-2 pb-1">
                <p className="font-mono text-[7px] uppercase tracking-widest text-white/25 mb-0.5">Mic</p>
                {mics.map(m => (
                  <button
                    key={m.id}
                    onClick={() => setMicDeviceId(m.id)}
                    className={`flex items-center gap-1.5 w-full text-left px-1.5 py-1 rounded font-mono text-[9px] transition-all ${micDeviceId === m.id ? 'text-emerald-400 bg-emerald-400/10' : 'text-white/40 hover:bg-white/5'}`}
                    title={m.name}
                  >
                    <span className={`w-1 h-1 rounded-full flex-shrink-0 ${micDeviceId === m.id ? 'bg-emerald-400' : 'bg-transparent'}`} />
                    <span className="truncate">{m.name}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          {/* System audio picker */}
          {showSystems && systems.length > 0 && (
            <>
              <div className="mx-2 my-0.5 h-px bg-white/[0.07]" />
              <div className="px-2 pb-1.5">
                <p className="font-mono text-[7px] uppercase tracking-widest text-white/25 mb-0.5">System</p>
                {systems.map(s => (
                  <button
                    key={s.id}
                    onClick={() => setSysDeviceId(s.id)}
                    className={`flex items-center gap-1.5 w-full text-left px-1.5 py-1 rounded font-mono text-[9px] transition-all ${sysDeviceId === s.id ? 'text-emerald-400 bg-emerald-400/10' : 'text-white/40 hover:bg-white/5'}`}
                    title={s.name}
                  >
                    <span className={`w-1 h-1 rounded-full flex-shrink-0 ${sysDeviceId === s.id ? 'bg-emerald-400' : 'bg-transparent'}`} />
                    <span className="truncate">{s.name}</span>
                  </button>
                ))}
              </div>
            </>
          )}
          {/* Test mic button */}
          <div className="mx-2 my-0.5 h-px bg-white/[0.07]" />
          <div className="px-2 pb-1.5 pt-1">
            <button
              onClick={handleTestMic}
              disabled={testing}
              className={`flex items-center gap-1.5 w-full justify-center px-2 py-1.5 rounded font-mono text-[9px] transition-all border ${testing ? 'border-amber-400/20 bg-amber-400/10 text-amber-400' : 'border-white/[0.07] bg-white/[0.03] text-white/40 hover:text-white/70 hover:bg-white/[0.06]'}`}
            >
              {testing ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                  recording… {testCountdown}s
                </>
              ) : (
                <>
                  <svg width="9" height="9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg>
                  test mic (5s)
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
