import React, { useState, useEffect, useRef } from 'react'
import { useOverlayStore, type AudioDevice } from '../../store/overlayStore'

export function AudioSourcePicker() {
  const { micDeviceId, setMicDeviceId, sysDeviceId, setSysDeviceId, setAudioSource } = useOverlayStore()
  const [open, setOpen]     = useState(false)
  const [mics, setMics]     = useState<AudioDevice[]>([])
  const [loops, setLoops]   = useState<AudioDevice[]>([])
  const [testing, setTesting]       = useState(false)
  const [testCountdown, setTestCountdown] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => { setAudioSource('both') }, [])

  // Fetch devices on mount and whenever dropdown opens
  useEffect(() => {
    const api = (window as any).electronAPI?.devcore
    api?.listDevices?.().then((result: { mics: AudioDevice[]; systems: AudioDevice[] }) => {
      if (!result) return
      const availMics  = result.mics    ?? []
      const availLoops = result.systems ?? []
      setMics(availMics)
      setLoops(availLoops)
      if (micDeviceId === null && availMics.length > 0)   setMicDeviceId(availMics[0].id)
      if (sysDeviceId === null && availLoops.length > 0)  setSysDeviceId(availLoops[0].id)
    })
  }, [open])

  // Hot-plug: update list live
  useEffect(() => {
    const api = (window as any).electronAPI?.devcore
    const remove = api?.onDevicesChanged?.((result: { mics: AudioDevice[]; systems: AudioDevice[] }) => {
      const availMics  = result.mics    ?? []
      const availLoops = result.systems ?? []
      setMics(availMics)
      setLoops(availLoops)
      const cur = useOverlayStore.getState()
      if (cur.micDeviceId === null || !availMics.some(m => m.id === cur.micDeviceId))
        setMicDeviceId(availMics.length > 0 ? availMics[0].id : null)
      if (cur.sysDeviceId === null || !availLoops.some(s => s.id === cur.sysDeviceId))
        setSysDeviceId(availLoops.length > 0 ? availLoops[0].id : null)
    })
    return () => remove?.()
  }, [])

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

  const selectedMic  = mics.find(m => m.id === micDeviceId)
  const selectedLoop = loops.find(s => s.id === sysDeviceId)

  function truncate(name: string, max = 18) {
    return name.length > max ? name.slice(0, max) + '…' : name
  }

  const micLabel  = selectedMic  ? truncate(selectedMic.name)  : 'Microphone'
  const loopLabel = selectedLoop ? truncate(selectedLoop.name) : loops.length === 0 ? 'No loopback' : 'System audio'

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-2 py-1 rounded-md border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.055] transition-all"
      >
        {/* Mic icon */}
        <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/50">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="22"/>
        </svg>
        <span className="font-mono text-[9px] text-white/60 whitespace-nowrap">{micLabel}</span>

        <span className="font-mono text-[9px] text-white/20 mx-0.5">·</span>

        {/* Speaker icon */}
        <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/50">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
          <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
        </svg>
        <span className="font-mono text-[9px] text-white/60 whitespace-nowrap">{loopLabel}</span>

        <svg width="9" height="9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/30 ml-0.5">
          <path d="m6 9 6 6 6-6"/>
        </svg>
      </button>

      {open && (
        <div className="absolute top-full mt-1 right-0 bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-lg shadow-xl z-50 w-[220px] flex flex-col" style={{ maxHeight: 'min(60vh, 320px)' }}>

          {/* ── Scrollable device lists ── */}
          <div className="overflow-y-auto flex-1 min-h-0">

            {/* Mic section */}
            <div className="px-2 pt-1.5 pb-1">
              <p className="font-mono text-[7px] uppercase tracking-widest text-white/25 mb-0.5">Microphone</p>
              {mics.length === 0 && (
                <p className="font-mono text-[9px] text-white/30 px-1.5 py-1">No microphones found</p>
              )}
              {mics.map(m => (
                <button
                  key={m.id}
                  onClick={() => setMicDeviceId(m.id)}
                  className={`flex items-center gap-1.5 w-full text-left px-1.5 py-1 rounded font-mono text-[9px] transition-all ${micDeviceId === m.id ? 'text-emerald-400 bg-emerald-400/10' : 'text-white/50 hover:bg-white/5'}`}
                  title={m.name}
                >
                  <span className={`w-1 h-1 rounded-full flex-shrink-0 ${micDeviceId === m.id ? 'bg-emerald-400' : 'bg-white/20'}`} />
                  <span className="truncate">{m.name}</span>
                </button>
              ))}
            </div>

            <div className="mx-2 my-0.5 h-px bg-white/[0.07]" />

            {/* System audio (loopback) section */}
            <div className="px-2 pt-1 pb-1">
              <p className="font-mono text-[7px] uppercase tracking-widest text-white/25 mb-0.5">System audio</p>
              {loops.length === 0 ? (
                <p className="font-mono text-[9px] text-white/20 px-1.5 py-1 leading-relaxed">
                  No loopback found.<br/>
                  Enable Stereo Mix in Sound settings.
                </p>
              ) : (
                loops.map(s => (
                  <button
                    key={s.id}
                    onClick={() => setSysDeviceId(s.id)}
                    className={`flex items-center gap-1.5 w-full text-left px-1.5 py-1 rounded font-mono text-[9px] transition-all ${sysDeviceId === s.id ? 'text-sky-400 bg-sky-400/10' : 'text-white/50 hover:bg-white/5'}`}
                    title={s.name}
                  >
                    <span className={`w-1 h-1 rounded-full flex-shrink-0 ${sysDeviceId === s.id ? 'bg-sky-400' : 'bg-white/20'}`} />
                    <span className="truncate">{s.name}</span>
                  </button>
                ))
              )}
            </div>

          </div>

          {/* ── Test mic — pinned to bottom ── */}
          <div className="mx-2 h-px bg-white/[0.07]" />
          <div className="px-2 pb-1.5 pt-1 flex-shrink-0">
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
                  <svg width="9" height="9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  </svg>
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
