import type { Campaign } from '../../types/jobHunter'
import StatusBadge from './StatusBadge'

interface Props {
  campaigns: Campaign[]
  onSelect: (campaignId: string) => void
  onCreateNew: () => void
}

export default function CampaignList({ campaigns, onSelect, onCreateNew }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white">Campaigns</h2>
        <button
          onClick={onCreateNew}
          className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          New Campaign
        </button>
      </div>

      {campaigns.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <p className="text-gray-500 text-sm">No campaigns yet</p>
          <button
            onClick={onCreateNew}
            className="text-sm text-blue-400 hover:text-blue-300 underline"
          >
            Create your first campaign
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {campaigns.map((c) => (
            <div
              key={c.id}
              className="flex items-center justify-between px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg hover:border-gray-700 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white">{c.name}</p>
                  <p className="text-xs text-gray-500">{c.broadCategory}</p>
                </div>
                <StatusBadge variant="status" value={c.status} />
              </div>
              <button
                onClick={() => onSelect(c.id)}
                className="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 px-3 py-1.5 rounded transition-colors flex-shrink-0 ml-4"
              >
                View
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
