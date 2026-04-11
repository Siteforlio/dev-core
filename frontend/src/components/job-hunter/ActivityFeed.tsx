import type { ActivityMessage } from '../../hooks/useCampaignActivity'

interface Props {
  feed: ActivityMessage[]
}

export default function ActivityFeed({ feed }: Props) {
  return (
    <div className="flex flex-col h-full">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Live Activity</h3>
      {feed.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-600 text-sm">No activity yet</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto flex flex-col gap-2">
          {feed.map((msg) => (
            <div
              key={msg.id}
              className="flex flex-col gap-0.5 p-2 bg-gray-900/50 rounded border border-gray-800/50"
            >
              <p className="text-xs text-gray-300 leading-relaxed">{msg.text}</p>
              <span className="text-[10px] text-gray-600">{msg.timestamp.toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
