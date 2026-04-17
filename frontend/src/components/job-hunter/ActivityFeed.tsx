import { useEffect, useRef, useState } from 'react'
import type { ActivityMessage } from '../../hooks/useCampaignActivity'

interface Props {
  feed: ActivityMessage[]
  onTriggerScrape?: () => void
  onClear?: () => void
  scraping?: boolean
  scrapeError?: string
}

type FeedTab = 'all' | 'linkedin'

export default function ActivityFeed({ feed, onTriggerScrape, onClear, scraping, scrapeError }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [tab, setTab] = useState<FeedTab>('all')

  const linkedinMessages = feed.filter((m) =>
    m.text.toLowerCase().includes('linkedin')
  )

  const visible = tab === 'linkedin' ? linkedinMessages : feed

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [visible])

  return (
    <div className="flex flex-col min-h-0 flex-1 gap-2">
      {/* Top bar */}
      <div className="flex items-center justify-between flex-shrink-0">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Live Activity</h3>
        <div className="flex items-center gap-1.5">
          {onClear && feed.length > 0 && (
            <button
              onClick={onClear}
              className="text-xs text-gray-600 hover:text-gray-400 transition-colors px-1.5 py-1 rounded hover:bg-gray-800"
              title="Clear activity log"
            >
              Clear
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

      {/* Tab filter */}
      <div className="flex gap-1 flex-shrink-0">
        {(['all', 'linkedin'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`text-xs px-2.5 py-0.5 rounded-full transition-colors ${
              tab === t
                ? 'bg-gray-700 text-white'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {t === 'all' ? `All (${feed.length})` : `LinkedIn (${linkedinMessages.length})`}
          </button>
        ))}
      </div>

      {scrapeError && (
        <div className="flex-shrink-0 bg-red-950 border border-red-800 rounded-lg px-3 py-2 text-xs text-red-300">
          {scrapeError}
        </div>
      )}

      <div className="flex-1 overflow-y-auto min-h-0 scrollbar-none [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {visible.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-600 text-sm text-center">
              {tab === 'linkedin'
                ? 'No LinkedIn activity yet'
                : scraping
                ? 'Scraping in progress…'
                : 'No activity yet — hit Run Scrape to start'}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5 text-xs font-mono">
            {visible.map((msg) => (
              <div key={msg.id} className="flex gap-2 items-start">
                <span className="text-gray-600 flex-shrink-0 tabular-nums">{msg.timestamp.toLocaleTimeString()}</span>
                <span className={`leading-relaxed break-words min-w-0 ${
                  msg.text.startsWith('❌') ? 'text-red-400' :
                  msg.text.startsWith('✅') ? 'text-green-400' :
                  msg.text.startsWith('⚠️') ? 'text-yellow-400' :
                  'text-gray-300'
                }`}>{msg.text}</span>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
    </div>
  )
}
