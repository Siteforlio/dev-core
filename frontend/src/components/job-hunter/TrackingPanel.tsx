import { useEffect, useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'
import type { TrackingStatus } from '../../types/jobHunter'

interface Props {
  campaignId: string
  applicationId: string
  onClose: () => void
}

const CLASSIFICATION_COLORS: Record<string, string> = {
  response: 'text-[#34d399] border-[#1e3a2e] bg-[#0a1f12]',
  rejection: 'text-[#f87171] border-[#3a1e1e] bg-[#1f0a0a]',
  interview: 'text-[#a89ef5] border-[#2a2550] bg-[#13102a]',
  offer: 'text-[#fbbf24] border-[#3a2e0a] bg-[#1f1a0a]',
  default: 'text-[#555] border-[#1c1c1c] bg-transparent',
}

function classColor(cls: string) {
  return CLASSIFICATION_COLORS[cls?.toLowerCase()] ?? CLASSIFICATION_COLORS.default
}

export default function TrackingPanel({ campaignId, applicationId, onClose }: Props) {
  const { getTrackingStatus, scanEmails } = useJobHunter()
  const [tracking, setTracking] = useState<TrackingStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [scanning, setScanning] = useState(false)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const t = await getTrackingStatus(campaignId, applicationId)
      setTracking(t)
    } catch {
      setError('Failed to load tracking data.')
    } finally {
      setLoading(false)
    }
  }

  const handleCheckEmail = async () => {
    setScanning(true)
    try {
      await scanEmails(campaignId)
      const t = await getTrackingStatus(campaignId, applicationId)
      setTracking(t)
    } catch {
      // silent — still show last known state
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => { load() }, [applicationId])  // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-[#0a0a0a] items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !tracking) {
    return (
      <div className="flex flex-col h-full bg-[#0a0a0a] items-center justify-center gap-3">
        <p className="text-red-400 text-sm">{error || 'Not found'}</p>
        <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">Close</button>
      </div>
    )
  }

  const appliedDate = tracking.appliedAt
    ? new Date(tracking.appliedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    : null

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a] overflow-hidden">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#141414] flex-shrink-0">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] text-[#444] mb-0.5">{tracking.company}</p>
          <p className="text-base font-semibold text-[#efefef] truncate">{tracking.title}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-4">
          <button
            onClick={handleCheckEmail}
            disabled={scanning}
            className="text-[12px] px-3 py-1.5 rounded-md border border-[#1c1c1c] text-[#444] hover:text-[#888] hover:border-[#2a2a2a] transition-all disabled:opacity-50"
          >
            {scanning ? 'Scanning…' : 'Check email'}
          </button>
          <button onClick={onClose} className="text-[12px] px-2 py-1.5 text-[#444] hover:text-[#888] transition-colors">✕</button>
        </div>
      </div>

      {/* Status row */}
      <div className="px-6 py-4 border-b border-[#141414] flex-shrink-0 flex items-center gap-6">
        <div>
          <p className="text-[10px] text-[#383838] uppercase tracking-widest mb-1.5">Status</p>
          <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border capitalize ${
            tracking.status === 'applied'
              ? 'text-[#60a5fa] border-[#1e2a3a] bg-[#0a1220]'
              : tracking.status === 'interview'
              ? 'text-[#a89ef5] border-[#2a2550] bg-[#13102a]'
              : tracking.status === 'offer'
              ? 'text-[#fbbf24] border-[#3a2e0a] bg-[#1f1a0a]'
              : 'text-[#555] border-[#1c1c1c] bg-transparent'
          }`}>
            {tracking.status}
          </span>
        </div>
        {appliedDate && (
          <div>
            <p className="text-[10px] text-[#383838] uppercase tracking-widest mb-1.5">Applied</p>
            <p className="text-[12px] text-[#666]">{appliedDate}</p>
          </div>
        )}
        <div>
          <p className="text-[10px] text-[#383838] uppercase tracking-widest mb-1.5">Email signals</p>
          <p className="text-[12px] text-[#666]">{tracking.emailEvents.length} found</p>
        </div>
      </div>

      {/* Email events */}
      <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-2 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {tracking.emailEvents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <p className="text-[#333] text-sm">No emails detected yet.</p>
            <p className="text-[#2a2a2a] text-xs text-center max-w-xs">
              The system scans your inbox for messages from {tracking.company}. Check back after a few days.
            </p>
          </div>
        ) : (
          <>
            <p className="text-[10px] text-[#383838] uppercase tracking-widest mb-1">Email Activity</p>
            {tracking.emailEvents.map((event) => (
              <div key={event.id} className="bg-[#0f0f0f] border border-[#171717] rounded-lg px-4 py-3">
                <div className="flex items-start justify-between gap-3 mb-1.5">
                  <p className="text-[13px] text-[#ccc] font-medium leading-snug flex-1">{event.subject}</p>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border flex-shrink-0 capitalize ${classColor(event.classification)}`}>
                    {event.classification}
                  </span>
                </div>
                <p className="text-[11px] text-[#444]">{event.sender}</p>
                <p className="text-[11px] text-[#333] mt-0.5">
                  {new Date(event.receivedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                </p>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
