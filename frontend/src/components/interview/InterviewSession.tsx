import { useState, useEffect, useRef } from 'react'
import { API_ROOT } from '../../lib/apiBase'
import { useInterviewStore } from '../../store/interviewStore'
import { useInterviewSession } from '../../hooks/useInterviewSession'
import { useVoice } from '../../hooks/useVoice'
import { useCoach } from '../../hooks/useCoach'
import AvatarPanel from './AvatarPanel'
import FeedbackStrip from './FeedbackStrip'
import type { EmotionState } from './FeedbackStrip'
import DebriefReport from './DebriefReport'
import CodeEditor from './CodeEditor'
import SkillsTaskEditor from './SkillsTaskEditor'
import CoachMode from './CoachMode'
import { pickCharacter } from './InterviewerCharacters'

// ── SVG icon primitives ───────────────────────────────────────────────────────

const _ip = { width: 15, height: 15, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

const IconMic = () => <svg {..._ip}><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
const IconMicOff = () => <svg {..._ip}><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
const IconVideo = () => <svg {..._ip}><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
const IconVideoOff = () => <svg {..._ip}><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 7H1v12h12.5"/><path d="M16 7h2a2 2 0 0 1 2 2v5"/><polygon points="23 7 16 12 23 17 23 7"/></svg>
const IconVolume = () => <svg {..._ip}><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
const IconKeyboard = () => <svg {..._ip}><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M10 13h.01M14 13h.01M18 13h.01M8 17h8"/></svg>
const IconEye = () => <svg {..._ip}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
const IconLightbulb = () => <svg {..._ip}><line x1="9" y1="18" x2="15" y2="18"/><line x1="10" y1="22" x2="14" y2="22"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/></svg>
const IconUser = () => <svg {..._ip}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
const IconSquare = () => <svg {..._ip}><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
const IconClock = () => <svg {..._ip}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
const IconCheck = () => <svg {..._ip}><polyline points="20 6 9 17 4 12"/></svg>
const IconArrowRight = () => <svg {..._ip}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
const IconLoader = () => <svg {..._ip} style={{ animation: 'spin 1s linear infinite' }}><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>

interface Props {
  token: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTime(secs: number): string {
  const m = Math.floor(Math.max(0, secs) / 60)
  const s = Math.floor(Math.max(0, secs) % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

const EMOTION_COLOR: Record<string, string> = {
  confident: '#4ade80',
  engaged:   '#60a5fa',
  neutral:   '#94a3b8',
  uncertain: '#fbbf24',
  nervous:   '#f87171',
}

// ── Shared inline-style primitives ────────────────────────────────────────────

const chip: React.CSSProperties = {
  background: '#1a1d28',
  borderRadius: 20,
  padding: '4px 11px',
  fontSize: 11,
  fontWeight: 500,
  color: '#7c8399',
  border: '1px solid rgba(255,255,255,0.04)',
  fontVariantNumeric: 'tabular-nums',
  whiteSpace: 'nowrap',
}

const ctrlBtn: React.CSSProperties = {
  width: 36, height: 36,
  borderRadius: '50%',
  border: '1px solid rgba(255,255,255,0.15)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: 15,
  cursor: 'pointer',
  background: '#22263a',
  color: '#94a3b8',
  flexShrink: 0,
}

const toggleBtn = (active: boolean, activeColor = 'rgba(99,102,241,0.12)', activeBorder = 'rgba(99,102,241,0.3)', activeText = '#818cf8'): React.CSSProperties => ({
  display: 'flex', alignItems: 'center', gap: 6,
  background: active ? activeColor : '#1a1d28',
  border: `1px solid ${active ? activeBorder : 'rgba(255,255,255,0.07)'}`,
  borderRadius: 8,
  padding: '5px 11px',
  fontSize: 11, fontWeight: 600,
  color: active ? activeText : '#7c8399',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
})

// ── Component ─────────────────────────────────────────────────────────────────

export default function InterviewSession({ token }: Props) {
  const {
    sessionId,
    currentRound,
    company,
    role,
    persona,
    careerTrack,
    level,
    remainingRounds,
    sessionComplete,
    roundFailed,
    advanceRound,
    setRoundFailed,
    completeSession,
    reset,
    setRoundResult,
    nextQuestion,
    setSkillsPhase,
  } = useInterviewStore()

  const { submitAnswer } = useInterviewSession()

  // submitWithText is defined below — forward-declared here so useVoice can reference it
  const submitWithTextRef = useRef<((text: string) => Promise<void>) | null>(null)

  const {
    speak,
    isSpeaking,
    isRecording,
    muted,
    setMuted,
    pendingTranscript,
    confirmTranscript,
    cancelTranscript,
    micStream: voiceMicStream,
    initMic,
    destroyMic,
  } = useVoice({
    sessionId,
    token,
    onTranscriptConfirmed: (text) => submitWithTextRef.current?.(text),
  })

  // ── Coach ─────────────────────────────────────────────────────────────────
  // Note: followUpQuestion is not available here (declared below); the active question
  // is passed via sessionContext when entering coach mode instead.
  const coach = useCoach({
    sessionId,
    question: currentRound?.questions[currentRound?.currentQuestionIndex ?? 0] ?? '',
    roundType: currentRound?.type ?? 'behavioral',
    careerTrack,
    level,
  })

  // ── Answer / flow state ──
  const [answer, setAnswer] = useState('')
  const [codeReaction, setCodeReaction] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<{
    what_worked: string
    what_was_missing: string
    stronger_version: string
    passed: boolean
    roundComplete: boolean
    roundPassed: boolean | null
    followUp: string | null
    evaluation: Record<string, unknown> | null
  } | null>(null)
  const [loading, setLoading] = useState(false)
  const [advancing, setAdvancing] = useState(false)
  const [followUpQuestion, setFollowUpQuestion] = useState<string | null>(null)
  const [isFollowUp, setIsFollowUp] = useState(false)
  const [avatarReaction, setAvatarReaction] = useState<string | null>(null)
  const [timeWarning, setTimeWarning] = useState<'amber' | 'red' | null>(null)

  // ── Video call UI state ──
  const [briefingDone, setBriefingDone] = useState(false)
  const [cameraOn, setCameraOn] = useState(true)
  const [faceAnalysisEnabled, setFaceAnalysisEnabled] = useState(false)
  const [textMode, setTextMode] = useState(false)
  const [emotion, setEmotion] = useState<EmotionState | null>(null)
  const [timerPct, setTimerPct] = useState(0)
  const [timeRemaining, setTimeRemaining] = useState(1800)
  const [showSpeakerMenu, setShowSpeakerMenu] = useState(false)
  const [audioOutputs, setAudioOutputs] = useState<MediaDeviceInfo[]>([])

  // ── Coach mode state ──
  const [coachMode, setCoachMode] = useState(false)
  const coachModeRef = useRef(false)                  // ref mirrors state so the timer closure can read it
  const pausedTimeRemainingRef = useRef(0)            // seconds left when coach mode was entered
  const pausedQuestionElapsedRef = useRef(0)          // seconds spent on current question at pause

  // ── Refs ──
  const prevQuestionRef = useRef('')
  const questionStartTimeRef = useRef<number>(Date.now())
  const rewriteCountRef = useRef(0)
  const prevAnswerLengthRef = useRef(0)
  const roundStartTimeRef = useRef<number>(Date.now())
  const handleSubmitRef = useRef<(() => Promise<void>) | null>(null)
  const userCamRef = useRef<HTMLVideoElement>(null)
  const userStreamRef = useRef<MediaStream | null>(null)

  // ── Derived ──
  const question = currentRound?.questions[currentRound.currentQuestionIndex] ?? ''
  const qIndex = currentRound?.currentQuestionIndex ?? 0
  const totalQuestions = currentRound?.questions.length ?? 0
  const isLeetcode = currentRound?.type === 'leetcode'
  const isSkillsTask = (currentRound?.type === 'skills_task' || currentRound?.type === 'technical') && currentRound?.task != null
  const activeQuestion = followUpQuestion ?? question
  const character = sessionId ? pickCharacter(sessionId, level) : undefined
  const timerColor = timerPct >= 95 ? '#ef4444' : timerPct >= 80 ? '#f59e0b' : 'rgba(255,255,255,0.4)'

  // ── Effects ──

  // Auto-speak question when it changes
  useEffect(() => {
    if (question && question !== prevQuestionRef.current) {
      prevQuestionRef.current = question
      speak(question)
    }
  }, [question]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reset timer + rewrite counter on question change
  useEffect(() => {
    questionStartTimeRef.current = Date.now()
    rewriteCountRef.current = 0
    prevAnswerLengthRef.current = 0
  }, [question])

  // Reset round start time on round change
  useEffect(() => {
    roundStartTimeRef.current = Date.now()
    setTimeWarning(null)
    setTimerPct(0)
  }, [currentRound?.id])

  // Timer tick — updates progress bar + time remaining + warns
  // Frozen while coachModeRef.current is true (coach pauses the clock)
  useEffect(() => {
    const budget = currentRound?.timeBudgetSeconds ?? 1800
    const tick = () => {
      if (coachModeRef.current) return
      const elapsed = (Date.now() - roundStartTimeRef.current) / 1000
      const pct = Math.min((elapsed / budget) * 100, 100)
      setTimerPct(pct)
      setTimeRemaining(Math.max(0, budget - elapsed))
      if (pct >= 100) {
        setTimeWarning('red')
        if (!loading && !feedback && answer.trim()) handleSubmitRef.current?.()
      } else if (pct >= 95) {
        setTimeWarning('red')
      } else if (pct >= 80) {
        setTimeWarning('amber')
      } else {
        setTimeWarning(null)
      }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [currentRound?.id, currentRound?.timeBudgetSeconds]) // eslint-disable-line react-hooks/exhaustive-deps

  // Mic — initialise on mount, destroy on unmount
  useEffect(() => {
    initMic()
    return () => destroyMic()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // User camera stream
  useEffect(() => {
    if (!cameraOn) {
      userStreamRef.current?.getTracks().forEach((t) => t.stop())
      userStreamRef.current = null
      if (userCamRef.current) userCamRef.current.srcObject = null
      return
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'user' } })
      .then((stream) => {
        userStreamRef.current = stream
        if (userCamRef.current) userCamRef.current.srcObject = stream
      })
      .catch(() => setCameraOn(false))
    return () => {
      userStreamRef.current?.getTracks().forEach((t) => t.stop())
      userStreamRef.current = null
    }
  }, [cameraOn])

  // Enumerate audio output devices
  useEffect(() => {
    navigator.mediaDevices
      ?.enumerateDevices()
      .then((d) => setAudioOutputs(d.filter((x) => x.kind === 'audiooutput')))
      .catch(() => {})
  }, [])

  // ── Early returns ──
  if (!currentRound || !sessionId) return null

  if (sessionComplete) return <DebriefReport token={token} onRestart={reset} />

  if (roundFailed) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="text-center max-w-md space-y-4">
          <div style={{ color: '#f87171' }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-red-400">Round Failed</h1>
          <p className="text-gray-400">
            Your score was too low to continue the{' '}
            <span className="capitalize text-white">{currentRound.type}</span> round.
          </p>
          <div className="flex gap-3 justify-center pt-2">
            <button
              className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg font-semibold"
              onClick={() => setRoundFailed(false)}
            >
              Retry Round
            </button>
            <button
              className="bg-gray-700 hover:bg-gray-600 px-6 py-2 rounded-lg font-semibold"
              onClick={completeSession}
            >
              View Debrief
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Pre-session briefing ──
  if (!briefingDone) {
    const budgetMins = Math.round((currentRound.timeBudgetSeconds ?? 1800) / 60)
    const roundLabel = currentRound.type.charAt(0).toUpperCase() + currentRound.type.slice(1)
    return (
      <div style={{
        height: '100vh', background: '#0a0a0d', color: 'white',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 0, fontFamily: 'inherit',
      }}>
        {/* Character preview */}
        {character && (
          <div style={{ width: 100, borderRadius: 12, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)', marginBottom: 32, boxShadow: '0 8px 32px rgba(0,0,0,0.6)' }}>
            <AvatarPanel character={character} isSpeaking={false} />
          </div>
        )}

        {/* Company / role */}
        <div style={{ fontSize: 13, color: '#4a5168', marginBottom: 6, letterSpacing: '0.04em' }}>
          {company} · {role}
        </div>

        {/* Round type */}
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#3b82f6', marginBottom: 28 }}>
          {roundLabel} Interview
        </div>

        {/* Time + encouragement */}
        <div style={{
          background: '#12131a', border: '1px solid #1e2330',
          borderRadius: 14, padding: '28px 36px',
          textAlign: 'center', maxWidth: 400,
          marginBottom: 32,
        }}>
          <div style={{ fontSize: 36, fontWeight: 700, color: '#f1f5f9', marginBottom: 4 }}>
            {budgetMins} min
          </div>
          <div style={{ fontSize: 13, color: '#4a5168', marginBottom: 20 }}>
            allocated for this session
          </div>
          <div style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.7 }}>
            Take a breath. Answer naturally — there are no trick questions,
            just a conversation. You've prepared for this.
          </div>
        </div>

        {/* Join button */}
        <button
          onClick={() => setBriefingDone(true)}
          style={{
            background: '#ffffff', color: '#0f0f13',
            border: 'none', borderRadius: 10,
            padding: '13px 36px', fontSize: 14, fontWeight: 700,
            cursor: 'pointer', letterSpacing: '0.02em',
          }}
        >
          I'm ready — Join Interview
        </button>

        {/* Persona */}
        {persona && (
          <div style={{ marginTop: 20, fontSize: 11, color: '#2a2d3a', fontStyle: 'italic', maxWidth: 340, textAlign: 'center' }}>
            {persona}
          </div>
        )}
      </div>
    )
  }

  // ── Handlers ──

  const handleAnswerChange = (newValue: string) => {
    const dropped = prevAnswerLengthRef.current - newValue.length
    if (dropped >= 40) {
      rewriteCountRef.current += 1
      fetch(`${API_ROOT()}/api/v1/interview-sessions/${sessionId}/behavioral-signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ rewrite_count: rewriteCountRef.current }),
      })
        .then((r) => r.json())
        .then((j) => {
          if (j.data?.reaction) {
            setAvatarReaction(j.data.reaction)
            setTimeout(() => setAvatarReaction(null), 8000)
          }
        })
        .catch(() => {})
    }
    prevAnswerLengthRef.current = newValue.length
    setAnswer(newValue)
  }

  // Core submit — accepts explicit text so both VAD auto-submit and manual
  // textarea submit funnel through the same path (§5.1: no business logic in component)
  const submitWithText = async (text: string) => {
    if (!text.trim()) return
    setLoading(true)
    const timeTakenSeconds = Math.floor((Date.now() - questionStartTimeRef.current) / 1000)
    const currentQuestion = followUpQuestion ?? question

    const result = await submitAnswer(sessionId, currentRound.id, currentQuestion, text, {
      totalQuestions,
      emotionState: emotion?.emotion,
      timeTakenSeconds,
      rewriteCount: rewriteCountRef.current,
      isFollowup: isFollowUp,
    })

    rewriteCountRef.current = 0
    prevAnswerLengthRef.current = 0

    const roundComplete = result.round_complete ?? false
    const roundPassed = result.round_passed ?? null

    setFeedback({
      what_worked: result.what_worked,
      what_was_missing: result.what_was_missing,
      stronger_version: result.stronger_version,
      passed: result.passed,
      roundComplete,
      roundPassed,
      followUp: result.follow_up ?? null,
      evaluation: result.evaluation ?? null,
    })
    setRoundResult(result.passed, {
      what_worked: result.what_worked,
      what_was_missing: result.what_was_missing,
      stronger_version: result.stronger_version,
      passed: result.passed,
    })
    speak(result.what_worked || '')
    setAnswer('')
    setLoading(false)
  }
  submitWithTextRef.current = submitWithText

  // Keyboard submit (text mode) — reads from controlled textarea state
  const handleSubmit = async () => submitWithText(answer)
  handleSubmitRef.current = handleSubmit

  // Phase 1 submission for skills_task
  const handleSkillsTaskSubmit = async (submission: string) => {
    if (!currentRound?.task) return
    setLoading(true)
    const timeTakenSeconds = Math.floor((Date.now() - roundStartTimeRef.current) / 1000)
    const result = await submitAnswer(sessionId!, currentRound.id, currentRound.task.title, submission, {
      totalQuestions: 1,
      emotionState: emotion?.emotion,
      timeTakenSeconds,
      rewriteCount: 0,
      isFollowup: false,
    })
    setRoundResult(result.passed, {
      what_worked: result.what_worked,
      what_was_missing: result.what_was_missing,
      stronger_version: result.stronger_version,
      passed: result.passed,
    })
    if (result.round_complete) {
      setFeedback({
        what_worked: result.what_worked,
        what_was_missing: result.what_was_missing,
        stronger_version: result.stronger_version,
        passed: result.passed,
        roundComplete: true,
        roundPassed: result.round_passed ?? null,
        followUp: null,
        evaluation: result.evaluation ?? null,
      })
      // Stay on task view to show feedback before advancing
    } else if (result.follow_up) {
      // Transition to Phase 2 follow-up interview
      setSkillsPhase('followup', result.follow_up)
      setFollowUpQuestion(result.follow_up)
      setIsFollowUp(true)
      speak(result.follow_up)
    }
    setLoading(false)
  }

  // Mic button toggles mute — when muted, text input is shown instead of VAD
  const handleMic = () => setMuted((m) => !m)

  /** Enter full-screen coach mode: pause timer + open coach with session snapshot. */
  const handleEnterCoach = () => {
    const timeRem = timeRemaining
    pausedTimeRemainingRef.current = timeRem
    pausedQuestionElapsedRef.current = (Date.now() - questionStartTimeRef.current) / 1000
    coachModeRef.current = true
    setCoachMode(true)
    coach.open({
      company,
      role,
      round_type: currentRound?.type ?? 'behavioral',
      level,
      career_track: careerTrack,
      current_question: followUpQuestion ?? question,
      question_number: qIndex + 1,
      total_questions: totalQuestions,
      time_remaining_seconds: Math.round(timeRem),
      last_feedback: feedback
        ? { what_worked: feedback.what_worked, what_was_missing: feedback.what_was_missing }
        : null,
    })
  }

  /** Exit coach mode: resume the frozen timer from where it was paused. */
  const handleReturnFromCoach = () => {
    const budget = currentRound?.timeBudgetSeconds ?? 1800
    // Shift roundStartRef so that elapsed recalculates to (budget - pausedTimeRemaining)
    roundStartTimeRef.current = Date.now() - (budget - pausedTimeRemainingRef.current) * 1000
    // Shift questionStartRef so the per-question elapsed is preserved
    questionStartTimeRef.current = Date.now() - pausedQuestionElapsedRef.current * 1000
    coachModeRef.current = false
    setCoachMode(false)
    coach.close()
  }

  const handleNext = async () => {
    if (!feedback) return
    const { roundComplete, roundPassed, followUp } = feedback
    setFeedback(null)
    setCodeReaction(null)

    if (followUp && !roundComplete) {
      setFollowUpQuestion(followUp)
      setIsFollowUp(true)
      return
    }

    setFollowUpQuestion(null)
    setIsFollowUp(false)

    if (!roundComplete) {
      nextQuestion()
      return
    }

    if (roundPassed === false) {
      setFollowUpQuestion(null)
      setIsFollowUp(false)
      setRoundFailed(true)
      return
    }

    if (remainingRounds.length === 0) {
      setFollowUpQuestion(null)
      setIsFollowUp(false)
      completeSession()
      return
    }

    setAdvancing(true)
    try {
      const res = await fetch(`${API_ROOT()}/api/v1/interview-sessions/${sessionId}/advance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ next_round_type: remainingRounds[0] }),
      })
      if (res.ok) {
        const json = await res.json()
        const d = json.data
        setFollowUpQuestion(null)
        setIsFollowUp(false)
        const nextIsSkillsTask = d.current_round === 'skills_task' || d.current_round === 'technical'
        advanceRound(
          {
            id: d.round_id,
            type: d.current_round,
            questions: d.questions ?? [],
            currentQuestionIndex: 0,
            timeBudgetSeconds: d.time_budget_seconds ?? 1800,
            task: d.task ?? null,
            skillsPhase: nextIsSkillsTask ? 'task' : undefined,
          },
          d.persona,
          remainingRounds.slice(1)
        )
      } else {
        completeSession()
      }
    } catch {
      completeSession()
    } finally {
      setAdvancing(false)
    }
  }

  // ── Controls bar (shared between layouts) ──────────────────────────────────
  const ControlsBar = () => {
    const submitDisabled = loading || advancing || (!feedback && !answer.trim() && !isLeetcode)
    const timerColor2 = timerPct >= 95 ? '#f87171' : timerPct >= 80 ? '#fbbf24' : '#64748b'

    return (
      <div style={{
        height: 62, flexShrink: 0,
        background: '#0b0c11',
        borderTop: '1px solid rgba(255,255,255,0.05)',
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        gap: 12,
      }}>

        {/* ── Left: timer + round label ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flexShrink: 0 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: timerPct >= 95 ? 'rgba(239,68,68,0.1)' : timerPct >= 80 ? 'rgba(245,158,11,0.08)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${timerPct >= 95 ? 'rgba(239,68,68,0.25)' : timerPct >= 80 ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.06)'}`,
            borderRadius: 8, padding: '5px 10px',
            color: timerColor2, fontSize: 12, fontWeight: 600, fontVariantNumeric: 'tabular-nums',
          }}>
            <IconClock />
            {formatTime(timeRemaining)}
          </div>
          <div style={{
            ...chip,
            fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600,
          }}>
            {currentRound.type.charAt(0).toUpperCase() + currentRound.type.slice(1)}
          </div>
        </div>

        {/* ── Center: core action buttons ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>

          {/* Mic toggle */}
          <button
            onClick={handleMic}
            title={muted ? 'Unmute mic' : 'Mute mic'}
            style={{
              ...ctrlBtn,
              background: muted ? 'rgba(239,68,68,0.12)' : isRecording ? 'rgba(34,197,94,0.12)' : 'rgba(255,255,255,0.04)',
              color: muted ? '#f87171' : isRecording ? '#4ade80' : '#64748b',
              border: `1px solid ${muted ? 'rgba(239,68,68,0.3)' : isRecording ? 'rgba(34,197,94,0.25)' : 'rgba(255,255,255,0.07)'}`,
              animation: isRecording && !muted ? 'micPulse 1.4s ease-in-out infinite' : 'none',
              position: 'relative',
            }}
          >
            {muted ? <IconMicOff /> : <IconMic />}
            {isRecording && !muted && (
              <span style={{ position: 'absolute', top: 7, right: 7, width: 5, height: 5, borderRadius: '50%', background: '#ef4444' }} />
            )}
          </button>

          {/* Camera toggle */}
          <button
            onClick={() => setCameraOn((v) => !v)}
            title={cameraOn ? 'Turn camera off' : 'Turn camera on'}
            style={{
              ...ctrlBtn,
              background: cameraOn ? 'rgba(255,255,255,0.04)' : 'rgba(239,68,68,0.1)',
              color: cameraOn ? '#64748b' : '#f87171',
              border: `1px solid ${cameraOn ? 'rgba(255,255,255,0.07)' : 'rgba(239,68,68,0.25)'}`,
            }}
          >
            {cameraOn ? <IconVideo /> : <IconVideoOff />}
          </button>

          {/* Divider */}
          <div style={{ width: 1, height: 22, background: 'rgba(255,255,255,0.06)', margin: '0 4px' }} />

          {/* Coach */}
          <button
            onClick={handleEnterCoach}
            title="Open coach"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              height: 36, padding: '0 14px',
              background: 'rgba(99,102,241,0.12)',
              border: '1px solid rgba(99,102,241,0.3)',
              borderRadius: 8,
              color: '#a5b4fc',
              fontSize: 12, fontWeight: 600,
              cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
            }}
          >
            <IconLightbulb />
            Coach
          </button>

          {/* Submit / Next — primary CTA */}
          <button
            onClick={feedback ? handleNext : handleSubmit}
            disabled={submitDisabled}
            title={feedback ? 'Next question' : 'Submit answer'}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              height: 36, padding: '0 16px',
              background: submitDisabled ? 'rgba(255,255,255,0.04)' : '#ffffff',
              color: submitDisabled ? '#2d3148' : '#0a0a0d',
              border: submitDisabled ? '1px solid rgba(255,255,255,0.06)' : 'none',
              borderRadius: 8,
              fontSize: 12, fontWeight: 700,
              cursor: submitDisabled ? 'not-allowed' : 'pointer',
              flexShrink: 0,
              transition: 'background 0.15s, color 0.15s',
            }}
          >
            {loading || advancing
              ? <><IconLoader /><span>Loading</span></>
              : feedback
              ? <><IconArrowRight /><span>Next</span></>
              : <><IconCheck /><span>Submit</span></>
            }
          </button>

          {/* Divider */}
          <div style={{ width: 1, height: 22, background: 'rgba(255,255,255,0.06)', margin: '0 4px' }} />

          {/* End session */}
          <button
            onClick={reset}
            title="End interview"
            style={{
              ...ctrlBtn,
              background: 'rgba(239,68,68,0.08)',
              color: '#f87171',
              border: '1px solid rgba(239,68,68,0.2)',
            }}
          >
            <IconSquare />
          </button>
        </div>

        {/* ── Right: toggles + speaker ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, position: 'relative' }}>

          {/* Speaker */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowSpeakerMenu((v) => !v)}
              title="Audio output"
              style={{
                ...ctrlBtn,
                background: showSpeakerMenu ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.04)',
                color: showSpeakerMenu ? '#94a3b8' : '#475569',
                border: `1px solid ${showSpeakerMenu ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)'}`,
              }}
            >
              <IconVolume />
            </button>
            {showSpeakerMenu && (
              <div style={{
                position: 'absolute', bottom: 'calc(100% + 8px)', right: 0,
                background: '#13151f', border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 10, padding: '6px 0', minWidth: 230, zIndex: 50,
                boxShadow: '0 8px 32px rgba(0,0,0,0.7)',
              }}>
                <div style={{ padding: '6px 14px 5px', fontSize: 10, color: '#334155', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  Audio Output
                </div>
                {audioOutputs.length === 0 ? (
                  <div style={{ padding: '8px 14px', fontSize: 12, color: '#334155' }}>No devices found</div>
                ) : audioOutputs.map((d) => (
                  <div key={d.deviceId} onClick={() => setShowSpeakerMenu(false)}
                    style={{ padding: '8px 14px', fontSize: 12, color: '#94a3b8', cursor: 'pointer' }}>
                    {d.label || `Speaker ${d.deviceId.slice(0, 8)}`}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Type toggle */}
          <button
            onClick={() => setTextMode((v) => !v)}
            title={textMode ? 'Switch to voice' : 'Switch to text input'}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              height: 36, padding: '0 12px',
              background: textMode ? 'rgba(34,197,94,0.1)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${textMode ? 'rgba(34,197,94,0.25)' : 'rgba(255,255,255,0.06)'}`,
              borderRadius: 8,
              color: textMode ? '#4ade80' : '#475569',
              fontSize: 12, fontWeight: 600,
              cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            <IconKeyboard />
            Type
          </button>

          {/* Face analysis toggle */}
          <button
            onClick={() => setFaceAnalysisEnabled((v) => !v)}
            title={faceAnalysisEnabled ? 'Disable face analysis' : 'Enable face analysis'}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              height: 36, padding: '0 12px',
              background: faceAnalysisEnabled ? 'rgba(99,102,241,0.1)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${faceAnalysisEnabled ? 'rgba(99,102,241,0.25)' : 'rgba(255,255,255,0.06)'}`,
              borderRadius: 8,
              color: faceAnalysisEnabled ? '#818cf8' : '#475569',
              fontSize: 12, fontWeight: 600,
              cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            <IconEye />
            Face
            <span style={{
              width: 5, height: 5, borderRadius: '50%',
              background: faceAnalysisEnabled ? '#818cf8' : '#1e2235',
              flexShrink: 0,
            }} />
          </button>
        </div>

        <style>{`
          @keyframes micPulse {
            0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.35); }
            50%      { box-shadow: 0 0 0 5px rgba(239,68,68,0); }
          }
          @keyframes emotionPulse {
            0%,100% { opacity: 1; }
            50%      { opacity: 0.35; }
          }
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    )
  }

  // ── COACH MODE — full-screen, pauses the interview ───────────────────────
  if (coachMode) {
    return (
      <CoachMode
        messages={coach.messages}
        isStreaming={coach.isStreaming}
        sessionInfo={{
          company,
          role,
          roundType: currentRound.type,
          questionNumber: qIndex + 1,
          totalQuestions,
          timeRemaining: pausedTimeRemainingRef.current,
          currentQuestion: followUpQuestion ?? question,
        }}
        onSend={coach.sendMessage}
        onReturn={handleReturnFromCoach}
      />
    )
  }

  // ── SKILLS TASK LAYOUT (Phase 1) ──────────────────────────────────────────
  if (isSkillsTask && currentRound.skillsPhase === 'task' && currentRound.task) {
    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0f1117', color: 'white', overflow: 'hidden' }}>
        {/* Timer bar */}
        <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', flexShrink: 0 }}>
          <div style={{ height: '100%', width: `${timerPct}%`, background: timerColor, transition: 'width 1s linear, background 0.5s' }} />
        </div>

        {/* Top bar */}
        <div style={{
          height: 44, flexShrink: 0, background: '#0e0f14',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', alignItems: 'center',
          padding: '0 16px', gap: 10,
        }}>
          <span style={{ ...chip, display: 'flex', alignItems: 'center', gap: 5, color: timerPct >= 95 ? '#f87171' : timerPct >= 80 ? '#fbbf24' : '#c4c9d8' }}>
            <IconClock />{formatTime(timeRemaining)}
          </span>
          <span style={{ ...chip, color: '#7c85f0' }}>Skills Assessment</span>
          <div style={{ flex: 1 }} />
          {/* Camera toggle in top bar for enforcement */}
          <button
            onClick={() => setCameraOn((v) => !v)}
            style={{
              ...ctrlBtn,
              background: cameraOn ? '#1a1d28' : 'rgba(239,68,68,0.1)',
              color: cameraOn ? '#94a3b8' : '#f87171',
              border: cameraOn ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(239,68,68,0.2)',
            }}
            title={cameraOn ? 'Camera on' : 'Camera off — required'}
          >
            {cameraOn ? <IconVideo /> : <IconVideoOff />}
          </button>
          {/* User camera pip */}
          {cameraOn && (
            <div style={{ width: 60, height: 44, borderRadius: 6, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)', flexShrink: 0 }}>
              <video ref={userCamRef} autoPlay muted playsInline style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>
          )}
          {character && (
            <div style={{ width: 36, borderRadius: 6, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
              <AvatarPanel character={character} isSpeaking={isSpeaking} />
            </div>
          )}
          <button
            onClick={handleEnterCoach}
            title="Open coach"
            style={toggleBtn(false, 'rgba(99,102,241,0.15)', 'rgba(99,102,241,0.35)', '#a5b4fc')}
          >
            <IconLightbulb />
            <span>Coach</span>
          </button>
          <button onClick={reset} title="End interview" style={{ ...ctrlBtn, background: 'rgba(239,68,68,0.08)', color: '#f87171', border: '1px solid rgba(239,68,68,0.12)' }}><IconSquare /></button>
        </div>

        {/* Task editor — fills remaining height */}
        <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
          {!feedback ? (
            <SkillsTaskEditor
              task={currentRound.task}
              sessionId={sessionId!}
              roundId={currentRound.id}
              cameraOn={cameraOn}
              onSubmit={handleSkillsTaskSubmit}
              disabled={loading}
            />
          ) : (
            // Phase 1 round-complete feedback (edge case)
            <div style={{ padding: 32, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 600 }}>
              <div style={{ background: feedback.passed ? 'rgba(22,101,52,0.5)' : 'rgba(127,29,29,0.5)', border: `1px solid ${feedback.passed ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`, borderRadius: 10, padding: '16px 20px', fontSize: 13, lineHeight: 1.6 }}>
                {feedback.what_worked && <p style={{ color: '#86efac', margin: '0 0 8px', display: 'flex', gap: 6, alignItems: 'flex-start' }}><span style={{ flexShrink: 0, marginTop: 2 }}><IconCheck /></span><span><strong>Worked: </strong>{feedback.what_worked}</span></p>}
                {feedback.what_was_missing && <p style={{ color: '#fde68a', margin: '0 0 8px', display: 'flex', gap: 6, alignItems: 'flex-start' }}><span style={{ flexShrink: 0, marginTop: 2 }}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span><span><strong>Missing: </strong>{feedback.what_was_missing}</span></p>}
                {feedback.stronger_version && <p style={{ color: '#93c5fd', margin: 0, display: 'flex', gap: 6, alignItems: 'flex-start' }}><span style={{ flexShrink: 0, marginTop: 2 }}><IconArrowRight /></span><span><strong>Stronger: </strong>{feedback.stronger_version}</span></p>}
              </div>
              <button onClick={handleNext} disabled={advancing} style={{ background: '#fff', color: '#0f0f13', border: 'none', borderRadius: 8, padding: '10px 28px', fontWeight: 600, fontSize: 13, cursor: 'pointer', alignSelf: 'flex-start' }}>
                {advancing ? 'Loading…' : 'Continue →'}
              </button>
            </div>
          )}
        </div>

        <FeedbackStrip active={!sessionComplete && !roundFailed} enabled={faceAnalysisEnabled} sharedStream={cameraOn ? userStreamRef.current : null} onEmotionChange={setEmotion} />
      </div>
    )
  }

  // ── LEETCODE LAYOUT ────────────────────────────────────────────────────────
  if (isLeetcode) {
    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0a0a0d', color: 'white', overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* Left: video pip area */}
          <div style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', background: '#0e0f14', borderRight: '1px solid #1a1d28' }}>
            {/* User cam or placeholder */}
            <div style={{ position: 'relative', aspectRatio: '4/3', background: '#111118', overflow: 'hidden' }}>
              <video
                ref={userCamRef}
                autoPlay muted playsInline
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: cameraOn ? 'block' : 'none' }}
              />
              {!cameraOn && (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#3d4459' }}>
                  <IconUser />
                </div>
              )}
              <div style={{ position: 'absolute', bottom: 6, left: 8, fontSize: 10, color: 'rgba(255,255,255,0.4)', background: 'rgba(0,0,0,0.5)', borderRadius: 4, padding: '2px 7px', display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: isRecording ? '#ef4444' : '#4ade80' }} />
                You
              </div>
            </div>
            {/* AI interviewer */}
            {character && (
              <div style={{ margin: 12, borderRadius: 8, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.07)' }}>
                <AvatarPanel character={character} isSpeaking={isSpeaking} />
              </div>
            )}
            {/* Avatar reaction */}
            {avatarReaction && (
              <div style={{ margin: '0 12px', background: 'rgba(30,41,59,0.9)', border: '1px solid rgba(34,211,238,0.2)', borderRadius: 8, padding: '8px 12px', fontSize: 11, color: 'rgba(226,232,240,0.85)', lineHeight: 1.5 }}>
                <span style={{ color: 'rgba(34,211,238,0.6)', fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em' }}>Interviewer</span>
                <p style={{ margin: '4px 0 0' }}>{avatarReaction}</p>
              </div>
            )}
            <div style={{ flex: 1 }} />
            {/* Persona */}
            <div style={{ padding: '8px 12px 12px', fontSize: 10, color: '#4a5168', fontStyle: 'italic', borderTop: '1px solid #1a1d28', textAlign: 'center' }}>
              {persona || 'Hiring Manager'}
            </div>
          </div>

          {/* Right: code editor */}
          <div className="flex flex-col flex-1 min-w-0">
            <div className="bg-gray-800 px-5 py-4 text-base leading-relaxed border-b border-gray-700 shrink-0">
              {activeQuestion}
            </div>
            {codeReaction && (
              <div className="bg-blue-950 border-b border-blue-800 px-5 py-2 text-xs text-blue-200 leading-relaxed shrink-0">
                <span className="font-semibold text-blue-400">AI: </span>{codeReaction}
              </div>
            )}
            <div className="flex-1 min-h-0">
              <CodeEditor
                question={activeQuestion}
                company={company}
                sessionId={sessionId}
                onReaction={setCodeReaction}
              />
            </div>
            <div className="flex gap-3 p-4 border-t border-gray-800 bg-gray-900 shrink-0">
              {!feedback ? (
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 px-6 py-2 rounded-lg font-semibold"
                >
                  {loading ? 'Grading…' : 'Submit Solution'}
                </button>
              ) : (
                <>
                  <div className={`flex-1 rounded-lg px-4 py-2 text-sm space-y-1 ${feedback.passed ? 'bg-green-950 border border-green-700' : 'bg-red-950 border border-red-700'}`}>
                    {feedback.what_worked && <p className="text-green-300"><span className="font-semibold">✓ Worked: </span>{feedback.what_worked}</p>}
                    {feedback.what_was_missing && <p className="text-yellow-300"><span className="font-semibold">△ Missing: </span>{feedback.what_was_missing}</p>}
                    {feedback.stronger_version && <p className="text-blue-300"><span className="font-semibold">→ Stronger: </span>{feedback.stronger_version}</p>}
                  </div>
                  <button onClick={handleNext} disabled={advancing} className="bg-gray-700 hover:bg-gray-600 disabled:opacity-40 px-5 py-2 rounded-lg font-semibold">
                    {advancing ? '…' : feedback.roundComplete ? 'Finish Round →' : 'Next →'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
        <ControlsBar />
        <FeedbackStrip
          active={!sessionComplete && !roundFailed}
          enabled={faceAnalysisEnabled}
          sharedStream={cameraOn ? userStreamRef.current : null}
          onEmotionChange={setEmotion}
        />
      </div>
    )
  }

  // ── STANDARD VIDEO CALL LAYOUT ─────────────────────────────────────────────
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0a0a0d', color: 'white', overflow: 'hidden' }}>
      <FeedbackStrip
        active={!sessionComplete && !roundFailed}
        enabled={faceAnalysisEnabled}
        sharedStream={cameraOn ? userStreamRef.current : null}
        onEmotionChange={setEmotion}
      />

      {/* Video area — fills all space above controls */}

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>

        {/* Timer bar */}
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: 'rgba(255,255,255,0.06)', zIndex: 10 }}>
          <div style={{ height: '100%', width: `${timerPct}%`, background: timerColor, transition: 'width 1s linear, background 0.5s' }} />
        </div>

        {/* User camera feed */}
        <video
          ref={userCamRef}
          autoPlay muted playsInline
          style={{
            position: 'absolute', inset: 0,
            width: '100%', height: '100%',
            objectFit: 'cover',
            display: cameraOn ? 'block' : 'none',
          }}
        />

        {/* Camera-off placeholder */}
        {!cameraOn && (
          <div style={{
            position: 'absolute', inset: 0,
            background: 'radial-gradient(ellipse at 50% 30%, #1a1a2e 0%, #0f0f14 60%)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14,
          }}>
            <div style={{
              width: 96, height: 96, borderRadius: '50%',
              background: '#1e2130', border: '2px solid #2a3050',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#3d4459',
            }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
              </svg>
            </div>
            <span style={{ fontSize: 13, color: '#3d4459' }}>Camera is off</span>
          </div>
        )}

        {/* AI interviewer pip — top-right */}
        {character && (
          <div style={{
            position: 'absolute', top: 16, right: 16,
            width: 148,
            borderRadius: 10, overflow: 'hidden',
            border: '1px solid rgba(255,255,255,0.09)',
            boxShadow: '0 4px 24px rgba(0,0,0,0.8)',
            zIndex: 20,
          }}>
            <AvatarPanel character={character} isSpeaking={isSpeaking} />
          </div>
        )}

        {/* Avatar reaction — floats left of pip */}
        {avatarReaction && (
          <div style={{
            position: 'absolute', top: 16, right: 180,
            maxWidth: 200,
            background: 'rgba(20,24,36,0.92)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8, padding: '8px 12px',
            fontSize: 12, color: 'rgba(226,232,240,0.8)', lineHeight: 1.5,
            zIndex: 20,
          }}>
            <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 4 }}>
              Interviewer
            </div>
            {avatarReaction}
          </div>
        )}

        {/* Emotion strip — top-left (only when face analysis active) */}
        {faceAnalysisEnabled && emotion && (
          <div style={{
            position: 'absolute', top: 16, left: 16,
            background: 'rgba(0,0,0,0.62)', backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8, padding: '7px 12px',
            display: 'flex', alignItems: 'center', gap: 10,
            zIndex: 20,
          }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: '#4ade80',
              animation: 'emotionPulse 2s ease-in-out infinite',
              flexShrink: 0,
            }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: EMOTION_COLOR[emotion.emotion] ?? '#94a3b8' }}>
                {emotion.emotion.charAt(0).toUpperCase() + emotion.emotion.slice(1)}
              </div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 1 }}>
                Face analysis on
              </div>
            </div>
            <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.1)' }} />
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>
              {emotion.eye_contact ? 'Eye contact' : '↗ Look at camera'}
            </div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>
              {Math.round(emotion.confidence * 100)}% conf
            </div>
          </div>
        )}

        {/* Time warning banner — top-center */}
        {timeWarning && (
          <div style={{
            position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
            background: timeWarning === 'red' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.12)',
            border: `1px solid ${timeWarning === 'red' ? 'rgba(239,68,68,0.4)' : 'rgba(245,158,11,0.4)'}`,
            color: timeWarning === 'red' ? '#f87171' : '#fbbf24',
            fontSize: 11, fontWeight: 600, padding: '4px 14px', borderRadius: 4,
            fontFamily: 'monospace', zIndex: 20,
          }}>
            {timeWarning === 'red' ? 'Time almost up' : 'Interview ending soon'}
          </div>
        )}

        {/* Follow-up badge */}
        {isFollowUp && (
          <div style={{
            position: 'absolute', bottom: 172, left: 16,
            background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.3)',
            color: '#22d3ee', fontSize: 10, fontWeight: 600,
            padding: '3px 8px', borderRadius: 4,
            fontFamily: 'monospace', textTransform: 'uppercase', letterSpacing: '0.12em',
            zIndex: 20,
          }}>
            ↩ Follow-up
          </div>
        )}

        {/* ── Bottom overlay: feedback / text input / question ── */}

        {feedback ? (
          // Feedback overlay
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.8) 70%, transparent 100%)',
            padding: '24px 20px 68px',
            zIndex: 20,
          }}>
            <div style={{
              background: feedback.passed ? 'rgba(22,101,52,0.5)' : 'rgba(127,29,29,0.5)',
              border: `1px solid ${feedback.passed ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
              borderRadius: 10, padding: '14px 16px',
              fontSize: 13, lineHeight: 1.6, marginBottom: 14,
              backdropFilter: 'blur(4px)',
            }}>
              {feedback.what_worked && (
                <p style={{ color: '#86efac', margin: '0 0 6px', display: 'flex', gap: 7, alignItems: 'flex-start' }}>
                  <span style={{ flexShrink: 0, marginTop: 2 }}><IconCheck /></span>
                  <span><strong>Worked: </strong>{feedback.what_worked}</span>
                </p>
              )}
              {feedback.what_was_missing && (
                <p style={{ color: '#fde68a', margin: '0 0 6px', display: 'flex', gap: 7, alignItems: 'flex-start' }}>
                  <span style={{ flexShrink: 0, marginTop: 2 }}>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  </span>
                  <span><strong>Missing: </strong>{feedback.what_was_missing}</span>
                </p>
              )}
              {feedback.stronger_version && (
                <p style={{ color: '#93c5fd', margin: 0, display: 'flex', gap: 7, alignItems: 'flex-start' }}>
                  <span style={{ flexShrink: 0, marginTop: 2 }}><IconArrowRight /></span>
                  <span><strong>Stronger: </strong>{feedback.stronger_version}</span>
                </p>
              )}
            </div>
            <button
              onClick={handleNext}
              disabled={advancing}
              style={{
                background: '#ffffff', color: '#0f0f13',
                border: 'none', borderRadius: 8,
                padding: '9px 24px', fontWeight: 600, fontSize: 13,
                cursor: advancing ? 'not-allowed' : 'pointer',
                opacity: advancing ? 0.5 : 1,
              }}
            >
              {advancing ? 'Loading next round…' : feedback.roundComplete ? 'Finish Round →' : 'Next Question →'}
            </button>
          </div>

        ) : pendingTranscript ? (
          // Transcript confirmation strip — auto-submits in 3 s, user can cancel
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.97) 0%, rgba(0,0,0,0.85) 70%, transparent 100%)',
            padding: '18px 20px 68px',
            zIndex: 20,
          }}>
            <div style={{
              background: 'rgba(34,197,94,0.08)',
              border: '1px solid rgba(34,197,94,0.2)',
              borderRadius: 10, padding: '12px 16px',
              display: 'flex', alignItems: 'flex-start', gap: 12,
            }}>
              <span style={{ flexShrink: 0, marginTop: 1, color: '#4ade80' }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: '#e2e8f0', lineHeight: 1.55, wordBreak: 'break-word' }}>
                  {pendingTranscript}
                </div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginTop: 6 }}>
                  Submitting in 3s…
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                <button
                  onClick={confirmTranscript}
                  style={{
                    background: '#4ade80', color: '#0f0f13',
                    border: 'none', borderRadius: 6,
                    padding: '5px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer',
                  }}
                >
                  Submit now
                </button>
                <button
                  onClick={cancelTranscript}
                  style={{
                    background: 'rgba(255,255,255,0.07)', color: '#94a3b8',
                    border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
                    padding: '5px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>

        ) : textMode || muted ? (
          // Text input overlay — shown when muted or text mode toggled
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.8) 60%, transparent 100%)',
            padding: '16px 20px 64px',
            zIndex: 20,
          }}>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginBottom: 8 }}>
              {muted ? 'Mic muted — type your answer' : `Q${qIndex + 1} — Type your answer`}
            </div>
            <textarea
              style={{
                width: '100%', maxWidth: 680,
                background: 'rgba(255,255,255,0.07)',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 8, padding: '10px 12px',
                fontSize: 13, color: '#e2e8f0',
                fontFamily: 'inherit', resize: 'none', height: 88,
                lineHeight: 1.55, outline: 'none',
              }}
              placeholder="Type your answer here…"
              value={answer}
              onChange={(e) => handleAnswerChange(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleSubmit() }}
            />
          </div>

        ) : (
          // Question overlay (default)
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.55) 60%, transparent 100%)',
            padding: '28px 20px 64px',
            zIndex: 20,
          }}>
            <div style={{
              fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
              color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', marginBottom: 8,
            }}>
              Question {qIndex + 1}
            </div>
            <div style={{ fontSize: 15, fontWeight: 400, color: '#f0f2f7', lineHeight: 1.6, maxWidth: '72%' }}>
              {activeQuestion}
            </div>
          </div>
        )}

        {/* User name tag — above controls */}
        <div style={{
          position: 'absolute', bottom: 12, left: 14,
          background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(8px)',
          borderRadius: 6, padding: '5px 12px',
          fontSize: 12, fontWeight: 500, color: '#d4d8e2',
          display: 'flex', alignItems: 'center', gap: 7,
          border: '1px solid rgba(255,255,255,0.06)',
          zIndex: 30,
        }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: isRecording ? '#ef4444' : '#4ade80',
            animation: 'emotionPulse 2s ease-in-out infinite',
          }} />
          You
        </div>
      </div>

      <ControlsBar />
    </div>
  )
}
