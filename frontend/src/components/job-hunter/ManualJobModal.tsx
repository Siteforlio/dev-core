import { useEffect, useRef, useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'

interface Props {
  campaignId: string
  onClose: () => void
  onAdded: (listingId: string) => void
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
      const { listingId } = await addManualJob(campaignId, {
        title: title.trim(),
        company: company.trim(),
        description: description.trim(),
        applyUrl: applyUrl.trim() || undefined,
      })
      setStep('done')
      setTimeout(() => {
        onAdded(listingId)
      }, 800)
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Something went wrong')
      setStep('error')
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') onClose()
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleSubmit()
  }

  const charCount = description.length
  const charColor = charCount > 9000 ? '#f87171' : charCount > 7000 ? '#fbbf24' : 'rgba(100,116,139,0.5)'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      onKeyDown={handleKeyDown}
    >
      <div
        className="w-full max-w-2xl flex flex-col rounded-2xl overflow-hidden"
        style={{
          background: 'linear-gradient(160deg, #0d1117 0%, #0a0e14 100%)',
          border: '1px solid rgba(255,255,255,0.07)',
          boxShadow: '0 32px 80px rgba(0,0,0,0.8), 0 0 0 1px rgba(34,211,238,0.04)',
          maxHeight: '92vh',
        }}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div
              className="flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0"
              style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.15)' }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="18" x2="12" y2="12" />
                <line x1="9" y1="15" x2="15" y2="15" />
              </svg>
            </div>
            <div>
              <h2 className="text-white font-semibold text-sm tracking-tight">Add Job</h2>
              <p className="text-[11px] mt-0.5" style={{ color: 'rgba(100,116,139,0.7)' }}>
                Paste the JD — AI will tailor your resume and open the apply screen
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-600 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-gray-800 flex-shrink-0"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div style={{ height: '1px', background: 'rgba(255,255,255,0.05)', margin: '0 24px' }} />

        {/* Form */}
        <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">

          {/* Title + Company */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-[10px] font-semibold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(100,116,139,0.6)' }}>
                Job Title <span className="text-red-500">*</span>
              </label>
              <input
                id="mjm-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Content Marketing Lead"
                disabled={step !== 'compose'}
                className="w-full rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none transition-colors disabled:opacity-50"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.07)',
                }}
                onFocus={e => e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)'}
                onBlur={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'}
              />
            </div>
            <div className="flex-1">
              <label className="block text-[10px] font-semibold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(100,116,139,0.6)' }}>
                Company <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="e.g. Bridge"
                disabled={step !== 'compose'}
                className="w-full rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none transition-colors disabled:opacity-50"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.07)',
                }}
                onFocus={e => e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)'}
                onBlur={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'}
              />
            </div>
          </div>

          {/* Job description */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'rgba(100,116,139,0.6)' }}>
                Job Description <span className="text-red-500">*</span>
              </label>
              {charCount > 0 && (
                <span className="text-[10px] font-mono" style={{ color: charColor }}>
                  {charCount.toLocaleString()} / 10,000
                </span>
              )}
            </div>
            <textarea
              ref={textareaRef}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={"Paste the full job description here…\n\nThe more detail you include, the better we can tailor your resume."}
              rows={11}
              disabled={step !== 'compose'}
              className="w-full rounded-lg px-3 py-3 text-sm text-white placeholder-gray-600 focus:outline-none transition-colors resize-none disabled:opacity-50 leading-relaxed"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
                fontFamily: 'inherit',
              }}
              onFocus={e => e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)'}
              onBlur={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'}
            />
            {charCount === 0 && (
              <p className="text-[10px] mt-1" style={{ color: 'rgba(100,116,139,0.4)' }}>
                Ctrl+Enter to submit
              </p>
            )}
          </div>

          {/* Apply URL */}
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(100,116,139,0.6)' }}>
              Apply URL{' '}
              <span className="normal-case tracking-normal font-normal" style={{ color: 'rgba(100,116,139,0.4)' }}>(optional)</span>
            </label>
            <input
              type="url"
              value={applyUrl}
              onChange={(e) => setApplyUrl(e.target.value)}
              placeholder="https://jobs.company.com/…"
              disabled={step !== 'compose'}
              className="w-full rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none transition-colors disabled:opacity-50"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
              }}
              onFocus={e => e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)'}
              onBlur={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'}
            />
          </div>

          {/* Error */}
          {step === 'error' && (
            <div
              className="rounded-lg px-4 py-3 text-xs flex items-center gap-3"
              style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.18)', color: '#fca5a5' }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0">
                <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span className="flex-1">{errorMsg}</span>
              <button onClick={() => setStep('compose')} className="underline text-red-400 hover:text-red-300 flex-shrink-0">
                Try again
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between px-6 py-4 flex-shrink-0"
          style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
        >
          <div className="flex items-center gap-2">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: step === 'done' ? '#34d399' : step === 'sending' ? '#fbbf24' : 'rgba(34,211,238,0.4)' }}
            />
            <p className="text-[10px] font-mono" style={{ color: 'rgba(100,116,139,0.5)' }}>
              {step === 'done' ? 'Job added — opening panel…' : step === 'sending' ? 'Adding job…' : 'Added as MATCH · resume tailored on open'}
            </p>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!canSubmit || step !== 'compose'}
            className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              background: step === 'done'
                ? 'rgba(52,211,153,0.12)'
                : 'rgba(34,211,238,0.1)',
              border: step === 'done'
                ? '1px solid rgba(52,211,153,0.3)'
                : '1px solid rgba(34,211,238,0.25)',
              color: step === 'done' ? '#6ee7b7' : '#67e8f9',
            }}
          >
            {step === 'sending' && (
              <span className="w-3.5 h-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            )}
            {step === 'done' && (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
            {step === 'compose' && (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
              </svg>
            )}
            {step === 'sending' ? 'Adding…' : step === 'done' ? 'Done!' : 'Add Job'}
          </button>
        </div>
      </div>
    </div>
  )
}
