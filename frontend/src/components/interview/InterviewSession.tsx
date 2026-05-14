import { useState, useEffect, useRef } from 'react'
import { useInterviewStore } from '../../store/interviewStore'
import { useInterviewSession } from '../../hooks/useInterviewSession'
import { useVoice } from '../../hooks/useVoice'
import AvatarPanel from './AvatarPanel'
import FeedbackStrip from './FeedbackStrip'
import DebriefReport from './DebriefReport'
import CodeEditor from './CodeEditor'

interface Props {
  token: string
}

export default function InterviewSession({ token }: Props) {
  const {
    sessionId,
    currentRound,
    company,
    role,
    persona,
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

  const prevQuestionRef = useRef('')
  const questionStartTimeRef = useRef<number>(Date.now())
  const rewriteCountRef = useRef(0)
  const prevAnswerLengthRef = useRef(0)
  const roundStartTimeRef = useRef<number>(Date.now())
  const handleSubmitRef = useRef<(() => Promise<void>) | null>(null)

  const question = currentRound?.questions[currentRound.currentQuestionIndex] ?? ''
  const qIndex = currentRound?.currentQuestionIndex ?? 0
  const totalQuestions = currentRound?.questions.length ?? 0
  const isLeetcode = currentRound?.type === 'leetcode'

  // Auto-speak question when it changes
  useEffect(() => {
    if (question && question !== prevQuestionRef.current) {
      prevQuestionRef.current = question
      speak(question)
    }
  }, [question]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reset timer and rewrite counter when question changes
  useEffect(() => {
    questionStartTimeRef.current = Date.now()
    rewriteCountRef.current = 0
    prevAnswerLengthRef.current = 0
  }, [question])

  // Reset round start time when round changes
  useEffect(() => {
    roundStartTimeRef.current = Date.now()
    setTimeWarning(null)
  }, [currentRound?.id])

  // Time warning banner — poll every 30s
  useEffect(() => {
    const timeBudgetSeconds = currentRound?.timeBudgetSeconds ?? 1800
    const interval = setInterval(() => {
      const elapsed = (Date.now() - roundStartTimeRef.current) / 1000
      const pct = elapsed / timeBudgetSeconds
      if (pct >= 1.0) {
        setTimeWarning('red')
        if (!loading && !feedback && answer.trim()) {
          handleSubmitRef.current?.()
        }
      } else if (pct >= 0.95) {
        setTimeWarning('red')
      } else if (pct >= 0.80) {
        setTimeWarning('amber')
      } else {
        setTimeWarning(null)
      }
    }, 30_000)
    return () => clearInterval(interval)
  }, [currentRound?.id, currentRound?.timeBudgetSeconds])
  // Note: handleSubmit is intentionally excluded from deps — auto-submit is best-effort

  if (!currentRound || !sessionId) return null

  // ── Debrief screen ──────────────────────────────────────────────────────────
  if (sessionComplete) {
    return <DebriefReport token={token} onRestart={reset} />
  }

  // ── Round failed screen ─────────────────────────────────────────────────────
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

  // Active question: follow-up overrides prepared question
  const activeQuestion = followUpQuestion ?? question

  // ── Answer change handler (rewrite detection) ───────────────────────────────
  const handleAnswerChange = (newValue: string) => {
    const dropped = prevAnswerLengthRef.current - newValue.length
    if (dropped >= 40) {
      rewriteCountRef.current += 1
      // Fire behavioral signal (non-blocking)
      fetch(`/api/v1/interview-sessions/${sessionId}/behavioral-signal`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
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

  // ── Submit handler ──────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!answer.trim()) return
    setLoading(true)

    const timeTakenSeconds = Math.floor((Date.now() - questionStartTimeRef.current) / 1000)
    const currentQuestion = followUpQuestion ?? question

    const result = await submitAnswer(sessionId, currentRound.id, currentQuestion, answer, {
      totalQuestions,
      emotionState: undefined,
      timeTakenSeconds,
      rewriteCount: rewriteCountRef.current,
      isFollowup: isFollowUp,
    })

    // Reset rewrite tracking for next question
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

    // If there's a follow-up question, inject it before advancing
    if (followUp && !roundComplete) {
      setFollowUpQuestion(followUp)
      setIsFollowUp(true)
      return  // Don't advance question index yet — follow-up is next
    }

    // Clear follow-up state and advance
    setFollowUpQuestion(null)
    setIsFollowUp(false)

    if (!roundComplete) {
      nextQuestion()
      return
    }

    // Round is over
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

  // ── Round indicator dots ────────────────────────────────────────────────────
  const allRoundTypes = [currentRound.type, ...remainingRounds]

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-800 px-8 py-3 flex items-center justify-between shrink-0">
        <div className="text-sm text-gray-400">
          <span className="text-white font-semibold">{company}</span> · {role} ·{' '}
          <span className="capitalize">{currentRound.type}</span> round
        </div>
        <div className="flex items-center gap-4">
          {/* Round progress dots */}
          <div className="flex items-center gap-1.5">
            {allRoundTypes.map((r, i) => (
              <div
                key={i}
                title={r}
                className={`w-2 h-2 rounded-full ${i === 0 ? 'bg-blue-500' : 'bg-gray-700'}`}
              />
            ))}
          </div>
          <span className="text-xs text-gray-500">
            Q {qIndex + 1} / {totalQuestions}
          </span>
          {timeWarning && (
            <div style={{
              background: timeWarning === 'red' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.12)',
              border: `1px solid ${timeWarning === 'red' ? 'rgba(239,68,68,0.4)' : 'rgba(245,158,11,0.4)'}`,
              color: timeWarning === 'red' ? '#f87171' : '#fbbf24',
              fontFamily: 'monospace', fontSize: '11px', fontWeight: 600,
              padding: '3px 10px', borderRadius: '4px',
            }}>
              {timeWarning === 'red' ? 'Time almost up' : 'Interview ending soon'}
            </div>
          )}
          <button className="text-xs text-gray-600 hover:text-gray-400 underline" onClick={reset}>
            Exit
          </button>
        </div>
      </div>

      {/* Split screen */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left — avatar */}
        <div className="w-2/5 flex flex-col">
          <div className="flex-1 p-6">
            <AvatarPanel sessionId={sessionId} persona={persona} isSpeaking={isSpeaking} />
            {avatarReaction && (
              <div style={{
                marginTop: '12px',
                background: 'rgba(30,41,59,0.9)',
                border: '1px solid rgba(34,211,238,0.2)',
                borderRadius: '8px',
                padding: '10px 14px',
                color: 'rgba(226,232,240,0.85)',
                fontFamily: 'monospace',
                fontSize: '12px',
                lineHeight: '1.5',
              }}>
                <span style={{ color: 'rgba(34,211,238,0.6)', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.12em' }}>Interviewer</span>
                <p style={{ margin: '4px 0 0' }}>{avatarReaction}</p>
              </div>
            )}
          </div>
        </div>

        {/* Right — Q&A (or code editor for leetcode) */}
        <div className={`w-3/5 flex flex-col ${isLeetcode ? '' : 'gap-5 p-6 overflow-y-auto'}`}>
          {isLeetcode ? (
            // ── Leetcode split: question top, Monaco bottom ──
            <div className="flex flex-col h-full">
              <div className="bg-gray-800 rounded-none px-5 py-4 text-base leading-relaxed border-b border-gray-700 shrink-0">
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
              {/* Submit code as answer */}
              <div className="flex gap-3 p-4 border-t border-gray-800 bg-gray-900 shrink-0">
                {!feedback ? (
                  <button
                    onClick={handleSubmit}
                    disabled={loading}
                    className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 px-6 py-2 rounded-lg font-semibold transition-colors"
                  >
                    {loading ? 'Grading…' : 'Submit Solution'}
                  </button>
                ) : (
                  <>
                    <div
                      className={`flex-1 rounded-lg px-4 py-2 text-sm space-y-1 ${
                        feedback.passed
                          ? 'bg-green-950 border border-green-700'
                          : 'bg-red-950 border border-red-700'
                      }`}
                    >
                      {feedback.what_worked && (
                        <p className="text-green-300"><span className="font-semibold">✓ Worked: </span>{feedback.what_worked}</p>
                      )}
                      {feedback.what_was_missing && (
                        <p className="text-yellow-300"><span className="font-semibold">△ Missing: </span>{feedback.what_was_missing}</p>
                      )}
                      {feedback.stronger_version && (
                        <p className="text-blue-300"><span className="font-semibold">→ Stronger: </span>{feedback.stronger_version}</p>
                      )}
                    </div>
                    <button
                      onClick={handleNext}
                      disabled={advancing}
                      className="bg-gray-700 hover:bg-gray-600 disabled:opacity-40 px-5 py-2 rounded-lg font-semibold"
                    >
                      {advancing ? '…' : feedback.roundComplete ? 'Finish Round →' : 'Next →'}
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
            // ── Standard Q&A layout ──
            <>
              {isFollowUp && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: '4px',
                  background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.3)',
                  color: '#22d3ee', fontFamily: 'monospace', fontSize: '10px',
                  fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.12em',
                  padding: '3px 8px', borderRadius: '4px', marginBottom: '6px',
                }}>
                  ↩ Follow-up
                </div>
              )}
              <div className="bg-gray-800 rounded-xl p-5 text-base leading-relaxed">
                {activeQuestion}
              </div>

              {feedback && (
                <div className={`rounded-xl p-4 text-sm leading-relaxed space-y-2 ${
                  feedback.passed
                    ? 'bg-green-950 border border-green-700'
                    : 'bg-red-950 border border-red-700'
                }`}>
                  {feedback.what_worked && (
                    <p className="text-green-300">
                      <span className="font-semibold">✓ Worked: </span>{feedback.what_worked}
                    </p>
                  )}
                  {feedback.what_was_missing && (
                    <p className="text-yellow-300">
                      <span className="font-semibold">△ Missing: </span>{feedback.what_was_missing}
                    </p>
                  )}
                  {feedback.stronger_version && (
                    <p className="text-blue-300">
                      <span className="font-semibold">→ Stronger: </span>{feedback.stronger_version}
                    </p>
                  )}
                </div>
              )}

              {!feedback && (
                <div className="flex flex-col gap-2">
                  <textarea
                    className="bg-gray-800 border border-gray-700 focus:border-blue-500 outline-none rounded-xl p-4 resize-none h-36 text-white text-sm"
                    placeholder="Type your answer or use the mic…"
                    value={answer}
                    onChange={(e) => handleAnswerChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && e.metaKey) handleSubmit()
                    }}
                  />
                  <div className="flex gap-3 items-center">
                    <button
                      onClick={handleSubmit}
                      disabled={loading || !answer.trim()}
                      className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 px-6 py-2 rounded-lg font-semibold transition-colors"
                    >
                      {loading ? 'Grading…' : 'Submit'}
                    </button>
                    <button
                      onClick={handleMic}
                      title={isRecording ? 'Stop recording' : 'Record answer'}
                      className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
                        isRecording
                          ? 'bg-red-600 hover:bg-red-700 animate-pulse'
                          : 'bg-gray-700 hover:bg-gray-600'
                      }`}
                    >
                      🎙️
                    </button>
                    <span className="text-xs text-gray-600">⌘+Enter to submit</span>
                  </div>
                </div>
              )}

              {feedback && (
                <button
                  onClick={handleNext}
                  disabled={advancing}
                  className="bg-gray-700 hover:bg-gray-600 disabled:opacity-40 px-6 py-2 rounded-lg font-semibold w-fit transition-colors"
                >
                  {advancing ? 'Loading next round…' : feedback.roundComplete ? 'Finish Round →' : 'Next Question →'}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Emotion feedback strip — bottom bar */}
      <FeedbackStrip active={!sessionComplete && !roundFailed} />
    </div>
  )
}
