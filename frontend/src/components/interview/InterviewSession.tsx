import { useState, useEffect, useRef } from 'react'
import { useInterviewStore } from '../../store/interviewStore'
import { useInterviewSession } from '../../hooks/useInterviewSession'
import { useVoice } from '../../hooks/useVoice'
import AvatarPanel from './AvatarPanel'
import FeedbackStrip, { EmotionState } from './FeedbackStrip'
import DebriefReport from './DebriefReport'
import CodeEditor from './CodeEditor'
import { pickCharacter } from './InterviewerCharacters'

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
  border: '1px solid rgba(255,255,255,0.08)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: 15,
  cursor: 'pointer',
  background: '#1a1d28',
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
  } = useInterviewStore()

  const { submitAnswer } = useInterviewSession()
  const { speak, startRecording, stopRecording, isSpeaking, isRecording } = useVoice()

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
  const [cameraOn, setCameraOn] = useState(true)
  const [faceAnalysisEnabled, setFaceAnalysisEnabled] = useState(false)
  const [textMode, setTextMode] = useState(false)
  const [emotion, setEmotion] = useState<EmotionState | null>(null)
  const [timerPct, setTimerPct] = useState(0)
  const [timeRemaining, setTimeRemaining] = useState(1800)
  const [showSpeakerMenu, setShowSpeakerMenu] = useState(false)
  const [audioOutputs, setAudioOutputs] = useState<MediaDeviceInfo[]>([])

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
  const activeQuestion = followUpQuestion ?? question
  const character = sessionId ? pickCharacter(sessionId, level) : undefined
  const allRoundTypes = currentRound ? [currentRound.type, ...remainingRounds] : []
  const roundIndex = 0  // current is always index 0 in allRoundTypes
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
  useEffect(() => {
    const budget = currentRound?.timeBudgetSeconds ?? 1800
    const tick = () => {
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
          <div className="text-5xl">✗</div>
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

  // ── Handlers ──

  const handleAnswerChange = (newValue: string) => {
    const dropped = prevAnswerLengthRef.current - newValue.length
    if (dropped >= 40) {
      rewriteCountRef.current += 1
      fetch(`/api/v1/interview-sessions/${sessionId}/behavioral-signal`, {
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

  const handleSubmit = async () => {
    if (!answer.trim()) return
    setLoading(true)
    const timeTakenSeconds = Math.floor((Date.now() - questionStartTimeRef.current) / 1000)
    const currentQuestion = followUpQuestion ?? question

    const result = await submitAnswer(sessionId, currentRound.id, currentQuestion, answer, {
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
  handleSubmitRef.current = handleSubmit

  const handleMic = async () => {
    if (isRecording) {
      const transcript = await stopRecording()
      if (transcript) setAnswer((prev) => (prev ? `${prev} ${transcript}` : transcript))
    } else {
      await startRecording()
    }
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
      const res = await fetch(`/api/v1/interview-sessions/${sessionId}/advance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ next_round_type: remainingRounds[0] }),
      })
      if (res.ok) {
        const json = await res.json()
        const d = json.data
        setFollowUpQuestion(null)
        setIsFollowUp(false)
        advanceRound(
          {
            id: d.round_id,
            type: d.current_round,
            questions: d.questions,
            currentQuestionIndex: 0,
            timeBudgetSeconds: d.time_budget_seconds ?? 1800,
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
  const ControlsBar = () => (
    <div style={{
      height: 58, flexShrink: 0,
      background: '#0e0f14',
      borderTop: '1px solid #1a1d28',
      display: 'flex', alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px',
      gap: 8,
    }}>
      {/* Left — timer + round info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ ...chip, color: timerPct >= 95 ? '#f87171' : timerPct >= 80 ? '#fbbf24' : '#c4c9d8' }}>
          ⏱ {formatTime(timeRemaining)}
        </span>
        <span style={chip}>
          {currentRound.type.charAt(0).toUpperCase() + currentRound.type.slice(1)}
        </span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {allRoundTypes.map((r, i) => (
            <div key={i} title={r} style={{
              width: 7, height: 7, borderRadius: '50%',
              background: i === roundIndex ? '#3b82f6' : '#2a2d3a',
            }} />
          ))}
        </div>
      </div>

      {/* Center — main action buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* Mic */}
        <button
          onClick={handleMic}
          title={isRecording ? 'Stop recording' : 'Start recording'}
          style={{
            ...ctrlBtn,
            background: isRecording ? 'rgba(239,68,68,0.15)' : '#1a1d28',
            color: isRecording ? '#f87171' : '#94a3b8',
            border: isRecording ? '1px solid rgba(239,68,68,0.3)' : '1px solid rgba(255,255,255,0.08)',
            animation: isRecording ? 'micPulse 1s ease-in-out infinite' : 'none',
          }}
        >
          {isRecording ? '⏹' : '🎙'}
        </button>

        {/* Camera */}
        <button
          onClick={() => setCameraOn((v) => !v)}
          title={cameraOn ? 'Turn camera off' : 'Turn camera on'}
          style={{
            ...ctrlBtn,
            background: cameraOn ? '#1a1d28' : 'rgba(239,68,68,0.1)',
            color: cameraOn ? '#94a3b8' : '#f87171',
            border: cameraOn ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(239,68,68,0.2)',
          }}
        >
          {cameraOn ? '📷' : '🚫'}
        </button>

        {/* Submit / Next — primary action */}
        <button
          onClick={feedback ? handleNext : handleSubmit}
          disabled={loading || advancing || (!feedback && !answer.trim() && !isLeetcode)}
          title={feedback ? (advancing ? 'Loading…' : 'Next') : 'Submit answer'}
          style={{
            width: 46, height: 46, borderRadius: '50%',
            background: '#ffffff', color: '#0f0f13',
            border: 'none', fontWeight: 700, fontSize: 18,
            cursor: 'pointer',
            opacity: (loading || advancing || (!feedback && !answer.trim() && !isLeetcode)) ? 0.4 : 1,
            flexShrink: 0,
          }}
        >
          {loading || advancing ? '…' : feedback ? '→' : '✓'}
        </button>

        {/* End session */}
        <button
          onClick={reset}
          title="End interview"
          style={{
            ...ctrlBtn,
            background: 'rgba(239,68,68,0.08)',
            color: '#f87171',
            border: '1px solid rgba(239,68,68,0.12)',
          }}
        >
          ■
        </button>
      </div>

      {/* Right — speaker, type, face analysis */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, position: 'relative' }}>
        {/* Speaker select */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowSpeakerMenu((v) => !v)}
            title="Select speaker"
            style={ctrlBtn}
          >
            🔊
          </button>
          {showSpeakerMenu && (
            <div style={{
              position: 'absolute', bottom: '100%', right: 0, marginBottom: 8,
              background: '#1a1d28', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8, padding: '4px 0', minWidth: 220, zIndex: 50,
              boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
            }}>
              <div style={{ padding: '6px 14px 4px', fontSize: 10, color: '#4a5168', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Audio Output
              </div>
              {audioOutputs.length === 0 ? (
                <div style={{ padding: '6px 14px', fontSize: 12, color: '#4a5168' }}>
                  No devices found (Chrome only)
                </div>
              ) : audioOutputs.map((d) => (
                <div
                  key={d.deviceId}
                  onClick={() => setShowSpeakerMenu(false)}
                  style={{ padding: '7px 14px', fontSize: 12, color: '#94a3b8', cursor: 'pointer' }}
                >
                  {d.label || `Speaker ${d.deviceId.slice(0, 8)}`}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Text input toggle */}
        <button
          onClick={() => setTextMode((v) => !v)}
          style={toggleBtn(textMode, 'rgba(34,197,94,0.1)', 'rgba(34,197,94,0.25)', '#4ade80')}
        >
          ⌨️ Type
        </button>

        {/* Face analysis toggle */}
        <button
          onClick={() => setFaceAnalysisEnabled((v) => !v)}
          style={toggleBtn(faceAnalysisEnabled)}
        >
          <span>👁</span>
          <span>Face Analysis</span>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: faceAnalysisEnabled ? '#818cf8' : '#3d4459',
            flexShrink: 0,
          }} />
        </button>

        {/* Q counter */}
        <span style={{ ...chip, color: '#4a5168' }}>
          Q {qIndex + 1}/{totalQuestions}
        </span>
      </div>

      <style>{`
        @keyframes micPulse {
          0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
          50%      { box-shadow: 0 0 0 6px rgba(239,68,68,0); }
        }
        @keyframes emotionPulse {
          0%,100% { opacity: 1; }
          50%      { opacity: 0.35; }
        }
      `}</style>
    </div>
  )

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
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28 }}>
                  🧑‍💻
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
              fontSize: '2.4rem',
            }}>🧑‍💻</div>
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
              {emotion.eye_contact ? '👁 Eye contact' : '↗ Look at camera'}
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
                <p style={{ color: '#86efac', margin: '0 0 6px' }}>
                  <strong>✓ Worked: </strong>{feedback.what_worked}
                </p>
              )}
              {feedback.what_was_missing && (
                <p style={{ color: '#fde68a', margin: '0 0 6px' }}>
                  <strong>△ Missing: </strong>{feedback.what_was_missing}
                </p>
              )}
              {feedback.stronger_version && (
                <p style={{ color: '#93c5fd', margin: 0 }}>
                  <strong>→ Stronger: </strong>{feedback.stronger_version}
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

        ) : textMode ? (
          // Text input overlay
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.8) 60%, transparent 100%)',
            padding: '16px 20px 64px',
            zIndex: 20,
          }}>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginBottom: 8 }}>
              Q{qIndex + 1} — Type your answer
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
