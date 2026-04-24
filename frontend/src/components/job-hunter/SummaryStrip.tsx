import type { CampaignSummary } from '../../types/jobHunter'

interface Props {
  summary: CampaignSummary
  compact?: boolean
}

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  compact?: boolean
}

function StatCard({ label, value, sub, compact }: StatCardProps) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-lg flex flex-col gap-0.5 ${compact ? 'px-2 py-2' : 'px-4 py-3 gap-1'}`}>
      <span className={`text-gray-500 uppercase tracking-wide ${compact ? 'text-[9px]' : 'text-xs'}`}>{label}</span>
      <span className={`font-bold text-white ${compact ? 'text-lg' : 'text-2xl'}`}>{value}</span>
      {sub && !compact && <span className="text-xs text-gray-600">{sub}</span>}
    </div>
  )
}

export default function SummaryStrip({ summary, compact }: Props) {
  return (
    <div className={`grid gap-3 ${compact ? 'grid-cols-3' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-6'}`}>
      <StatCard label="Total Sent" value={summary.totalApplications} sub={`${summary.todayApplications} today`} compact={compact} />
      <StatCard label="This Week" value={summary.weekApplications} compact={compact} />
      <StatCard label="Responses" value={summary.responses} compact={compact} />
      <StatCard label="Interviews" value={summary.interviews} compact={compact} />
      <StatCard label="Offers" value={summary.offers} compact={compact} />
      <StatCard label="Rejection Rate" value={`${summary.rejectionRate}%`} compact={compact} />
    </div>
  )
}
