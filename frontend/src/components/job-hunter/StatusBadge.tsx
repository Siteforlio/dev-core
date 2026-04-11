interface MatchScoreProps {
  variant: 'matchScore'
  value: 'MATCH' | 'PARTIAL' | 'SKIP' | null
}

interface StatusProps {
  variant: 'status'
  value: string
}

type Props = MatchScoreProps | StatusProps

const MATCH_COLORS: Record<string, string> = {
  MATCH: 'bg-green-900/60 text-green-300 border border-green-700',
  PARTIAL: 'bg-yellow-900/60 text-yellow-300 border border-yellow-700',
  SKIP: 'bg-gray-800 text-gray-500 border border-gray-700',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-800 text-gray-400 border border-gray-700',
  applied: 'bg-blue-900/60 text-blue-300 border border-blue-700',
  responded: 'bg-cyan-900/60 text-cyan-300 border border-cyan-700',
  interview: 'bg-purple-900/60 text-purple-300 border border-purple-700',
  offer: 'bg-green-900/60 text-green-300 border border-green-700',
  rejected: 'bg-red-900/60 text-red-300 border border-red-700',
  failed: 'bg-red-900/40 text-red-400 border border-red-800',
  withdrawn: 'bg-gray-800 text-gray-500 border border-gray-700',
  active: 'bg-green-900/60 text-green-300 border border-green-700',
  paused: 'bg-yellow-900/60 text-yellow-300 border border-yellow-700',
  archived: 'bg-gray-800 text-gray-500 border border-gray-700',
}

export default function StatusBadge(props: Props) {
  const { variant, value } = props
  if (!value) return null

  const colorClass =
    variant === 'matchScore'
      ? (MATCH_COLORS[value] ?? MATCH_COLORS.SKIP)
      : (STATUS_COLORS[value] ?? 'bg-gray-800 text-gray-400 border border-gray-700')

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}
    >
      {value}
    </span>
  )
}
