import { useState, useEffect } from 'react'
import { useInterviewStore } from '../../store/interviewStore'
import { useInterviewSession } from '../../hooks/useInterviewSession'
import { useVoice } from '../../hooks/useVoice'
import AvatarPanel from './AvatarPanel'

export default function InterviewSession() {
  const { sessionId, currentRound, company, role, persona, remainingRounds } = useInterviewStore()
  const { submitAnswer } = useInterviewSession()
  const nextQuestion = useInterviewStore((s) => s.nextQuestion)
  const setRoundResult = useInterviewStore((s) => s.setRoundResult)
  const completeSession = useInterviewStore((s) => s.completeSession)
  const sessionComplete = useInterviewStore((s) => s.sessionComplete)
  const reset = useInterviewStore((s) => s.reset)

  const { speak, startRecording, stopRecording, isSpeaking, isRecording } = useVoice()

  const [answer, setAnswer] = useState('')
  const [feedback, setFeedback] = useState<{ text: string; passed: boolean } | null>(null)
  const [loading, setLoading] = useState(false)

  const question = currentRound?.questions[currentRound.currentQuestionIndex] ?? ''
  const qIndex = currentRound?.currentQuestionIndex ?? 0
  const totalQuestions = currentRound?.questions.length ?? 0
  const isLastQuestion = qIndex >= totalQuestions - 1

  // Auto-speak question when it changes
  useEffect(() => {
    if (question) speak(question)
  }, [question]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!currentRound || !sessionId) return null

  if (sessionComplete) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="text-center max-w-md">
          <h1 className="text-3xl font-bold mb-3">Session Complete</h1>
          <p className="text-gray-400 mb-2">{company} · {role}</p>
          <p className="text-green-400 text-sm mb-6">All rounds finished.</p>
          <button
            className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg font-semibold"
            onClick={reset}
          >
            Start New Session
          </button>
        </div>
      </div>
    )
  }

  const handleSubmit = async () => {
    if (!answer.trim()) return
    setLoading(true)
    const result = await submitAnswer(sessionId, currentRound.id, question, answer)
    setFeedback({ text: result.feedback, passed: result.passed })
    setRoundResult(result.passed, result.feedback)
    // Speak the feedback
    speak(result.feedback)
    setAnswer('')
    setLoading(false)
  }

  const handleMic = async () => {
    if (isRecording) {
      const transcript = await stopRecording()
      if (transcript) setAnswer((prev) => prev ? `${prev} ${transcript}` : transcript)
    } else {
      await startRecording()
    }
  }

  const handleNext = () => {
    setFeedback(null)
    if (isLastQuestion) {
      if (remainingRounds.length === 0) {
        completeSession()
      } else {
        completeSession() // Task 14 will chain rounds
      }
    } else {
      nextQuestion()
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-800 px-8 py-3 flex items-center justify-between shrink-0">
        <div className="text-sm text-gray-400">
          <span className="text-white font-semibold">{company}</span> · {role} ·{' '}
          <span className="capitalize">{currentRound.type}</span> round
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-500">
            Question {qIndex + 1} / {totalQuestions}
          </span>
          <button className="text-xs text-gray-600 hover:text-gray-400 underline" onClick={reset}>
            Exit
          </button>
        </div>
      </div>

      {/* Split screen */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left — avatar */}
        <div className="w-2/5 p-6 flex flex-col">
          <AvatarPanel sessionId={sessionId} persona={persona} isSpeaking={isSpeaking} />
        </div>

        {/* Right — Q&A */}
        <div className="w-3/5 flex flex-col gap-5 p-6 overflow-y-auto">
          {/* Question */}
          <div className="bg-gray-800 rounded-xl p-5 text-base leading-relaxed">
            {question}
          </div>

          {/* Feedback */}
          {feedback && (
            <div
              className={`rounded-xl p-4 text-sm leading-relaxed ${
                feedback.passed
                  ? 'bg-green-950 border border-green-700 text-green-200'
                  : 'bg-red-950 border border-red-700 text-red-200'
              }`}
            >
              <span className="font-semibold mr-1">{feedback.passed ? '✓ Pass' : '✗ Needs work'}</span>
              — {feedback.text}
            </div>
          )}

          {/* Answer textarea + mic */}
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

          {/* Next button after feedback */}
          {feedback && (
            <button
              onClick={handleNext}
              className="bg-gray-700 hover:bg-gray-600 px-6 py-2 rounded-lg font-semibold w-fit transition-colors"
            >
              {isLastQuestion ? 'Finish Round →' : 'Next Question →'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
