import { useInterviewStore } from '../store/interviewStore'
import { apiFetch } from '../lib/apiFetch'

const API = 'http://localhost:8000/api/v1'

export function useInterviewSession() {
  const setSession = useInterviewStore((s) => s.setSession)

  const startSession = async (company: string, role: string, rounds: string[]) => {
    const res = await apiFetch(`${API}/interview-sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company, role, round_types: rounds }),
    })
    const { data } = await res.json()
    setSession(
      data.session_id,
      data.company,
      data.role,
      {
        id: data.round_id,
        type: data.current_round,
        questions: data.questions,
        currentQuestionIndex: 0,
      },
      data.remaining_rounds ?? [],
      data.persona,
    )
    return data
  }

  const submitAnswer = async (
    sessionId: string,
    roundId: string,
    question: string,
    answer: string,
    opts?: { totalQuestions?: number; emotionState?: string },
  ) => {
    const res = await apiFetch(`${API}/interview-sessions/${sessionId}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        round_id: roundId,
        question,
        answer,
        total_questions: opts?.totalQuestions ?? 5,
        emotion_state: opts?.emotionState ?? null,
      }),
    })
    return (await res.json()).data
  }

  return { startSession, submitAnswer }
}
