import { useEffect, useRef, useState } from 'react'

export interface EmotionState {
  emotion: string
  eye_contact: boolean
  confidence: number
  nervousness_score?: number
  gaze_direction?: string
}

interface Props {
  active: boolean
  /** Controlled by parent — true = analysis running */
  enabled: boolean
  /** Pass the user's display camera stream to avoid opening a second camera */
  sharedStream: MediaStream | null
  /** Called with new emotion data every ~2s, or null when disabled */
  onEmotionChange: (state: EmotionState | null) => void
}

/**
 * Headless component: captures video frames and calls /api/v1/emotion/analyze-frame.
 * Renders only a hidden <video> element. All UI is handled by the parent.
 */
export default function FeedbackStrip({ active, enabled, sharedStream, onEmotionChange }: Props) {
  const [, setCameraError] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const ownStreamRef = useRef<MediaStream | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)
  const onEmotionRef = useRef(onEmotionChange)

  useEffect(() => {
    onEmotionRef.current = onEmotionChange
  }, [onEmotionChange])

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)

    if (!active || !enabled) {
      ownStreamRef.current?.getTracks().forEach((t) => t.stop())
      ownStreamRef.current = null
      if (videoRef.current) videoRef.current.srcObject = null
      onEmotionRef.current(null)
      return
    }

    const setup = async () => {
      try {
        if (sharedStream) {
          // Reuse the display camera stream — no extra getUserMedia call
          if (videoRef.current) videoRef.current.srcObject = sharedStream
        } else {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 320, height: 240, facingMode: 'user' },
          })
          ownStreamRef.current = stream
          if (videoRef.current) videoRef.current.srcObject = stream
        }
        setCameraError(false)
      } catch {
        setCameraError(true)
        return
      }

      const capture = async () => {
        if (!mountedRef.current || !videoRef.current) return
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
            onEmotionRef.current(json.data)
          }
        } catch {
          // network error — keep last state
        }
      }

      intervalRef.current = setInterval(capture, 2000)
    }

    setup()

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      // Only stop own stream — never stop a shared stream we don't own
      ownStreamRef.current?.getTracks().forEach((t) => t.stop())
      ownStreamRef.current = null
      if (videoRef.current && !sharedStream) videoRef.current.srcObject = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, enabled, sharedStream])

  return <video ref={videoRef} autoPlay muted playsInline style={{ display: 'none' }} />
}
