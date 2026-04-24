import StatusBadge from './StatusBadge'
import type { Application } from '../../types/jobHunter'

interface Props {
  application: Application
  onStartInterviewPrep: (applicationId: string) => void
  onApply: (applicationId: string) => void
  onViewTracking: (applicationId: string) => void
}

export default function ApplicationCard({ application, onStartInterviewPrep, onApply, onViewTracking }: Props) {
  const { id, company, title, location, appliedAt, status, matchScore } = application
  const isApplied = status === 'applied' || status === 'interview' || status === 'offer' || status === 'responded'
  const showInterviewPrep = status === 'interview'
  const appliedDate = appliedAt ? new Date(appliedAt).toLocaleDateString('en-GB') : null

  return (
    <div className="px-3 py-2.5 bg-gray-900 border border-gray-800 rounded-lg hover:border-gray-700 transition-colors">
      {/* Row 1: company + action button */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white leading-tight truncate">{company}</p>
          <p className="text-xs text-gray-400 leading-tight truncate">{title}</p>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {showInterviewPrep && (
            <button
              onClick={() => onStartInterviewPrep(id)}
              className="text-[11px] bg-purple-600 hover:bg-purple-700 text-white px-2 py-1 rounded font-medium transition-colors whitespace-nowrap"
            >
              Prep
            </button>
          )}
          {isApplied ? (
            <button
              onClick={() => onViewTracking(id)}
              className="text-[11px] bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 px-2.5 py-1 rounded font-medium transition-colors whitespace-nowrap"
            >
              Track →
            </button>
          ) : (
            <button
              onClick={() => onApply(id)}
              className="text-[11px] bg-blue-600/20 hover:bg-blue-600/30 border border-blue-600/40 text-blue-400 px-2.5 py-1 rounded font-medium transition-colors whitespace-nowrap"
            >
              Apply →
            </button>
          )}
        </div>
      </div>

      {/* Row 2: badges + meta */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {matchScore && <StatusBadge variant="matchScore" value={matchScore} />}
        <StatusBadge variant="status" value={status} />
        {location && (
          <span className="text-[10px] text-gray-600 truncate max-w-[120px]">{location}</span>
        )}
        {appliedDate && (
          <span className="text-[10px] text-gray-700 ml-auto flex-shrink-0">{appliedDate}</span>
        )}
      </div>
    </div>
  )
}
