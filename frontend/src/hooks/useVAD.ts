import { useEffect, useRef, useCallback } from 'react'
import { apiFetch } from '../lib/apiFetch'

const API = 'http://localhost:8000/api/v1'

// VAD outputs Float32 audio at 16 kHz mono
const VAD_SAMPLE_RATE = 16_000

interface VADOptions {
  /** When true, VAD is paused and no speech events fire. */
  muted: boolean
  /** Called the instant speech is detected — use to interrupt TTS. */
  onSpeechStart?: () => void
  /** Called with the Deepgram transcript once a speech segment ends. */
  onTranscript: (text: string) => void
  languagePref?: string
}

/** Convert a Float32Array (16 kHz mono) to a WAV Blob for the transcribe endpoint. */
function float32ToWav(samples: Float32Array, sampleRate: number): Blob {
  const byteCount = samples.length * 2
  const buffer = new ArrayBuffer(44 + byteCount)
  const view = new DataView(buffer)

  const str = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i))
  }

  str(0, 'RIFF')
  view.setUint32(4, 36 + byteCount, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  view.setUint32(16, 16, true)       // chunk size
  view.setUint16(20, 1, true)        // PCM
  view.setUint16(22, 1, true)        // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true)        // block align
  view.setUint16(34, 16, true)       // bits per sample
  str(36, 'data')
  view.setUint32(40, byteCount, true)

  const pcm = new Int16Array(buffer, 44)
  for (let i = 0; i < samples.length; i++) {
    pcm[i] = Math.max(-32_768, Math.min(32_767, Math.round(samples[i] * 32_768)))
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

/**
 * Always-on voice activity detection using @ricky0123/vad-web (Silero VAD).
 *
 * Behaviour:
 *  - When `muted` is false: continuously listens on `micStream`, fires
 *    onSpeechStart() the moment speech is detected, then sends the captured
 *    audio to POST /speech/transcribe and calls onTranscript() with the result.
 *  - When `muted` is true: VAD is paused — no callbacks fire.
 *
 * The hook manages VAD lifecycle (init, start, pause, destroy) automatically.
 * @ricky0123/vad-web requires vad.worklet.js and silero_vad.onnx to be
 * served from the public root (copy from node_modules/@ricky0123/vad-web/dist/).
 */
export function useVAD(micStream: MediaStream | null, opts: VADOptions) {
  // Keep latest opts in a ref so callbacks never capture stale closures
  const optsRef = useRef(opts)
  optsRef.current = opts

  const vadRef = useRef<{ start: () => void; pause: () => void; destroy: () => void } | null>(null)
  const initialisedRef = useRef(false)

  const sendToTranscribe = useCallback(async (audio: Float32Array) => {
    try {
      const wav = float32ToWav(audio, VAD_SAMPLE_RATE)
      const form = new FormData()
      form.append('audio', wav, 'speech.wav')
      form.append('language', optsRef.current.languagePref ?? 'en')
      const res = await apiFetch(`${API}/speech/transcribe`, { method: 'POST', body: form })
      const body = await res.json()
      const transcript: string = body.data?.transcript ?? ''
      if (transcript.trim()) {
        optsRef.current.onTranscript(transcript)
      }
    } catch {
      // Transcription failure is non-critical — user can type instead
    }
  }, [])

  // Initialise VAD once when micStream becomes available
  useEffect(() => {
    if (!micStream || initialisedRef.current) return
    initialisedRef.current = true

    let cancelled = false

    async function init() {
      try {
        const { MicVAD } = await import('@ricky0123/vad-web')
        if (cancelled) return

        const vad = await MicVAD.new({
          stream: micStream!,
          onSpeechStart: () => optsRef.current.onSpeechStart?.(),
          onSpeechEnd: (audio: Float32Array) => sendToTranscribe(audio),
          workletURL: '/vad.worklet.js',
          modelURL: '/silero_vad.onnx',
        })

        if (cancelled) {
          vad.destroy()
          return
        }

        vadRef.current = vad
        if (!optsRef.current.muted) vad.start()
      } catch (err) {
        // VAD failed to load (e.g. assets not in /public) — muted mode still works
        console.warn('[useVAD] init failed:', err)
      }
    }

    init()

    return () => {
      cancelled = true
    }
  }, [micStream, sendToTranscribe])

  // Respond to muted toggle without re-initialising
  useEffect(() => {
    if (!vadRef.current) return
    if (opts.muted) {
      vadRef.current.pause()
    } else {
      vadRef.current.start()
    }
  }, [opts.muted])

  // Destroy on unmount
  useEffect(() => {
    return () => {
      vadRef.current?.destroy()
      vadRef.current = null
      initialisedRef.current = false
    }
  }, [])
}
