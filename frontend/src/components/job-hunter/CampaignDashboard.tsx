import { useEffect, useRef, useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'
import { useCampaignActivity, type ActivityMessage } from '../../hooks/useCampaignActivity'
import { useAuthStore } from '../../store/authStore'
import SummaryStrip from './SummaryStrip'
import ApplicationCard from './ApplicationCard'
import ActivityFeed from './ActivityFeed'
import CampaignSettings from './CampaignSettings'
import ApplyPanel from './ApplyPanel'
import DidYouApplyPopup from './DidYouApplyPopup'
import TrackingPanel from './TrackingPanel'
import type {
  CampaignSummary, Application, ScheduledInterview,
  ScrapePreferences, BoardStatus, ScrapeRunStatus,
} from '../../types/jobHunter'

type PanelMode = 'none' | 'apply' | 'tracking'

interface Props {
  campaignId: string
  onBack: () => void
  onStartInterviewPrep: (personaString: string, company: string, role: string) => void
  onGoToSettings?: () => void
}

const DEFAULT_PREFS: ScrapePreferences = {
  companyTypes: [],
  workType: 'any',
  regions: [],
  dailyTarget: 100,
}

export default function CampaignDashboard({ campaignId, onBack, onStartInterviewPrep, onGoToSettings }: Props) {
  const { getDashboard, getInterviewContext, triggerScrape, getScrapeStatus } = useJobHunter()
  const token = useAuthStore((s) => s.accessToken)
  const [persistedFeed, setPersistedFeed] = useState<ActivityMessage[]>([])
  const { feed: liveFeed } = useCampaignActivity(campaignId, token)

  // Apply panel state machine
  const [panelMode, setPanelMode] = useState<PanelMode>('none')
  const [activeApplicationId, setActiveApplicationId] = useState<string | null>(null)
  const [prevApplicationId, setPrevApplicationId] = useState<string | null>(null)
  const [showDidYouApply, setShowDidYouApply] = useState(false)

  // Merge persisted + live, deduplicated by message+timestamp
  const feed = [
    ...persistedFeed,
    ...liveFeed.filter(
      (live) => !persistedFeed.some((p) => p.text === live.text)
    ),
  ]

  const [summary, setSummary] = useState<CampaignSummary | null>(null)
  const [pipeline, setPipeline] = useState<Application[]>([])
  const [interviews, setInterviews] = useState<ScheduledInterview[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [bridgeLoading, setBridgeLoading] = useState<string | null>(null)
  const [scraping, setScraping] = useState(false)
  const [scrapeError, setScrapeError] = useState('')
  const [rightPanel, setRightPanel] = useState<'activity' | 'settings'>('activity')
  const [pipelineTab, setPipelineTab] = useState<'all' | 'match' | 'partial' | 'applied' | 'interview'>('all')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 10

  // Scrape preferences + per-board status
  const [prefs, setPrefs] = useState<ScrapePreferences>(DEFAULT_PREFS)
  const [boardStatuses, setBoardStatuses] = useState<Record<string, BoardStatus>>({})
  const [runStatus, setRunStatus] = useState<ScrapeRunStatus | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const filteredPipeline = pipeline.filter((app) => {
    if (pipelineTab === 'all') return true
    if (pipelineTab === 'match') return app.matchScore === 'MATCH'
    if (pipelineTab === 'partial') return app.matchScore === 'PARTIAL'
    if (pipelineTab === 'applied') return app.status === 'applied'
    if (pipelineTab === 'interview') return app.status === 'interview'
    return true
  })

  const totalPages = Math.max(1, Math.ceil(filteredPipeline.length / PAGE_SIZE))
  const pagedPipeline = filteredPipeline.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const tabCounts = {
    all: pipeline.length,
    match: pipeline.filter(a => a.matchScore === 'MATCH').length,
    partial: pipeline.filter(a => a.matchScore === 'PARTIAL').length,
    applied: pipeline.filter(a => a.status === 'applied').length,
    interview: pipeline.filter(a => a.status === 'interview').length,
  }

  const loadDashboard = async () => {
    const { summary: s, pipeline: p, interviews: i, activityLog } = await getDashboard(campaignId)
    setSummary(s)
    setPipeline(p)
    setInterviews(i)
    setPersistedFeed(
      activityLog.map((l, idx) => ({
        id: `persisted-${idx}-${l.createdAt}`,
        text: l.message,
        timestamp: new Date(l.createdAt),
      }))
    )
  }

  const startStatusPolling = () => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const { run, boards } = await getScrapeStatus(campaignId)
        setBoardStatuses(boards)
        if (run) setRunStatus(run)
        // Stop polling once run is done and no boards are still running
        const stillRunning = Object.values(boards).some(
          (b) => b.status === 'running' || b.status === 'queued'
        )
        if (run?.status === 'done' && !stillRunning) {
          stopStatusPolling()
          setScraping(false)
          await loadDashboard()
        }
      } catch {
        // polling errors are silent
      }
    }, 2000)
  }

  const stopStatusPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const handleTriggerScrape = async () => {
    setScraping(true)
    setScrapeError('')
    setBoardStatuses({})
    setRunStatus(null)
    try {
      await triggerScrape(campaignId, prefs)
      startStatusPolling()
    } catch (e: unknown) {
      setScrapeError(e instanceof Error ? e.message : 'Scrape failed')
      setScraping(false)
    }
  }

  // Clean up polling on unmount
  useEffect(() => () => stopStatusPolling(), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError('')
    loadDashboard()
      .then(() => { if (!cancelled) setLoading(false) })
      .catch(() => { if (!cancelled) { setLoadError('Failed to load dashboard. Is the backend running?'); setLoading(false) } })
    return () => { cancelled = true }
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

  // Open apply panel — if switching away from an in-progress panel, prompt "did you apply?"
  const handleApply = (listingId: string) => {
    const listing = pipeline.find((a) => a.id === listingId)
    if (!listing?.applicationId) return // no application record yet — tailoring hasn't run

    if (
      activeApplicationId &&
      activeApplicationId !== listing.applicationId &&
      panelMode === 'apply'
    ) {
      const prev = pipeline.find((a) => a.applicationId === activeApplicationId)
      if (prev && (prev.status === 'pending' || prev.status === 'tailored')) {
        setPrevApplicationId(activeApplicationId)
        setShowDidYouApply(true)
        return
      }
    }
    setActiveApplicationId(listing.applicationId)
    setPanelMode('apply')
  }

  const handleViewTracking = (listingId: string) => {
    const listing = pipeline.find((a) => a.id === listingId)
    if (!listing?.applicationId) return
    setActiveApplicationId(listing.applicationId)
    setPanelMode('tracking')
  }

  const handlePanelClose = () => {
    // If closing an apply panel for a pending app, prompt
    if (panelMode === 'apply' && activeApplicationId) {
      const app = pipeline.find((a) => a.applicationId === activeApplicationId)
      if (app && (app.status === 'pending' || app.status === 'tailored')) {
        setPrevApplicationId(activeApplicationId)
        setShowDidYouApply(true)
        setPanelMode('none')
        return
      }
    }
    setPanelMode('none')
    setActiveApplicationId(null)
  }

  const handleDidYouApplyDone = (status: 'applied' | 'failed' | 'withdrawn') => {
    setShowDidYouApply(false)
    setPrevApplicationId(null)
    // Refresh pipeline so status badge updates
    loadDashboard().catch(() => {})
  }

  const activeApp = activeApplicationId ? pipeline.find((a) => a.id === activeApplicationId) : null

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
    <div className="flex flex-col gap-4 h-full">
      <button
        onClick={onBack}
        className="self-start flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        All Campaigns
      </button>

    <div className="flex gap-4 flex-1 min-h-0 overflow-hidden">
      {/* Main panel */}
      <div className={`flex flex-col gap-4 overflow-hidden transition-all ${panelMode !== 'none' ? 'w-80 flex-shrink-0' : 'flex-1 min-w-0'}`}>
        {summary && <SummaryStrip summary={summary} compact={panelMode !== 'none'} />}

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

        {/* Pipeline tabs */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1 border-b border-gray-800 flex-shrink-0 overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
            {([
              { key: 'all', label: 'All' },
              { key: 'match', label: 'Match' },
              { key: 'partial', label: 'Partial' },
              { key: 'applied', label: 'Applied' },
              { key: 'interview', label: 'Interview' },
            ] as const).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => { setPipelineTab(key); setPage(1) }}
                className={`px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-px flex items-center gap-1.5 ${
                  pipelineTab === key
                    ? 'border-blue-500 text-white'
                    : 'border-transparent text-gray-500 hover:text-gray-300'
                }`}
              >
                {label}
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  pipelineTab === key ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400'
                }`}>
                  {tabCounts[key]}
                </span>
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-1.5 flex-shrink-0">
            {filteredPipeline.length === 0 ? (
              <p className="text-gray-600 text-sm py-8 text-center">
                {pipeline.length === 0 ? 'No jobs yet — hit Run Scrape to start.' : 'No jobs in this category.'}
              </p>
            ) : (
              pagedPipeline.map((app) => (
                <div
                  key={app.id}
                  className={bridgeLoading === app.id ? 'opacity-60 pointer-events-none' : ''}
                >
                  <ApplicationCard
                    application={app}
                    onStartInterviewPrep={handleStartInterviewPrep}
                    onApply={handleApply}
                    onViewTracking={handleViewTracking}
                  />
                </div>
              ))
            )}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between flex-shrink-0 pt-2 border-t border-gray-800">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="text-xs text-gray-400 hover:text-white disabled:opacity-30 px-2 py-1 rounded hover:bg-gray-800 transition-colors"
              >
                ← Prev
              </button>
              <span className="text-xs text-gray-500">
                Page {page} of {totalPages}
                <span className="ml-1 text-gray-600">({filteredPipeline.length} total)</span>
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="text-xs text-gray-400 hover:text-white disabled:opacity-30 px-2 py-1 rounded hover:bg-gray-800 transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Apply / Tracking panel (70% when active) */}
      {panelMode !== 'none' && activeApplicationId && (
        <div className="flex-1 min-w-0 border border-[#1c1c1c] rounded-xl overflow-hidden" style={{ maxHeight: 'calc(100vh - 160px)' }}>
          {panelMode === 'apply' && (
            <ApplyPanel
              campaignId={campaignId}
              applicationId={activeApplicationId}
              onClose={handlePanelClose}
            />
          )}
          {panelMode === 'tracking' && (
            <TrackingPanel
              campaignId={campaignId}
              applicationId={activeApplicationId}
              onClose={handlePanelClose}
            />
          )}
        </div>
      )}

      {/* Right panel — Activity / Settings (hidden when apply/tracking panel is open) */}
      {panelMode === 'none' && (
      <div className="w-72 flex-shrink-0 bg-gray-950/50 border border-gray-800 rounded-lg flex flex-col overflow-hidden" style={{ maxHeight: 'calc(100vh - 160px)' }}>
        {/* Panel tabs */}
        <div className="flex border-b border-gray-800 flex-shrink-0">
          {(['activity', 'settings'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setRightPanel(tab)}
              className={`flex-1 py-2 text-xs font-medium transition-colors ${
                rightPanel === tab ? 'text-white border-b-2 border-blue-500' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab === 'activity' ? 'Activity' : 'Settings'}
            </button>
          ))}
        </div>

        <div className="flex-1 min-h-0 p-4 overflow-y-auto flex flex-col [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
          {rightPanel === 'activity' ? (
            <ActivityFeed
              feed={feed}
              onTriggerScrape={handleTriggerScrape}
              onClear={() => setPersistedFeed([])}
              scraping={scraping}
              scrapeError={scrapeError}
              prefs={prefs}
              onPrefsChange={setPrefs}
              boardStatuses={boardStatuses}
              runStatus={runStatus}
            />
          ) : (
            <CampaignSettings campaignId={campaignId} onGoToGlobalSettings={onGoToSettings} />
          )}
        </div>
      </div>
      )}
    </div>

    {/* "Did you apply?" popup */}
    {showDidYouApply && prevApplicationId && (() => {
      const app = pipeline.find((a) => a.applicationId === prevApplicationId)
      if (!app) return null
      return (
        <DidYouApplyPopup
          campaignId={campaignId}
          applicationId={prevApplicationId}
          company={app.company}
          title={app.title}
          onDone={handleDidYouApplyDone}
          onDismiss={() => { setShowDidYouApply(false); setPrevApplicationId(null) }}
        />
      )
    })()}
    </div>
  )
}
