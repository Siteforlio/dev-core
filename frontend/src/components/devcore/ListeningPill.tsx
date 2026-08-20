import { useEffect, useRef, useState } from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import type { AssessmentMode } from '../../types/devcore'

const MODE_STYLE: Record<
  AssessmentMode | 'standard',
  { pill: string; label: string; dot: string }
> = {
  standard: {
    pill:  'bg-[rgba(9,9,18,0.60)] border-white/[0.07] backdrop-blur-xl',
    label: 'text-violet-400',
    dot:   'bg-violet-400 shadow-[0_0_10px_rgba(167,139,250,0.8)]',
  },
  present: {
    pill:  'bg-[rgba(0,30,28,0.65)] border-teal-400/[0.18] backdrop-blur-xl',
    label: 'text-teal-400',
    dot:   'bg-teal-400 shadow-[0_0_10px_rgba(45,212,191,0.8)]',
  },
  coding: {
    pill:  'bg-[rgba(40,24,0,0.65)] border-amber-400/[0.18] backdrop-blur-xl',
    label: 'text-amber-400',
    dot:   'bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.8)]',
  },
  live: {
    pill:  'bg-[rgba(0,32,18,0.65)] border-emerald-400/[0.18] backdrop-blur-xl',
    label: 'text-emerald-400',
    dot:   'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]',
  },
  ai_model: {
    pill:  'bg-[rgba(10,0,45,0.65)] border-sky-400/[0.18] backdrop-blur-xl',
    label: 'text-sky-400',
    dot:   'bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.8)]',
  },
}

const BAR_COUNT = 6
const MIN_H = 2
const MAX_H = 18
const BIN_PICKS = [2, 5, 9, 14, 20, 28]

function useAudioBars(active: boolean) {
  const [bars, setBars] = useState<number[]>(Array(BAR_COUNT).fill(MIN_H))
  const rafRef     = useRef<number | null>(null)
  const ctxRef     = useRef<AudioContext | null>(null)
  const streamRef  = useRef<MediaStream | null>(null)

  useEffect(() => {
    if (!active) {
      rafRef.current && cancelAnimationFrame(rafRef.current)
      streamRef.current?.getTracks().forEach(t => t.stop())
      ctxRef.current?.close()
      rafRef.current = ctxRef.current = streamRef.current = null
      setBars(Array(BAR_COUNT).fill(MIN_H))
      return
    }

    let alive = true

    async function start() {
      try {
        // No device ID — always use default mic, avoids naudiodon integer vs browser string ID mismatch
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        if (!alive) { stream.getTracks().forEach(t => t.stop()); return }

        streamRef.current = stream
        const ctx = new AudioContext()
        ctxRef.current = ctx
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 128
        analyser.smoothingTimeConstant = 0.6
        ctx.createMediaStreamSource(stream).connect(analyser)

        const data = new Uint8Array(analyser.frequencyBinCount)
        function tick() {
          if (!alive) return
          analyser.getByteFrequencyData(data)
          setBars(BIN_PICKS.map(idx => {
            const raw = data[Math.min(idx, data.length - 1)] / 255
            return Math.round(MIN_H + raw * (MAX_H - MIN_H))
          }))
          rafRef.current = requestAnimationFrame(tick)
        }
        tick()
      } catch (e) {
        console.warn('[bars] getUserMedia failed:', e)
        setBars(Array(BAR_COUNT).fill(MIN_H))
      }
    }

    start()
    return () => {
      alive = false
      rafRef.current && cancelAnimationFrame(rafRef.current)
      streamRef.current?.getTracks().forEach(t => t.stop())
      ctxRef.current?.close()
      rafRef.current = ctxRef.current = streamRef.current = null
    }
  }, [active])

  return bars
}

export function ListeningPill() {
  const { state, assessmentMode, sessionId } = useOverlayStore()

  // Connecting = session was started but WS hasn't confirmed listening yet
  const isConnecting   = !!sessionId && state === 'idle'
  const isActive       = state !== 'idle'
  const isThinking     = state === 'thinking'
  const isReconnecting = state === 'reconnecting'
  const isListening    = isActive && !isThinking && !isReconnecting

  const bars = useAudioBars(isListening)

  const modeKey = assessmentMode ?? 'standard'
  const style   = MODE_STYLE[modeKey]

  const modeLabel: Record<string, string> = {
    present:  'PRESENT',
    coding:   'CODING',
    live:     'LIVE',
    ai_model: 'AI MODEL',
  }

  return (
    <div className={`flex items-center gap-3 px-6 py-2.5 rounded-full border shadow-lg ${style.pill}`}>
      <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
        isConnecting   ? 'bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.8)]'
        : isReconnecting ? 'bg-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.8)]'
        : isActive     ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]'
                       : style.dot
      } animate-pulse`} />

      <span className={`font-orbitron text-[14px] font-bold tracking-[0.18em] ${style.label}`}>
        DEVCORE{assessmentMode ? ` · ${modeLabel[assessmentMode]}` : ''}
      </span>
      <div className="w-px h-5 bg-white/[0.07]" />

      {isConnecting ? (
        <span className="font-mono text-[12px] text-cyan-400 tracking-wider">loading…</span>
      ) : isReconnecting ? (
        <span className="font-mono text-[12px] text-yellow-400 tracking-wider">reconnecting…</span>
      ) : isThinking ? (
        <span className="font-mono text-[12px] text-amber-400 tracking-wider">thinking...</span>
      ) : isActive ? (
        <div className="flex items-end gap-[3px] h-5">
          {bars.map((h, i) => (
            <span
              key={i}
              className="w-[3px] bg-emerald-400 rounded-sm shadow-[0_0_4px_rgba(52,211,153,0.8)] transition-all duration-75"
              style={{ height: h }}
            />
          ))}
        </div>
      ) : (
        <span className="font-mono text-[12px] text-white/30 tracking-wider">idle</span>
      )}

      <span className="font-mono text-[12px] text-white/40 tracking-wider ml-1">
        {isConnecting ? 'starting session…' : isReconnecting ? 'reconnecting...' : isActive ? 'listening...' : 'Ctrl+Shift+Enter to start'}
      </span>
    </div>
  )
}
