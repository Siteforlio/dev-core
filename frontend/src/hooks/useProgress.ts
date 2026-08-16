// frontend/src/hooks/useProgress.ts
import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/apiFetch'
import { API_BASE } from '../lib/apiBase'

export interface ProgressSummary {
  dimensions: Record<string, number>
  total_sessions: number
  average_score: number
}

export function useProgress() {
  const [data, setData] = useState<ProgressSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch(`${API_BASE()}/progress/me`)
      .then(r => r.json())
      .then(j => setData(j.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return { data, loading }
}
