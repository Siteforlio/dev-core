import { useEffect, useRef, useState } from 'react'
import type { ActivityMessage } from '../../hooks/useCampaignActivity'
import type { BoardStatus, ScrapePreferences, ScrapeRunStatus } from '../../types/jobHunter'

interface Props {
  feed: ActivityMessage[]
  onTriggerScrape?: () => void
  onClear?: () => void
  scraping?: boolean
  scrapeError?: string
  prefs?: ScrapePreferences
  onPrefsChange?: (p: ScrapePreferences) => void
  boardStatuses?: Record<string, BoardStatus>
  runStatus?: ScrapeRunStatus | null
}

const COMPANY_TYPE_OPTS = [
  { id: 'faang',      label: 'FAANG' },
  { id: 'enterprise', label: 'Enterprise' },
  { id: 'startup',    label: 'Startup' },
  { id: 'sme',        label: 'SME' },
] as const

const WORK_TYPE_OPTS = [
  { id: 'any',    label: 'Any' },
  { id: 'remote', label: 'Remote' },
  { id: 'hybrid', label: 'Hybrid' },
  { id: 'onsite', label: 'Onsite' },
] as const

const REGION_OPTS = [
  { id: 'global', label: 'Global' },
  { id: 'africa', label: 'Africa' },
  { id: 'kenya',  label: 'Kenya' },
] as const

const BOARD_DISPLAY: Record<string, string> = {
  indeed: 'Indeed', glassdoor: 'Glassdoor', zip_recruiter: 'ZipRecruiter',
  google: 'Google', greenhouse: 'Greenhouse', lever: 'Lever', ashby: 'Ashby',
  remotive: 'Remotive', remoteok: 'RemoteOK', hn_hiring: 'HN Hiring',
  weworkremotely: 'WWR', zindi: 'Zindi', startupdeals_africa: 'SD Africa',
  fuzu: 'Fuzu', brightermonday: 'BrighterMonday', myjobmag: 'MyJobMag',
  kuhustle: 'Kuhustle', andela: 'Andela', arc: 'Arc.dev', linkedin: 'LinkedIn',
}

