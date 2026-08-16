import { useInterviewStore } from '../store/interviewStore'
import { apiFetch } from '../lib/apiFetch'
import { API_BASE } from '../lib/apiBase'
import type { SubmitAnswerResponse } from '../types'

export function useInterviewSession() {
  const setSession = useInterviewStore((s) => s.setSession)

  const startSession = async (
    company: string,
    role: string,
    rounds: string[],
    careerTrack: string = '',
    level: string = '',
    interviewStage: string = '',
    jdText?: string,
    managerName?: string,
  ) => {
    const res = await apiFetch(`${API_BASE()}/interview-sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company,
        role,
        round_types: rounds,
        career_track: careerTrack,
        level,
        interview_stage: interviewStage,
        jd_text: jdText || null,
        manager_name: managerName || null,
      }),
    })
    const { data } = await res.json()
    const isSkillsTask = data.current_round === 'skills_task' || data.current_round === 'technical'
    setSession(
      data.session_id,
      data.company,
      data.role,
      {
        id: data.round_id,
        type: data.current_round,
        questions: data.questions ?? [],
        currentQuestionIndex: 0,
        timeBudgetSeconds: data.time_budget_seconds ?? 1800,
        task: data.task ?? null,
        skillsPhase: isSkillsTask ? 'task' : undefined,
      },
      data.remaining_rounds ?? [],
      data.persona,
      data.career_track ?? careerTrack,
      data.level ?? level,
      data.interview_stage ?? interviewStage,
    )
    return data
  }

  const submitAnswer = async (
    sessionId: string,
    roundId: string,
    question: string,
    answer: string,
    opts?: {
      totalQuestions?: number
      emotionState?: string
      timeTakenSeconds?: number
      rewriteCount?: number
      isFollowup?: boolean
    },
  ) => {
    const res = await apiFetch(`${API_BASE()}/interview-sessions/${sessionId}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        round_id: roundId,
        question,
        answer,
        total_questions: opts?.totalQuestions ?? 5,
        emotion_state: opts?.emotionState ?? null,
        time_taken_seconds: opts?.timeTakenSeconds ?? null,
        rewrite_count: opts?.rewriteCount ?? 0,
        is_followup: opts?.isFollowup ?? false,
      }),
    })
    return (await res.json()).data as SubmitAnswerResponse
  }

  const reportCheatSignal = async (
    sessionId: string,
    roundId: string,
    signalType: string,
    extra?: { pasteChars?: number; durationSeconds?: number; charsPerSecond?: number },
  ) => {
    try {
      await apiFetch(`${API_BASE()}/interview-sessions/${sessionId}/cheat-signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          round_id: roundId,
          signal_type: signalType,
          paste_chars: extra?.pasteChars ?? null,
          duration_seconds: extra?.durationSeconds ?? null,
          chars_per_second: extra?.charsPerSecond ?? null,
        }),
      })
    } catch {
      // non-critical — fire and forget
    }
  }

  return { startSession, submitAnswer, reportCheatSignal }
}
