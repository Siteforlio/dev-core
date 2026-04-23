import { useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'

interface Props {
  campaignId: string
  applicationId: string
  company: string
  title: string
  onDone: (status: 'applied' | 'failed' | 'withdrawn') => void
  onDismiss: () => void
}

export default function DidYouApplyPopup({ campaignId, applicationId, company, title, onDone, onDismiss }: Props) {
  const { patchApplicationStatus } = useJobHunter()
  const [loading, setLoading] = useState(false)
  const [notes, setNotes] = useState('')

  const handleChoice = async (status: 'applied' | 'failed' | 'withdrawn') => {
    setLoading(true)
    try {
      await patchApplicationStatus(campaignId, applicationId, status, notes || undefined)
      onDone(status)
    } catch {
      // still close — don't block user
      onDone(status)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center pb-6 px-4 pointer-events-none">
      <div className="bg-[#101010] border border-[#1c1c1c] rounded-xl shadow-2xl w-full max-w-sm pointer-events-auto">
        <div className="px-5 pt-5 pb-4">
          <p className="text-sm font-semibold text-[#e0e0e0] mb-0.5">Did you apply?</p>
          <p className="text-[12px] text-[#555]">{company} · {title}</p>
        </div>

        <div className="px-5 pb-3">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Any notes? (optional)"
            rows={2}
            className="w-full bg-[#0a0a0a] border border-[#1c1c1c] rounded-lg px-3 py-2 text-[12px] text-[#c0c0c0] placeholder-[#333] resize-none outline-none focus:border-[#2a2a2a] font-[inherit]"
          />
        </div>

        <div className="flex items-center gap-2 px-5 pb-5">
          <button
            onClick={() => handleChoice('applied')}
            disabled={loading}
            className="flex-1 py-2 rounded-lg text-[12px] font-semibold bg-[#1a2e1a] border border-[#1e3a1e] text-[#34d399] hover:bg-[#1f3a1f] transition-all disabled:opacity-50"
          >
            Yes, applied
          </button>
          <button
            onClick={() => handleChoice('failed')}
            disabled={loading}
            className="flex-1 py-2 rounded-lg text-[12px] font-medium bg-transparent border border-[#1c1c1c] text-[#555] hover:text-[#888] hover:border-[#2a2a2a] transition-all disabled:opacity-50"
          >
            Failed / skipped
          </button>
          <button
            onClick={onDismiss}
            disabled={loading}
            className="py-2 px-3 rounded-lg text-[12px] text-[#444] hover:text-[#666] transition-colors disabled:opacity-50"
          >
            Later
          </button>
        </div>
      </div>
    </div>
  )
}
