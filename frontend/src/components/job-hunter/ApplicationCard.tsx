import StatusBadge from './StatusBadge'
import type { Application } from '../../types/jobHunter'

interface Props {
  application: Application
  onStartInterviewPrep: (applicationId: string) => void
}

export default function ApplicationCard({ application, onStartInterviewPrep }: Props) {
  const { id, company, title, location, appliedAt, status, matchScore } = application
  const showInterviewPrep = status === 'interview'
  const appliedDate = appliedAt ? new Date(appliedAt).toLocaleDateString() : '—'

  return (
    <div className="flex items-center justify-between px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg hover:border-gray-700 transition-colors">
      <div className="flex items-center gap-4 min-w-0">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white truncate">{company}</p>
          <p className="text-xs text-gray-400 truncate">{title}</p>
        </div>
        <div className="hidden sm:flex items-center gap-2 flex-shrink-0">
          {matchScore && <StatusBadge variant="matchScore" value={matchScore} />}
          <StatusBadge variant="status" value={status} />
        </div>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
        <span className="text-xs text-gray-500 hidden md:block">{location}</span>
        <span className="text-xs text-gray-600 hidden lg:block">{appliedDate}</span>
        {showInterviewPrep && (
          <button
            onClick={() => onStartInterviewPrep(id)}
            className="text-xs bg-purple-600 hover:bg-purple-700 text-white px-3 py-1.5 rounded font-medium transition-colors whitespace-nowrap"
          >
            Interview Prep
          </button>
        )}
      </div>
    </div>
  )
}
