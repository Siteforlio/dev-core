import { forwardRef, useEffect, useRef, useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'

interface Props {
  campaignId: string
  onClose: () => void
  onAdded: (listingId: string) => void
}

type Tab = 'fetch' | 'manual'
type Step = 'idle' | 'loading' | 'preview' | 'saving' | 'done' | 'error'

interface FetchedJob {
  title: string
  company: string
  description: string
  date_posted: string | null
  location: string | null
  remote: boolean
  apply_url: string
}

/* ── Shared input style helpers ── */
const inputBase: React.CSSProperties = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(255,255,255,0.07)',
  borderRadius: '8px',
  padding: '10px 12px',
  fontSize: '13px',
  color: '#e2e8f0',
  width: '100%',
  outline: 'none',
  fontFamily: 'inherit',
  transition: 'border-color 0.15s',
}

function Field({ label, required, hint, children }: { label: string; required?: boolean; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
        <span style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.6)' }}>
          {label}
        </span>
        {required && <span style={{ color: '#f87171', fontSize: '10px' }}>*</span>}
        {hint && <span style={{ fontSize: '10px', color: 'rgba(100,116,139,0.4)' }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}

const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input(props, ref) {
  const [focused, setFocused] = useState(false)
  return (
    <input
      ref={ref}
      {...props}
      style={{ ...inputBase, borderColor: focused ? 'rgba(34,211,238,0.35)' : 'rgba(255,255,255,0.07)', ...props.style }}
      onFocus={e => { setFocused(true); props.onFocus?.(e) }}
      onBlur={e => { setFocused(false); props.onBlur?.(e) }}
    />
  )
})

function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const [focused, setFocused] = useState(false)
  return (
    <textarea
      {...props}
      style={{ ...inputBase, resize: 'none', lineHeight: 1.6, borderColor: focused ? 'rgba(34,211,238,0.35)' : 'rgba(255,255,255,0.07)', ...props.style }}
      onFocus={e => { setFocused(true); props.onFocus?.(e) }}
      onBlur={e => { setFocused(false); props.onBlur?.(e) }}
    />
  )
}

function ActionBtn({ onClick, disabled, loading, done, children }: {
  onClick: () => void; disabled?: boolean; loading?: boolean; done?: boolean; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        display: 'flex', alignItems: 'center', gap: '7px',
        padding: '8px 18px', borderRadius: '8px',
        background: done ? 'rgba(52,211,153,0.1)' : 'rgba(34,211,238,0.1)',
        border: `1px solid ${done ? 'rgba(52,211,153,0.3)' : 'rgba(34,211,238,0.25)'}`,
        color: done ? '#6ee7b7' : '#67e8f9',
        fontSize: '13px', fontWeight: 500, cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled && !loading ? 0.35 : 1,
        transition: 'all 0.15s',
      }}
    >
      {loading && <span style={{ width: 13, height: 13, border: '2px solid rgba(34,211,238,0.3)', borderTopColor: '#22d3ee', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />}
      {done && <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>}
      {children}
    </button>
  )
}

