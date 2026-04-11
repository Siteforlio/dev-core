import type { CampaignSummary } from '../../types/jobHunter'

interface Props {
  summary: CampaignSummary
}

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
}

function StatCard({ label, value, sub }: StatCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex flex-col gap-1">
      <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold text-white">{value}</span>
      {sub && <span className="text-xs text-gray-600">{sub}</span>}
    </div>
  )
}

export default function SummaryStrip({ summary }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <StatCard label="Total Sent" value={summary.totalApplications} sub={`${summary.todayApplications} today`} />
      <StatCard label="This Week" value={summary.weekApplications} />
      <StatCard label="Responses" value={summary.responses} />
      <StatCard label="Interviews" value={summary.interviews} />
      <StatCard label="Offers" value={summary.offers} />
      <StatCard label="Rejection Rate" value={`${summary.rejectionRate}%`} />
    </div>
  )
}
