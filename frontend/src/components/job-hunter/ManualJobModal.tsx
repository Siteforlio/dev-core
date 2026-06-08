import { useEffect, useRef, useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'

interface Props {
  campaignId: string
  onClose: () => void
  onAdded: () => void
}

type Step = 'compose' | 'sending' | 'done' | 'error'

export default function ManualJobModal({ campaignId, onClose, onAdded }: Props) {
  const { addManualJob } = useJobHunter()

  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [description, setDescription] = useState('')
  const [applyUrl, setApplyUrl] = useState('')
  const [step, setStep] = useState<Step>('compose')
  const [errorMsg, setErrorMsg] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Focus the title on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      document.getElementById('mjm-title')?.focus()
    }, 80)
    return () => clearTimeout(timer)
  }, [])

  const canSubmit = title.trim().length > 0 && company.trim().length > 0 && description.trim().length > 30

  async function handleSubmit() {
    if (!canSubmit || step !== 'compose') return
    setStep('sending')
    setErrorMsg('')
    try {
      await addManualJob(campaignId, {
        title: title.trim(),
        company: company.trim(),
        description: description.trim(),
        applyUrl: applyUrl.trim() || undefined,
      })
      setStep('done')
      // Give user a moment to see success, then close and refresh
      setTimeout(() => {
        onAdded()
        onClose()
      }, 1400)
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Something went wrong')
      setStep('error')
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') onClose()
    // Ctrl/Cmd+Enter to submit from the description textarea
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleSubmit()
  }

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      onKeyDown={handleKeyDown}
    >
      <div
        className="w-full max-w-xl flex flex-col rounded-2xl overflow-hidden"
        style={{
          background: '#0d0d0d',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.7)',
          maxHeight: '90vh',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 flex-shrink-0">
          <div>
            <h2 className="text-white font-semibold text-sm">Add a Job Manually</h2>
            <p className="text-gray-500 text-xs mt-0.5">Paste the JD — we'll tailor your resume for it</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-600 hover:text-white transition-colors p-1 rounded-md hover:bg-gray-800"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="border-t border-gray-900 mx-5" />

        {/* Form body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">

          {/* Title + Company row */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-[10px] font-semibold uppercase tracking-widest text-gray-600 mb-1.5">
                Job Title <span className="text-red-500">*</span>
              </label>
              <input
                id="mjm-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Senior Backend Engineer"
                disabled={step !== 'compose'}
                className="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-gray-600 transition-colors disabled:opacity-50"
              />
            </div>
            <div className="flex-1">
              <label className="block text-[10px] font-semibold uppercase tracking-widest text-gray-600 mb-1.5">
                Company <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="e.g. Stripe"
                disabled={step !== 'compose'}
                className="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-gray-600 transition-colors disabled:opacity-50"
              />
            </div>
          </div>

          {/* Job description — the main paste area */}
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-widest text-gray-600 mb-1.5">
              Job Description <span className="text-red-500">*</span>
            </label>
            <textarea
              ref={textareaRef}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={"Paste the full job description here…\n\nThe more detail you include, the better we can tailor your resume."}
              rows={10}
              disabled={step !== 'compose'}
              className="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-gray-600 transition-colors resize-none disabled:opacity-50 leading-relaxed"
              style={{ fontFamily: 'inherit' }}
            />
            <p className="text-[10px] text-gray-700 mt-1">
              {description.length > 0 ? `${description.length} chars` : 'Ctrl+Enter to send'}
            </p>
          </div>

          {/* Apply URL — optional */}
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-widest text-gray-600 mb-1.5">
              Apply URL <span className="text-gray-700 normal-case tracking-normal font-normal">(optional)</span>
            </label>
            <input
              type="url"
              value={applyUrl}
              onChange={(e) => setApplyUrl(e.target.value)}
              placeholder="https://jobs.company.com/..."
              disabled={step !== 'compose'}
              className="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-gray-600 transition-colors disabled:opacity-50"
            />
          </div>

          {/* Error message */}
          {step === 'error' && (
            <div className="rounded-lg px-3 py-2.5 text-xs text-red-300" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
              {errorMsg}
              <button
                onClick={() => setStep('compose')}
                className="ml-2 underline text-red-400 hover:text-red-300"
              >
                Try again
              </button>
            </div>
          )}
        </div>

        {/* Footer / send button */}
        <div
          className="flex items-center justify-between px-5 py-4 flex-shrink-0"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
        >
          <p className="text-[10px] text-gray-700">
            Added as <span className="text-gray-500">MATCH</span> · resume tailored automatically
          </p>

          <button
            onClick={handleSubmit}
            disabled={!canSubmit || step !== 'compose'}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              background: step === 'done' ? 'rgba(34,197,94,0.15)' : 'rgba(59,130,246,0.15)',
              border: step === 'done' ? '1px solid rgba(34,197,94,0.3)' : '1px solid rgba(59,130,246,0.3)',
              color: step === 'done' ? '#86efac' : '#93c5fd',
            }}
          >
            {step === 'sending' && (
              <span className="w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            )}
            {step === 'done' && (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            )}
            {step === 'compose' && (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            )}
            {step === 'sending' ? 'Adding…' : step === 'done' ? 'Added!' : step === 'error' ? 'Retry' : 'Add Job'}
          </button>
        </div>
      </div>
    </div>
  )
}