export default function ManualJobModal({ campaignId, onClose, onAdded }: Props) {
  const { addManualJob, fetchJobFromUrl } = useJobHunter()
  const [tab, setTab] = useState<Tab>('fetch')
  const [step, setStep] = useState<Step>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  // Fetch tab state
  const [fetchUrl, setFetchUrl] = useState('')
  const [fetched, setFetched] = useState<FetchedJob | null>(null)

  // Manual tab state
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [description, setDescription] = useState('')
  const [applyUrl, setApplyUrl] = useState('')

  const urlInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const t = setTimeout(() => urlInputRef.current?.focus(), 80)
    return () => clearTimeout(t)
  }, [tab]) // re-focus when tab changes

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') onClose()
  }

  /* ── Fetch tab ── */
  async function handleFetch() {
    const url = fetchUrl.trim()
    if (!url) return
    setStep('loading')
    setErrorMsg('')
    setFetched(null)
    try {
      const data = await fetchJobFromUrl(campaignId, url)
      setFetched(data)
      setStep('preview')
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Failed to fetch job')
      setStep('error')
    }
  }

  async function handleSaveFetched() {
    if (!fetched) return
    setStep('saving')
    try {
      const { listingId } = await addManualJob(campaignId, {
        title: fetched.title,
        company: fetched.company,
        description: fetched.description,
        applyUrl: fetched.apply_url,
        location: fetched.location ?? undefined,
      })
      setStep('done')
      setTimeout(() => onAdded(listingId), 700)
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Failed to save job')
      setStep('error')
    }
  }

  /* ── Manual tab ── */
  const canManualSubmit = title.trim().length > 0 && company.trim().length > 0 && description.trim().length > 30

  async function handleManualSubmit() {
    if (!canManualSubmit) return
    setStep('saving')
    setErrorMsg('')
    try {
      const { listingId } = await addManualJob(campaignId, {
        title: title.trim(),
        company: company.trim(),
        description: description.trim(),
        applyUrl: applyUrl.trim() || undefined,
      })
      setStep('done')
      setTimeout(() => onAdded(listingId), 700)
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Something went wrong')
      setStep('error')
    }
  }

  const isWorking = step === 'loading' || step === 'saving'

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16, background: 'rgba(0,0,0,0.78)', backdropFilter: 'blur(6px)' }}
        onClick={e => { if (e.target === e.currentTarget) onClose() }}
        onKeyDown={handleKeyDown}
      >
        <div
          style={{
            width: '100%', maxWidth: 640, maxHeight: '92vh',
            display: 'flex', flexDirection: 'column',
            background: 'linear-gradient(160deg, #0d1117 0%, #0a0e14 100%)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: 18,
            boxShadow: '0 32px 80px rgba(0,0,0,0.8), 0 0 0 1px rgba(34,211,238,0.04)',
            animation: 'fadeUp 0.18s ease-out',
          }}
        >
          {/* ── Header ── */}
          <div style={{ padding: '22px 24px 16px', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                    <line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/>
                  </svg>
                </div>
                <div>
                  <h2 style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', margin: 0 }}>Add Job</h2>
                  <p style={{ fontSize: 11, color: 'rgba(100,116,139,0.65)', margin: '3px 0 0' }}>
                    Fetch from a URL or paste the JD manually
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                style={{ background: 'transparent', border: 'none', color: 'rgba(100,116,139,0.5)', cursor: 'pointer', padding: 6, borderRadius: 6, lineHeight: 1 }}
                onMouseEnter={e => (e.currentTarget.style.color = '#e2e8f0')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.5)')}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 2, marginTop: 18, background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 3 }}>
              {(['fetch', 'manual'] as Tab[]).map(t => (
                <button
                  key={t}
                  onClick={() => { setTab(t); setStep('idle'); setErrorMsg(''); setFetched(null) }}
                  disabled={isWorking}
                  style={{
                    flex: 1, padding: '6px 12px', borderRadius: 6, border: 'none', cursor: 'pointer',
                    fontFamily: 'monospace', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                    transition: 'all 0.15s',
                    background: tab === t ? 'rgba(34,211,238,0.1)' : 'transparent',
                    color: tab === t ? '#22d3ee' : 'rgba(100,116,139,0.5)',
                    border: tab === t ? '1px solid rgba(34,211,238,0.2)' : '1px solid transparent',
                  }}
                >
                  {t === 'fetch' ? '🔗  Fetch from URL' : '✍️  Manual'}
                </button>
              ))}
            </div>
          </div>

          <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', margin: '0 24px' }} />

          {/* ── Body ── */}
          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* ── FETCH TAB ── */}
            {tab === 'fetch' && (
              <>
                <Field label="Job Posting URL" required>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <Input
                      ref={urlInputRef}
                      type="url"
                      value={fetchUrl}
                      onChange={e => { setFetchUrl(e.target.value); if (step === 'error') setStep('idle') }}
                      placeholder="https://jobs.company.com/…  or  https://linkedin.com/jobs/…"
                      disabled={isWorking}
                      onKeyDown={e => { if (e.key === 'Enter') handleFetch() }}
                      style={{ flex: 1 }}
                    />
                    <ActionBtn onClick={handleFetch} disabled={!fetchUrl.trim() || step === 'preview' || step === 'done'} loading={step === 'loading'}>
                      {step === 'loading' ? 'Fetching…' : 'Fetch'}
                    </ActionBtn>
                  </div>
                </Field>

                {step === 'error' && (
                  <div style={{ borderRadius: 8, padding: '10px 14px', background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.2)', display: 'flex', alignItems: 'center', gap: 10 }}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <span style={{ fontSize: 12, color: '#fca5a5', flex: 1 }}>{errorMsg}</span>
                    <button onClick={() => setStep('idle')} style={{ fontSize: 11, color: 'rgba(248,113,113,0.7)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
                      Try again
                    </button>
                  </div>
                )}

                {/* Preview card */}
                {fetched && (step === 'preview' || step === 'saving' || step === 'done') && (
                  <div style={{ borderRadius: 10, border: '1px solid rgba(34,211,238,0.15)', background: 'rgba(34,211,238,0.03)', padding: 16, display: 'flex', flexDirection: 'column', gap: 12, animation: 'fadeUp 0.2s ease-out' }}>
                    {/* Job header */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', margin: 0, lineHeight: 1.3 }}>{fetched.title}</p>
                        <p style={{ fontSize: 12, color: 'rgba(148,163,184,0.7)', margin: '4px 0 0' }}>
                          {fetched.company || <span style={{ color: 'rgba(100,116,139,0.4)', fontStyle: 'italic' }}>Company not found</span>}
                          {fetched.location && <> · {fetched.location}</>}
                          {fetched.remote && <span style={{ marginLeft: 6, fontSize: 10, fontFamily: 'monospace', fontWeight: 700, color: '#22d3ee', background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.2)', borderRadius: 4, padding: '1px 5px' }}>REMOTE</span>}
                        </p>
                        {fetched.date_posted && (
                          <p style={{ fontSize: 11, color: 'rgba(100,116,139,0.5)', margin: '4px 0 0', fontFamily: 'monospace' }}>
                            Posted {fetched.date_posted}
                          </p>
                        )}
                      </div>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#34d399', flexShrink: 0, marginTop: 6, boxShadow: '0 0 8px rgba(52,211,153,0.6)' }} />
                    </div>

                    {/* Description preview */}
                    <div>
                      <p style={{ fontSize: 10, fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)', marginBottom: 6 }}>
                        Description preview
                      </p>
                      <p style={{ fontSize: 12, color: 'rgba(148,163,184,0.65)', lineHeight: 1.6, margin: 0, maxHeight: 120, overflow: 'hidden', maskImage: 'linear-gradient(to bottom, black 60%, transparent)' }}>
                        {fetched.description.slice(0, 600)}
                      </p>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 6, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      <span style={{ fontSize: 11, color: 'rgba(100,116,139,0.4)', fontFamily: 'monospace' }}>
                        {fetched.description.length.toLocaleString()} chars
                      </span>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          onClick={() => { setFetched(null); setStep('idle'); setFetchUrl('') }}
                          disabled={isWorking}
                          style={{ fontSize: 12, color: 'rgba(100,116,139,0.5)', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px' }}
                          onMouseEnter={e => (e.currentTarget.style.color = '#e2e8f0')}
                          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.5)')}
                        >
                          Refetch
                        </button>
                        <ActionBtn onClick={handleSaveFetched} loading={step === 'saving'} done={step === 'done'}>
                          {step === 'done' ? 'Done!' : step === 'saving' ? 'Tailoring…' : 'Tailor Resume'}
                        </ActionBtn>
                      </div>
                    </div>
                  </div>
                )}

                {step === 'idle' && !fetched && (
                  <div style={{ borderRadius: 10, border: '1px dashed rgba(255,255,255,0.06)', padding: '28px 24px', textAlign: 'center' }}>
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.25)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ margin: '0 auto 10px' }}>
                      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                    <p style={{ fontSize: 12, color: 'rgba(100,116,139,0.45)', margin: 0 }}>
                      Paste a job posting URL above — works with LinkedIn, Greenhouse, Lever, Workday, and most job boards
                    </p>
                  </div>
                )}
              </>
            )}

            {/* ── MANUAL TAB ── */}
            {tab === 'manual' && (
              <>
                <div style={{ display: 'flex', gap: 12 }}>
                  <Field label="Job Title" required>
                    <Input
                      type="text"
                      value={title}
                      onChange={e => setTitle(e.target.value)}
                      placeholder="e.g. Senior Backend Engineer"
                      disabled={isWorking}
                    />
                  </Field>
                  <Field label="Company" required>
                    <Input
                      type="text"
                      value={company}
                      onChange={e => setCompany(e.target.value)}
                      placeholder="e.g. Stripe"
                      disabled={isWorking}
                    />
                  </Field>
                </div>

                <Field label="Job Description" required hint={`${description.length.toLocaleString()} / 10,000`}>
                  <Textarea
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    placeholder={"Paste the full job description here…\n\nInclude requirements, responsibilities, and qualifications for the best tailoring results."}
                    rows={11}
                    disabled={isWorking}
                    onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleManualSubmit() }}
                  />
                </Field>

                <Field label="Apply URL" hint="(optional)">
                  <Input
                    type="url"
                    value={applyUrl}
                    onChange={e => setApplyUrl(e.target.value)}
                    placeholder="https://jobs.company.com/…"
                    disabled={isWorking}
                  />
                </Field>

                {step === 'error' && (
                  <div style={{ borderRadius: 8, padding: '10px 14px', background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.2)', display: 'flex', alignItems: 'center', gap: 10 }}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <span style={{ fontSize: 12, color: '#fca5a5', flex: 1 }}>{errorMsg}</span>
                    <button onClick={() => setStep('idle')} style={{ fontSize: 11, color: 'rgba(248,113,113,0.7)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
                      Try again
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* ── Footer ── */}
          <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', margin: '0 24px' }} />
          <div style={{ padding: '14px 24px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 5, height: 5, borderRadius: '50%', background: step === 'done' ? '#34d399' : step === 'saving' || step === 'loading' ? '#fbbf24' : 'rgba(34,211,238,0.35)' }} />
              <span style={{ fontSize: 10, fontFamily: 'monospace', color: 'rgba(100,116,139,0.5)' }}>
                {step === 'done' ? 'Job added — opening apply panel…' : step === 'saving' ? 'Saving & queuing resume tailor…' : step === 'loading' ? 'Fetching job from URL…' : 'Added as MATCH · resume tailored automatically'}
              </span>
            </div>
            {tab === 'manual' && (
              <ActionBtn onClick={handleManualSubmit} disabled={!canManualSubmit} loading={step === 'saving'} done={step === 'done'}>
                {step === 'done' ? 'Done!' : step === 'saving' ? 'Adding…' : 'Add Job'}
              </ActionBtn>
            )}
            {tab === 'fetch' && step !== 'preview' && step !== 'saving' && step !== 'done' && (
              <button
                onClick={onClose}
                style={{ fontSize: 12, color: 'rgba(100,116,139,0.5)', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px' }}
                onMouseEnter={e => (e.currentTarget.style.color = '#e2e8f0')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.5)')}
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
