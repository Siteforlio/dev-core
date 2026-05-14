import { useEffect, useState } from 'react'
import { useInterviewStore } from '../../store/interviewStore'

interface DebriefData {
  overall_score: number
  strengths: string[]
  improvements: string[]
  recommendation: string
  top_3_focus_areas: string[]
  recommended_next_session: string
  emotion_summary: Record<string, number>
  rounds: { type: string; grade: number; passed: boolean }[]
}

interface Props {
  token: string
  onRestart: () => void
}

export default function DebriefReport({ token, onRestart }: Props) {
  const { sessionId, company, role } = useInterviewStore()
  const [data, setData] = useState<DebriefData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) return
    fetch(`/api/v1/interview-sessions/${sessionId}/debrief`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((j) => setData(j.data))
      .catch(() => setError('Failed to load debrief.'))
  }, [sessionId, token])

  const score = data?.overall_score ?? 0
  const scoreColor = score >= 7 ? 'text-green-400' : score >= 5 ? 'text-yellow-400' : 'text-red-400'

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-start py-12 px-6">
      <div className="w-full max-w-2xl space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold">Session Debrief</h1>
          <p className="text-gray-400 mt-1">{company} · {role}</p>
        </div>

        {error && <p className="text-red-400 text-center">{error}</p>}

        {!data && !error && (
          <p className="text-gray-500 text-center animate-pulse">Generating your report…</p>
        )}

        {data && (
          <>
            {/* Overall score */}
            <div className="bg-gray-900 rounded-2xl p-6 text-center">
              <p className="text-sm text-gray-500 mb-1">Overall Score</p>
              <p className={`text-5xl font-bold ${scoreColor}`}>{score.toFixed(1)}</p>
              <p className="text-gray-400 text-sm mt-1">/ 10</p>
              <p className="mt-3 text-gray-300 text-sm leading-relaxed">{data.recommendation}</p>
            </div>

            {/* Rounds summary */}
            <div className="bg-gray-900 rounded-2xl p-5">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Rounds</h2>
              <div className="space-y-2">
                {data.rounds.map((r, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="capitalize text-gray-300">{r.type}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-400">{r.grade?.toFixed(1) ?? '—'} / 10</span>
                      <span className={r.passed ? 'text-green-400' : 'text-red-400'}>
                        {r.passed ? 'Pass' : 'Fail'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Strengths */}
            {data.strengths.length > 0 && (
              <div className="bg-gray-900 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-green-400 uppercase tracking-wider mb-3">Strengths</h2>
                <ul className="space-y-1.5">
                  {data.strengths.map((s, i) => (
                    <li key={i} className="text-sm text-gray-300 flex gap-2">
                      <span className="text-green-500 mt-0.5">+</span>{s}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Improvements */}
            {data.improvements.length > 0 && (
              <div className="bg-gray-900 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-yellow-400 uppercase tracking-wider mb-3">Areas to Improve</h2>
                <ul className="space-y-1.5">
                  {data.improvements.map((s, i) => (
                    <li key={i} className="text-sm text-gray-300 flex gap-2">
                      <span className="text-yellow-500 mt-0.5">→</span>{s}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {data.top_3_focus_areas?.length > 0 && (
              <div className="bg-gray-900 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider mb-3">Top 3 Focus Areas</h2>
                <ol className="space-y-1.5 list-decimal list-inside">
                  {data.top_3_focus_areas.map((area, i) => (
                    <li key={i} className="text-sm text-gray-300">{area}</li>
                  ))}
                </ol>
              </div>
            )}

            {data.recommended_next_session && (
              <div className="bg-cyan-950 border border-cyan-800 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider mb-1">Recommended Next Session</h2>
                <p className="text-sm text-cyan-200">{data.recommended_next_session}</p>
              </div>
            )}

            {/* Emotion summary */}
            {Object.keys(data.emotion_summary).length > 0 && (
              <div className="bg-gray-900 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Emotion Breakdown</h2>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(data.emotion_summary).map(([emotion, count]) => (
                    <span key={emotion} className="text-xs bg-gray-800 px-3 py-1.5 rounded-full capitalize text-gray-300">
                      {emotion} <span className="text-gray-500">×{count}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={onRestart}
              className="w-full bg-blue-600 hover:bg-blue-700 py-3 rounded-xl font-semibold transition-colors"
            >
              Start New Session
            </button>
          </>
        )}
      </div>
    </div>
  )
}
