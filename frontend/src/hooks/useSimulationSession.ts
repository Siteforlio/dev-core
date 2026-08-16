import { useEffect, useRef, useState, useCallback } from 'react'
import { useSimulationStore } from '../store/simulationStore'
import { useAuthStore } from '../store/authStore'
import { apiFetch } from '../lib/apiFetch'
import { WS_BASE } from '../lib/apiBase'

export interface SimTurn {
  id: string
  speaker: 'user' | 'ai'
  text: string
  toolEvents?: SimToolEvent[]
}

export interface SimToolEvent {
  tool: string
  command: string
  output: string
  status: 'running' | 'done'
}

export interface SimDebriefData {
  overall_score: number
  hire_signal: string
  core_scores: Record<string, number>
  scenario_scores: Record<string, number>
  summary: string
  strengths: string[]
  improvements: string[]
  focus_areas: string[]
}

interface MicOptions {
  micMuted: boolean
  selectedMicId: string | undefined
  selectedSpeakerId: string | undefined
}

interface UseSimulationSessionReturn {
  turns: SimTurn[]
  remaining: number | null
  hardCutoff: boolean
  cutoffMsg: string
  sessionEnded: boolean
  aiThinking: boolean
  aiSpeaking: boolean
  activeTool: SimToolEvent | null
  wsReady: boolean
  isRecording: boolean
  sendText: (content: string) => void
  endSession: () => void
}

