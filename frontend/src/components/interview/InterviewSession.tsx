import { useState } from 'react'
import { useInterviewStore } from '../../store/interviewStore'
import { useInterviewSession } from '../../hooks/useInterviewSession'

export default function InterviewSession() {
  const { sessionId, currentRound, company, role, persona, remainingRounds } = useInterviewStore()
  const { submitAnswer } = useInterviewSession()
  const nextQuestion = useInterviewStore((s) => s.nextQuestion)
  const setRoundResult = useInterviewStore((s) => s.setRoundResult)
  const completeSession = useInterviewStore((s) => s.completeSession)
  const sessionComplete = useInterviewStore((s) => s.sessionComplete)

  const [answer, setAnswer] = useState('')
  const [feedback, setFeedback] = useState<{ text: string; passed: boolean } | null>(null)
  const [loading, setLoading] = useState(false)

  if (!currentRound || !sessionId) return null

  const totalQuestions = currentRound.questions.length
  const qIndex = currentRound.currentQuestionIndex
  const question = currentRound.questions[qIndex]
  const isLastQuestion = qIndex >= totalQuestions - 1

  if (sessionComplete) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="text-center max-w-md">
          <h1 className="text-3xl font-bold mb-3">Session Complete</h1>
          <p className="text-gray-400 mb-2">{company} · {role}</p>
          <p className="text-green-400 text-sm">All rounds finished. Check your debrief in Task 11.</p>
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
    setAnswer('')
    setLoading(false)
  }

  const handleNext = () => {
    setFeedback(null)
    if (isLastQuestion) {
      if (remainingRounds.length === 0) {
        completeSession()
      } else {
        // Next round — for now mark complete (Task 7+ will chain rounds)
        completeSession()
      }
    } else {
      nextQuestion()
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-800 px-8 py-3 flex items-center justify-between">
        <div className="text-sm text-gray-400">
          <span className="text-white font-semibold">{company}</span> · {role} ·{' '}
          <span className="capitalize">{currentRound.type}</span> round
        </div>
        <div className="text-xs text-gray-500">
          Question {qIndex + 1} / {totalQuestions}
        </div>
      </div>

      {/* Persona strip */}
      <div className="bg-gray-900 px-8 py-2 text-xs text-blue-300 italic border-b border-gray-800">
        {persona}
      </div>

      {/* Main content */}
      <div className="flex flex-col gap-5 p-8 max-w-2xl mx-auto w-full flex-1">
        {/* Question */}
        <div className="bg-gray-800 rounded-lg p-5 text-lg leading-relaxed">
          {question}
        </div>

        {/* Feedback */}
        {feedback && (
          <div
            className={`rounded-lg p-4 text-sm leading-relaxed ${
              feedback.passed
                ? 'bg-green-950 border border-green-700 text-green-200'
                : 'bg-red-950 border border-red-700 text-red-200'
            }`}
          >
            <span className="font-semibold mr-1">{feedback.passed ? '✓ Pass' : '✗ Needs work'}</span>
            — {feedback.text}
          </div>
        )}

        {/* Answer input */}
        {!feedback && (
          <textarea
            className="bg-gray-800 border border-gray-700 focus:border-blue-500 outline-none rounded-lg p-4 resize-none h-36 text-white text-sm"
            placeholder="Type your answer here…"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.metaKey) handleSubmit()
            }}
          />
        )}

        {/* Actions */}
        <div className="flex gap-3">
          {!feedback ? (
            <button
              onClick={handleSubmit}
              disabled={loading || !answer.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 px-6 py-2 rounded-lg font-semibold transition-colors"
            >
              {loading ? 'Grading…' : 'Submit Answer'}
            </button>
          ) : (
            <button
              onClick={handleNext}
              className="bg-gray-700 hover:bg-gray-600 px-6 py-2 rounded-lg font-semibold transition-colors"
            >
              {isLastQuestion ? 'Finish Round →' : 'Next Question →'}
            </button>
          )}
        </div>

        {/* Hint */}
        {!feedback && (
          <p className="text-xs text-gray-600">Tip: ⌘+Enter to submit</p>
        )}
      </div>
    </div>
  )
}
