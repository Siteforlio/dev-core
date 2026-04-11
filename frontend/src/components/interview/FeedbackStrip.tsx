import { useEffect, useRef, useState } from 'react'

interface EmotionState {
  emotion: string
  eye_contact: boolean
  confidence: number
}

const EMOTION_COLOR: Record<string, string> = {
  confident: 'text-green-400',
  engaged: 'text-blue-400',
  neutral: 'text-gray-400',
  uncertain: 'text-yellow-400',
  nervous: 'text-red-400',
}

interface Props {
  active: boolean
}

export default function FeedbackStrip({ active }: Props) {
  const [enabled, setEnabled] = useState(false)
  const [state, setState] = useState<EmotionState>({ emotion: 'neutral', eye_contact: false, confidence: 0.5 })
  const [cameraError, setCameraError] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    if (!active || !enabled) return

    const startCamera = async () => {
      try {
        // Prefer built-in/USB camera, avoid phone cameras
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 320, height: 240, facingMode: 'user' },
        })
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
        setCameraError(false)
      } catch {
        setCameraError(true)
      }
    }

    startCamera()

    const capture = async () => {
      if (!mountedRef.current || !videoRef.current || !streamRef.current) return
      const canvas = document.createElement('canvas')
      canvas.width = 320
      canvas.height = 240
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.drawImage(videoRef.current, 0, 0, 320, 240)
      const frame_b64 = canvas.toDataURL('image/jpeg', 0.6).split(',')[1]
      try {
        const res = await fetch('/api/v1/emotion/analyze-frame', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ frame_b64 }),
        })
        if (res.ok && mountedRef.current) {
          const json = await res.json()
          setState(json.data)
        }
      } catch {
        // network error — keep last state
      }
    }

    intervalRef.current = setInterval(capture, 2000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [active, enabled])

  const confidencePct = Math.round(state.confidence * 100)

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-gray-900 border-t border-gray-800 text-xs shrink-0">
      <video ref={videoRef} autoPlay muted playsInline className="hidden" />

      {!enabled ? (
        <button
          onClick={() => setEnabled(true)}
          className="text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-1.5"
        >
          <span className="w-2 h-2 rounded-full bg-gray-700 inline-block" />
          Enable emotion tracking
        </button>
      ) : cameraError ? (
        <span className="text-gray-600">Camera unavailable</span>
      ) : (
        <>
          <span className={`capitalize font-medium ${EMOTION_COLOR[state.emotion] ?? 'text-gray-400'}`}>
            {state.emotion}
          </span>

          <div className="flex items-center gap-2 flex-1 max-w-32">
            <span className="text-gray-500 shrink-0">Confidence</span>
            <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-700"
                style={{ width: `${confidencePct}%` }}
              />
            </div>
            <span className="text-gray-400 shrink-0 w-8 text-right">{confidencePct}%</span>
          </div>

          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${state.eye_contact ? 'bg-green-500' : 'bg-gray-600'}`} />
            <span className="text-gray-500">Eye contact</span>
          </div>

          <button
            onClick={() => {
              setEnabled(false)
              streamRef.current?.getTracks().forEach((t) => t.stop())
            }}
            className="text-gray-600 hover:text-gray-400 ml-auto"
          >
            ✕
          </button>
        </>
      )}
    </div>
  )
}
