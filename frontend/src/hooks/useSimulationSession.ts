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

export interface SimAnswerEval {
  answer_quality: string
  score: number
  what_worked: string
  gap: string
  follow_up_needed: boolean
  topic_drift: boolean
  inconsistency: boolean
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
  lastEval: SimAnswerEval | null
  interimTranscript: string
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
  const [lastEval, setLastEval] = useState<SimAnswerEval | null>(null)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [statusMessage, setStatusMessage] = useState('')

  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const audioQueueRef = useRef<ArrayBuffer[]>([])
  const audioPlayingRef = useRef(false)
  const captureProcRef = useRef<ScriptProcessorNode | null>(null)
  const captureCtxRef  = useRef<AudioContext | null>(null)
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

      if (msg.type === 'status') {
        setStatusMessage(msg.message as string)
      }

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
        if (msg.speaker === 'user') setInterimTranscript('')
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

      if (msg.type === 'transcript_interim') {
        setInterimTranscript(msg.text as string)
      }

      if (msg.type === 'answer_eval') {
        setLastEval(msg.data as SimAnswerEval)
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
      // Disconnect ScriptProcessor → send flush
      if (captureProcRef.current) {
        captureProcRef.current.disconnect()
        captureProcRef.current = null
      }
      if (captureCtxRef.current) {
        captureCtxRef.current.close()
        captureCtxRef.current = null
      }
      micStreamRef.current?.getTracks().forEach((t) => t.stop())
      micStreamRef.current = null
      setIsRecording(false)
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'audio_flush' }))
      }
      return
    }

    // Start mic recording — capture raw PCM Int16 at 16 kHz (WAV-compatible)
    const constraints: MediaStreamConstraints = {
      audio: selectedMicId ? { deviceId: { exact: selectedMicId } } : true,
    }

    navigator.mediaDevices.getUserMedia(constraints).then((stream) => {
      micStreamRef.current = stream

      // Use native sample rate; ScriptProcessor downsamples automatically if browser supports it
      const ctx = new AudioContext({ sampleRate: 16000 })
      captureCtxRef.current = ctx

      const source = ctx.createMediaStreamSource(stream)
      // 4096-sample buffer ≈ 256 ms at 16 kHz — sent as one audio_chunk per callback
      const proc = ctx.createScriptProcessor(4096, 1, 1)
      captureProcRef.current = proc

      proc.onaudioprocess = (e: AudioProcessingEvent) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return
        const float32 = e.inputBuffer.getChannelData(0)
        // Float32 → Int16 LE PCM
        const int16 = new Int16Array(float32.length)
        for (let i = 0; i < float32.length; i++) {
          int16[i] = Math.max(-32768, Math.min(32767, Math.round(float32[i] * 32768)))
        }
        // Safe base64 encoding for binary data
        const bytes = new Uint8Array(int16.buffer)
        let binary = ''
        for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
        const b64 = btoa(binary)
        wsRef.current!.send(JSON.stringify({ type: 'audio_chunk', data: b64 }))
      }

      source.connect(proc)
      proc.connect(ctx.destination)
      setIsRecording(true)
    }).catch(() => {})

    return () => {
      captureProcRef.current?.disconnect()
      captureProcRef.current = null
      captureCtxRef.current?.close()
      captureCtxRef.current = null
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
    wsReady, isRecording, lastEval, interimTranscript, statusMessage,
    sendText, endSession,
  }
}
