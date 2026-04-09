import { useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'

const API = 'http://localhost:8000/api/v1'

export function useVoice() {
  const token = useAuthStore((s) => s.accessToken)
  const languagePref = useAuthStore((s) => s.languagePref)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const currentAudioRef = useRef<HTMLAudioElement | null>(null)

  const speak = useCallback(async (text: string) => {
    try {
      // Stop any currently playing audio
      currentAudioRef.current?.pause()

      const form = new FormData()
      form.append('text', text)
      form.append('language', languagePref)

      const res = await fetch(`${API}/speech/synthesize`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      })
      if (!res.ok) return

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      currentAudioRef.current = audio
      setIsSpeaking(true)
      audio.onended = () => {
        setIsSpeaking(false)
        URL.revokeObjectURL(url)
      }
      audio.onerror = () => setIsSpeaking(false)
      await audio.play()
    } catch {
      setIsSpeaking(false)
    }
  }, [token, languagePref])

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      audioChunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setIsRecording(true)
    } catch {
      // mic permission denied — silent fail, user can still type
    }
  }, [])

  const stopRecording = useCallback((): Promise<string> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current
      if (!recorder || recorder.state === 'inactive') { resolve(''); return }

      recorder.onstop = async () => {
        setIsRecording(false)
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        recorder.stream.getTracks().forEach((t) => t.stop())

        try {
          const form = new FormData()
          form.append('audio', blob, 'recording.webm')
          form.append('language', languagePref)
          const res = await fetch(`${API}/speech/transcribe`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: form,
          })
          const body = await res.json()
          resolve(body.data?.transcript ?? '')
        } catch {
          resolve('')
        }
      }
      recorder.stop()
    })
  }, [token, languagePref])

  const stopSpeaking = useCallback(() => {
    currentAudioRef.current?.pause()
    setIsSpeaking(false)
  }, [])

  return { speak, startRecording, stopRecording, stopSpeaking, isSpeaking, isRecording }
}