export function useSimulationSession(
  onDebrief: (data: SimDebriefData) => void,
  onEnd: () => void,
  micOptions: MicOptions,
): UseSimulationSessionReturn {
  const { activeSimSessionId, timeBudgetSeconds } = useSimulationStore()
  const token = useAuthStore((s) => s.accessToken)

  const { micMuted, selectedMicId, selectedSpeakerId } = micOptions

  const [turns, setTurns] = useState<SimTurn[]>([])
  const [remaining, setRemaining] = useState<number | null>(timeBudgetSeconds)
  const [hardCutoff, setHardCutoff] = useState(false)
  const [cutoffMsg, setCutoffMsg] = useState('')
  const [sessionEnded, setSessionEnded] = useState(false)
  const [aiThinking, setAiThinking] = useState(false)
  const [aiSpeaking, setAiSpeaking] = useState(false)
  const [activeTool, setActiveTool] = useState<SimToolEvent | null>(null)
  const [wsReady, setWsReady] = useState(false)
  const [isRecording, setIsRecording] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const audioQueueRef = useRef<ArrayBuffer[]>([])
  const audioPlayingRef = useRef(false)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const micStreamRef = useRef<MediaStream | null>(null)

  // ── Audio playback ──────────────────────────────────────────────────────────

  const playNextChunk = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      audioPlayingRef.current = false
      setAiSpeaking(false)
      return
    }
    const buf = audioQueueRef.current.shift()!
    if (!audioCtxRef.current) audioCtxRef.current = new AudioContext()
    const ctx = audioCtxRef.current
    const play = () => {
      ctx.decodeAudioData(buf.slice(0)).then((decoded) => {
        const src = ctx.createBufferSource()
        src.buffer = decoded
        src.connect(ctx.destination)
        src.onended = playNextChunk
        src.start()
      }).catch(playNextChunk)
    }
    if (ctx.state === 'suspended') {
      ctx.resume().then(play).catch(playNextChunk)
    } else {
      play()
    }
  }, [])

  // Change speaker output device when selection changes
  useEffect(() => {
    if (!audioCtxRef.current || !selectedSpeakerId) return
    const ctx = audioCtxRef.current
    if ('setSinkId' in ctx) {
      (ctx as AudioContext & { setSinkId: (id: string) => Promise<void> })
        .setSinkId(selectedSpeakerId)
        .catch(() => {})
    }
  }, [selectedSpeakerId])

  // ── WebSocket ───────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!activeSimSessionId || !token) return

    const wsUrl = `${WS_BASE()}/sim-sessions/${activeSimSessionId}/ws?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      // Connected — waiting for AI opening message
    }

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data) as Record<string, unknown>

      if (msg.type === 'thinking') {
        setAiThinking(msg.active as boolean)
        if (msg.active) setAiSpeaking(false)
      }

      if (msg.type === 'transcript' && msg.final) {
        setAiThinking(false)
        const turn: SimTurn = {
          id: `${msg.speaker}-${Date.now()}`,
          speaker: msg.speaker as 'user' | 'ai',
          text: msg.text as string,
        }
        setTurns((prev) => [...prev, turn])
        // Mark session ready after the first AI turn (opening message)
        if (msg.speaker === 'ai') setWsReady(true)
      }

      if (msg.type === 'timer_update') {
        setRemaining(msg.remaining_seconds as number)
      }

      if (msg.type === 'hard_cutoff') {
        setHardCutoff(true)
        setCutoffMsg(msg.message as string)
      }

      if (msg.type === 'tool_event') {
        const event: SimToolEvent = {
          tool: msg.tool as string,
          command: (msg.command as string) || '',
          output: (msg.output as string) || '',
          status: msg.status as 'running' | 'done',
        }
        if (event.status === 'running') {
          setActiveTool(event)
        } else {
          setActiveTool((prev) => prev ? { ...prev, output: event.output, status: 'done' } : null)
          setTimeout(() => setActiveTool(null), 3000)
        }
        setTurns((prev) => {
          const last = prev[prev.length - 1]
          if (!last) return prev
          return [...prev.slice(0, -1), { ...last, toolEvents: [...(last.toolEvents || []), event] }]
        })
      }

      if (msg.type === 'session_end') {
        setSessionEnded(true)
        apiFetch(`/api/v1/sim-sessions/${activeSimSessionId}/debrief`, { method: 'POST' })
          .then((r) => r.json())
          .then((j: { data: SimDebriefData | null }) => { if (j.data) onDebrief(j.data) })
          .catch(() => {})
      }

      if (msg.type === 'ai_audio') {
        const bytes = Uint8Array.from(atob(msg.data as string), (c) => c.charCodeAt(0))
        audioQueueRef.current.push(bytes.buffer)
        setAiSpeaking(true)
        if (!audioPlayingRef.current) {
          audioPlayingRef.current = true
          playNextChunk()
        }
      }
    }

    ws.onerror = () => {}
    ws.onclose = () => {}
    return () => { ws.close() }
  }, [activeSimSessionId, token, onDebrief, playNextChunk])

  // ── Mic recording ───────────────────────────────────────────────────────────

  useEffect(() => {
    if (micMuted || sessionEnded) {
      // Stop recorder and flush accumulated audio to backend
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop()
      }
      return
    }

    // Start mic recording
    const constraints: MediaStreamConstraints = {
      audio: selectedMicId ? { deviceId: { exact: selectedMicId } } : true,
    }

    navigator.mediaDevices.getUserMedia(constraints).then((stream) => {
      micStreamRef.current = stream
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      recorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size < 10 || wsRef.current?.readyState !== WebSocket.OPEN) return
        const reader = new FileReader()
        reader.onload = () => {
          const b64 = (reader.result as string).split(',')[1]
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'audio_chunk', data: b64 }))
          }
        }
        reader.readAsDataURL(e.data)
      }

      recorder.onstop = () => {
        setIsRecording(false)
        stream.getTracks().forEach((t) => t.stop())
        micStreamRef.current = null
        // Send flush to trigger transcription
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'audio_flush' }))
        }
      }

      recorder.start(500) // 500ms timeslice chunks
      setIsRecording(true)
    }).catch(() => {})

    return () => {
      recorderRef.current?.stop()
      micStreamRef.current?.getTracks().forEach((t) => t.stop())
      micStreamRef.current = null
    }
  }, [micMuted, selectedMicId, sessionEnded])

  // ── Actions ─────────────────────────────────────────────────────────────────

  const sendText = useCallback((content: string) => {
    if (!content.trim() || !wsRef.current || sessionEnded || hardCutoff) return
    wsRef.current.send(JSON.stringify({ type: 'text_turn', content: content.trim(), elapsed_seconds: 0 }))
  }, [sessionEnded, hardCutoff])

  const endSession = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: 'end_session' }))
    onEnd()
  }, [onEnd])

  return {
    turns, remaining, hardCutoff, cutoffMsg,
    sessionEnded, aiThinking, aiSpeaking, activeTool,
    wsReady, isRecording,
    sendText, endSession,
  }
}
