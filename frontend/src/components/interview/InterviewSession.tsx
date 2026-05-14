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
  } | null>(null)
  const [loading, setLoading] = useState(false)
  const [advancing, setAdvancing] = useState(false)
  const prevQuestionRef = useRef('')

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

  // ── Submit handler ──────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!answer.trim()) return
    setLoading(true)
    const result = await submitAnswer(sessionId, currentRound.id, question, answer, {
      totalQuestions,
      emotionState: undefined,
    })
    const roundComplete = result.round_complete ?? false
    const roundPassed = result.round_passed ?? null
    setFeedback({
      what_worked: result.what_worked,
      what_was_missing: result.what_was_missing,
      stronger_version: result.stronger_version,
      passed: result.passed,
      roundComplete,
      roundPassed,
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
    const { roundComplete, roundPassed } = feedback
    setFeedback(null)
    setCodeReaction(null)

    if (!roundComplete) {
      nextQuestion()
      return
    }

    // Round is over
    if (roundPassed === false) {
      setRoundFailed(true)
      return
    }

    // Round passed — advance or complete
    if (remainingRounds.length === 0) {
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
          </div>
        </div>

        {/* Right — Q&A (or code editor for leetcode) */}
        <div className={`w-3/5 flex flex-col ${isLeetcode ? '' : 'gap-5 p-6 overflow-y-auto'}`}>
          {isLeetcode ? (
            // ── Leetcode split: question top, Monaco bottom ──
            <div className="flex flex-col h-full">
              <div className="bg-gray-800 rounded-none px-5 py-4 text-base leading-relaxed border-b border-gray-700 shrink-0">
                {question}
              </div>
              {codeReaction && (
                <div className="bg-blue-950 border-b border-blue-800 px-5 py-2 text-xs text-blue-200 leading-relaxed shrink-0">
                  <span className="font-semibold text-blue-400">AI: </span>{codeReaction}
                </div>
              )}
              <div className="flex-1 min-h-0">
                <CodeEditor
                  question={question}
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
              <div className="bg-gray-800 rounded-xl p-5 text-base leading-relaxed">
                {question}
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
                    onChange={(e) => setAnswer(e.target.value)}
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