function StatusDot({ status }: { status: BoardStatus['status'] }) {
  const cls = {
    idle:    'bg-gray-600',
    queued:  'bg-yellow-500 animate-pulse',
    running: 'bg-blue-500 animate-pulse',
    done:    'bg-green-500',
    failed:  'bg-red-500',
  }[status]
  return <span className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${cls}`} />
}

export default function ActivityFeed({
  feed, onTriggerScrape, onClear, scraping, scrapeError,
  prefs, onPrefsChange, boardStatuses = {}, runStatus,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [showPrefs, setShowPrefs] = useState(false)

  const activeBoardIds = Object.keys(boardStatuses)
  const hasStatus = activeBoardIds.length > 0

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [feed])

  function toggleCompanyType(id: string) {
    if (!prefs || !onPrefsChange) return
    const ct = prefs.companyTypes as string[]
    onPrefsChange({
      ...prefs,
      companyTypes: ct.includes(id)
        ? ct.filter((x) => x !== id)
        : [...ct, id] as ScrapePreferences['companyTypes'],
    })
  }

  function toggleRegion(id: string) {
    if (!prefs || !onPrefsChange) return
    const rs = prefs.regions as string[]
    onPrefsChange({
      ...prefs,
      regions: rs.includes(id)
        ? rs.filter((x) => x !== id)
        : [...rs, id] as ScrapePreferences['regions'],
    })
  }

  return (
    <div className="flex flex-col min-h-0 flex-1 gap-2">

      {/* ── Top bar ── */}
      <div className="flex items-center justify-between flex-shrink-0">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Live Activity</h3>
        <div className="flex items-center gap-1.5">
          {onClear && feed.length > 0 && (
            <button
              onClick={onClear}
              className="text-xs text-gray-600 hover:text-gray-400 transition-colors px-1.5 py-1 rounded hover:bg-gray-800"
            >
              Clear
            </button>
          )}
          {onPrefsChange && (
            <button
              onClick={() => setShowPrefs((v) => !v)}
              title="Scrape settings"
              className={`text-xs px-1.5 py-1 rounded transition-colors ${
                showPrefs ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
              }`}
            >
              ⚙
            </button>
          )}
          {onTriggerScrape && (
            <button
              onClick={onTriggerScrape}
              disabled={scraping}
              className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-2.5 py-1 rounded font-medium transition-colors flex items-center gap-1.5"
            >
              {scraping && (
                <span className="w-2.5 h-2.5 border border-white border-t-transparent rounded-full animate-spin" />
              )}
              {scraping ? 'Scraping…' : 'Run Scrape'}
            </button>
          )}
        </div>
      </div>

      {/* ── Preferences panel ── */}
      {showPrefs && prefs && onPrefsChange && (
        <div className="flex-shrink-0 bg-gray-900 border border-gray-700 rounded-lg p-3 flex flex-col gap-3">

          {/* Company type */}
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1.5">Company type</p>
            <div className="flex flex-wrap gap-1">
              {COMPANY_TYPE_OPTS.map(({ id, label }) => {
                const active = (prefs.companyTypes as string[]).includes(id)
                return (
                  <button
                    key={id}
                    onClick={() => toggleCompanyType(id)}
                    className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${
                      active
                        ? 'bg-blue-600 border-blue-500 text-white'
                        : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
                    }`}
                  >
                    {label}
                  </button>
                )
              })}
              {prefs.companyTypes.length > 0 && (
                <button
                  onClick={() => onPrefsChange({ ...prefs, companyTypes: [] })}
                  className="text-[11px] px-2 py-0.5 text-gray-600 hover:text-gray-400"
                >
                  clear
                </button>
              )}
            </div>
          </div>

          {/* Work type */}
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1.5">Work type</p>
            <div className="flex gap-1">
              {WORK_TYPE_OPTS.map(({ id, label }) => (
                <button
                  key={id}
                  onClick={() => onPrefsChange({ ...prefs, workType: id })}
                  className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${
                    prefs.workType === id
                      ? 'bg-blue-600 border-blue-500 text-white'
                      : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Regions */}
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1.5">
              Location <span className="normal-case text-gray-600">(empty = anywhere)</span>
            </p>
            <div className="flex gap-1">
              {REGION_OPTS.map(({ id, label }) => {
                const active = (prefs.regions as string[]).includes(id)
                return (
                  <button
                    key={id}
                    onClick={() => toggleRegion(id)}
                    className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${
                      active
                        ? 'bg-blue-600 border-blue-500 text-white'
                        : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
                    }`}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Daily target */}
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1.5">
              Daily target: <span className="text-white">{prefs.dailyTarget}</span> jobs
            </p>
            <input
              type="range"
              min={10}
              max={100}
              step={10}
              value={prefs.dailyTarget}
              onChange={(e) => onPrefsChange({ ...prefs, dailyTarget: Number(e.target.value) })}
              className="w-full accent-blue-500"
            />
            <div className="flex justify-between text-[10px] text-gray-600 mt-0.5">
              <span>10</span><span>100</span>
            </div>
          </div>
        </div>
      )}

      {/* ── Per-board status grid ── */}
      {hasStatus && (
        <div className="flex-shrink-0">
          {runStatus && (
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-[10px] text-gray-500 uppercase tracking-wide">
                Round {runStatus.round}
              </p>
              <p className="text-[10px] text-gray-400">
                {runStatus.matches} matches
                {runStatus.status === 'running' && (
                  <span className="ml-1.5 inline-block w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
                )}
              </p>
            </div>
          )}
          <div className="grid grid-cols-2 gap-1">
            {activeBoardIds.map((boardId) => {
              const bs = boardStatuses[boardId]
              return (
                <div
                  key={boardId}
                  className={`flex items-center gap-1.5 px-2 py-1.5 rounded border text-[11px] ${
                    bs.status === 'failed'
                      ? 'border-red-900 bg-red-950/30'
                      : bs.status === 'done'
                      ? 'border-green-900/50 bg-green-950/20'
                      : bs.status === 'running'
                      ? 'border-blue-900/50 bg-blue-950/20'
                      : 'border-gray-800 bg-gray-900/50'
                  }`}
                  title={bs.error ?? undefined}
                >
                  <StatusDot status={bs.status} />
                  <span className="text-gray-300 truncate flex-1 min-w-0">
                    {BOARD_DISPLAY[boardId] ?? boardId}
                  </span>
                  {bs.status === 'done' && (
                    <span className="text-green-400 flex-shrink-0">{bs.count}</span>
                  )}
                  {bs.status === 'failed' && (
                    <span className="text-red-400 flex-shrink-0">!</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {scrapeError && (
        <div className="flex-shrink-0 bg-red-950 border border-red-800 rounded-lg px-3 py-2 text-xs text-red-300">
          {scrapeError}
        </div>
      )}

      {/* ── Activity log ── */}
      <div className="flex-1 overflow-y-auto min-h-0 scrollbar-none [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {feed.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-600 text-sm text-center">
              {scraping ? 'Scraping in progress…' : 'No activity yet — hit Run Scrape to start'}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5 text-xs font-mono">
            {feed.map((msg) => (
              <div key={msg.id} className="flex gap-2 items-start">
                <span className="text-gray-600 flex-shrink-0 tabular-nums">
                  {msg.timestamp.toLocaleTimeString()}
                </span>
                <span className={`leading-relaxed break-words min-w-0 ${
                  msg.text.startsWith('❌') ? 'text-red-400' :
                  msg.text.startsWith('✅') ? 'text-green-400' :
                  msg.text.startsWith('⚠️') ? 'text-yellow-400' :
                  msg.text.startsWith('🟡') ? 'text-yellow-300' :
                  'text-gray-300'
                }`}>
                  {msg.text}
                </span>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
    </div>
  )
}
