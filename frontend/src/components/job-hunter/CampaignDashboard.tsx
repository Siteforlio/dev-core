import { useEffect, useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'
import { useCampaignActivity } from '../../hooks/useCampaignActivity'
import { useAuthStore } from '../../store/authStore'
import SummaryStrip from './SummaryStrip'
import ApplicationCard from './ApplicationCard'
import ActivityFeed from './ActivityFeed'
import type { CampaignSummary, Application, ScheduledInterview } from '../../types/jobHunter'

interface Props {
  campaignId: string
  onStartInterviewPrep: (personaString: string, company: string, role: string) => void
}

export default function CampaignDashboard({ campaignId, onStartInterviewPrep }: Props) {
  const { getDashboard, getInterviewContext } = useJobHunter()
  const token = useAuthStore((s) => s.accessToken)
  const { feed } = useCampaignActivity(campaignId, token)

  const [summary, setSummary] = useState<CampaignSummary | null>(null)
  const [pipeline, setPipeline] = useState<Application[]>([])
  const [interviews, setInterviews] = useState<ScheduledInterview[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [bridgeLoading, setBridgeLoading] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError('')
    getDashboard(campaignId)
      .then(({ summary: s, pipeline: p, interviews: i }) => {
        if (!cancelled) {
          setSummary(s)
          setPipeline(p)
          setInterviews(i)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError('Failed to load dashboard. Is the backend running?')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [campaignId])

  const handleStartInterviewPrep = async (applicationId: string) => {
    setBridgeLoading(applicationId)
    try {
      const ctx = await getInterviewContext(campaignId, applicationId)
      onStartInterviewPrep(ctx.personaString, ctx.company, ctx.role)
    } finally {
      setBridgeLoading(null)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <div
          role="status"
          className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
        />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <p className="text-red-400 text-sm">{loadError}</p>
      </div>
    )
  }

  return (
    <div className="flex gap-4 h-full">
      {/* Main panel */}
      <div className="flex-1 flex flex-col gap-4 min-w-0 overflow-y-auto">
        {summary && <SummaryStrip summary={summary} />}

        {interviews.length > 0 && (
          <div className="bg-purple-900/20 border border-purple-800 rounded-lg px-4 py-3">
            <h3 className="text-xs font-semibold text-purple-300 uppercase tracking-wide mb-2">
              Scheduled Interviews
            </h3>
            <div className="flex flex-col gap-2">
              {interviews.map((inv) => (
                <div key={inv.applicationId} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white font-medium">
                      {inv.company} — {inv.role}
                    </p>
                    <p className="text-xs text-gray-400">
                      {new Date(inv.scheduledAt).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-2">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
            Applications Pipeline
          </h3>
          {pipeline.length === 0 ? (
            <p className="text-gray-600 text-sm py-8 text-center">
              No applications yet — the scraper is warming up.
            </p>
          ) : (
            pipeline.map((app) => (
              <div
                key={app.id}
                className={bridgeLoading === app.id ? 'opacity-60 pointer-events-none' : ''}
              >
                <ApplicationCard application={app} onStartInterviewPrep={handleStartInterviewPrep} />
              </div>
            ))
          )}
        </div>
      </div>

      {/* Activity feed panel */}
      <div className="w-72 flex-shrink-0 bg-gray-950/50 border border-gray-800 rounded-lg p-4 h-full">
        <ActivityFeed feed={feed} />
      </div>
    </div>
  )
}
