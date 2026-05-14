import { useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { apiFetch } from '../lib/apiFetch'

const API = 'http://localhost:8000/api/v1'

export function useVoice() {
  const languagePref = useAuthStore((s) => s.languagePref)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const speak = useCallback((text: string) => {
    if (!text || typeof window === 'undefined' || !window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.95
    utterance.pitch = 1.0
    utterance.volume = 1.0
    const voices = window.speechSynthesis.getVoices()
    const enVoice = voices.find(v => v.lang.startsWith('en') && !v.name.includes('Google'))
    if (enVoice) utterance.voice = enVoice
    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)
    window.speechSynthesis.speak(utterance)
  }, [])

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
          const res = await apiFetch(`${API}/speech/transcribe`, {
            method: 'POST',
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
  }, [languagePref])

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel()
    setIsSpeaking(false)
  }, [])

  return { speak, startRecording, stopRecording, stopSpeaking, isSpeaking, isRecording }
}
