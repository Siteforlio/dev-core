import { useRef, useState, useCallback, useEffect } from 'react'
import { WS_BASE } from '../lib/apiBase'

interface TTSMeta {
  sampleRate: number
  channels: number
}

/**
 * Manages a WebSocket connection to the Kokoro TTS endpoint and plays
 * streamed PCM int16 audio via the Web Audio API.
 *
 * speak()     — sends text to the server; audio begins as soon as the first
 *               sentence chunk arrives (low latency streaming).
 * interrupt() — cancels server-side synthesis and stops client playback
 *               immediately, so the user can barge in mid-sentence.
 */
export function useTTS(sessionId: string | null, token: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const nextStartTimeRef = useRef<number>(0)
  const metaRef = useRef<TTSMeta>({ sampleRate: 24000, channels: 1 })
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([])
  const [isSpeaking, setIsSpeaking] = useState(false)

  // ── Schedule one incoming PCM int16 chunk into the Web Audio API ──────────
  const scheduleChunk = useCallback((buffer: ArrayBuffer) => {
    const ctx = audioCtxRef.current
    if (!ctx) return

    setIsSpeaking(true)

    // PCM int16 → Float32
    const int16 = new Int16Array(buffer)
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32_768
    }

    const audioBuffer = ctx.createBuffer(
      metaRef.current.channels,
      float32.length,
      metaRef.current.sampleRate,
    )
    audioBuffer.getChannelData(0).set(float32)

    const source = ctx.createBufferSource()
    source.buffer = audioBuffer
    source.connect(ctx.destination)

    // Gapless scheduling: each chunk starts exactly where the previous ended
    const startAt = Math.max(ctx.currentTime, nextStartTimeRef.current)
    source.start(startAt)
    nextStartTimeRef.current = startAt + audioBuffer.duration

    activeSourcesRef.current.push(source)
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source)
      if (activeSourcesRef.current.length === 0) {
        setIsSpeaking(false)
      }
    }
  }, [])

  // ── Open / close WebSocket when sessionId changes ─────────────────────────
  useEffect(() => {
    if (!sessionId) return

    const ws = new WebSocket(`${WS_BASE()}/ws/tts/${sessionId}?token=${encodeURIComponent(token)}`)
    ws.binaryType = 'arraybuffer'

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        scheduleChunk(event.data)
        return
      }
      try {
        const msg = JSON.parse(event.data as string)
        if (msg.type === 'meta') {
          metaRef.current = { sampleRate: msg.sample_rate, channels: msg.channels ?? 1 }
          if (!audioCtxRef.current) {
            audioCtxRef.current = new AudioContext({ sampleRate: msg.sample_rate })
          }
        } else if (msg.type === 'interrupted') {
          setIsSpeaking(false)
        }
        // 'done' — isSpeaking goes false via onended of last source node
      } catch {
        // malformed JSON — ignore
      }
    }

    ws.onclose = () => setIsSpeaking(false)
    wsRef.current = ws

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [sessionId, token, scheduleChunk])

  // ── Public API ─────────────────────────────────────────────────────────────

  const speak = useCallback((text: string, voice?: string) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN || !text.trim()) return
    ws.send(JSON.stringify({ type: 'speak', text, voice }))
  }, [])

  const interrupt = useCallback(() => {
    // Stop all queued audio immediately on the client side
    const ctx = audioCtxRef.current
    if (ctx) {
      activeSourcesRef.current.forEach((s) => {
        try { s.stop() } catch { /* already ended */ }
      })
      activeSourcesRef.current = []
      nextStartTimeRef.current = ctx.currentTime
    }
    setIsSpeaking(false)

    // Tell the server to stop synthesis so no further chunks arrive
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'interrupt' }))
    }
  }, [])

  return { speak, interrupt, isSpeaking }
}
