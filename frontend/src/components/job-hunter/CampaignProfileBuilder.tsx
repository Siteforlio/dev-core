import { useState, useEffect, useRef } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'

const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.txt', '.md']
const CONTEXT_BUDGET_BYTES = 400 * 1024

interface QueuedFile { id: string; file: File }
interface Props {
  campaignId: string
  campaignName: string
  campaignCategories: string[]
  onReady: () => void
  onCategoriesAdded: (cats: string[]) => void
}
interface GapAnalysis {
  score: number
  is_ready: boolean
  has_mandatory: boolean
  has_contact: boolean
  has_experience: boolean
  gaps: string[]
  questions: { gap: string; question: string }[]
  summary: string
  suggested_titles: string[]
}
type Step = 'paste' | 'gaps' | 'ready'

function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 75 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171'
  const r = 28, circ = 2 * Math.PI * r
  const dash = (score / 100) * circ
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" style={{ transform: 'rotate(-90deg)' }}>
      <circle cx="36" cy="36" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="5" />
      <circle cx="36" cy="36" r={r} fill="none" stroke={color} strokeWidth="5"
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 0.6s ease', filter: `drop-shadow(0 0 6px ${color})` }}
      />
      <text x="36" y="40" textAnchor="middle" fill={color}
        style={{ transform: 'rotate(90deg) translate(0, -72px)', fontFamily: 'monospace', fontSize: '14px', fontWeight: 700, transformOrigin: '36px 36px' }}>
        {score}
      </text>
    </svg>
  )
}

export default function CampaignProfileBuilder({ campaignId, campaignName, campaignCategories, onReady, onCategoriesAdded }: Props) {
  const { getCampaignProfile, analyzeProfileGaps, addCampaignCategories, processRawContext, processContextFile } = useJobHunter()

  const [step, setStep] = useState<Step>('paste')
  const [rawText, setRawText] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [queue, setQueue] = useState<QueuedFile[]>([])
  const [sendingIdx, setSendingIdx] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [analysis, setAnalysis] = useState<GapAnalysis | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [loadingLabel, setLoadingLabel] = useState('')
  const submittingRef = useRef(false)
  const [error, setError] = useState('')
  const [previewFile, setPreviewFile] = useState<QueuedFile | null>(null)
  const [previewText, setPreviewText] = useState<string | null>(null)
  const [addedTitles, setAddedTitles] = useState<Set<string>>(new Set(campaignCategories))

  const totalQueueBytes = queue.reduce((s, q) => s + q.file.size, 0)
  const contextPct = Math.min(100, Math.round((totalQueueBytes / CONTEXT_BUDGET_BYTES) * 100))
  const contextFull = totalQueueBytes >= CONTEXT_BUDGET_BYTES

  useEffect(() => {
    getCampaignProfile(campaignId).then(p => {
      if ((p as any).raw_context || (p.work_experience as unknown[])?.length) {
        setStep('gaps')
        loadAnalysis()
      }
    }).catch(() => {})
  }, [campaignId])

  const loadAnalysis = async () => {
    setLoading(true)
    setLoadingLabel('Analyzing your profile…')
    try {
      const result = await analyzeProfileGaps(campaignId)
      setAnalysis(result)
      setStep(result.is_ready ? 'ready' : 'gaps')
    } catch {
      setError('Failed to analyze profile')
    } finally {
      setLoading(false)
      setLoadingLabel('')
    }
  }

  const handlePasteSubmit = async () => {
    if (!rawText.trim() || submittingRef.current) return
    submittingRef.current = true
    setLoading(true)
    setLoadingLabel('Saving your info…')
    setError('')
    try {
      await processRawContext(campaignId, rawText)
      setLoadingLabel('Analyzing your profile…')
      await loadAnalysis()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to process context')
      setLoading(false); setLoadingLabel('')
    } finally { submittingRef.current = false }
  }

  const addFilesToQueue = (files: FileList | File[]) => {
    setError('')
    const arr = Array.from(files)
    const valid: QueuedFile[] = []
    for (const file of arr) {
      const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase()
      if (!ALLOWED_EXTS.includes(ext)) { setError(`"${file.name}" — unsupported. Allowed: ${ALLOWED_EXTS.join(', ')}`); continue }
      if (totalQueueBytes + file.size > CONTEXT_BUDGET_BYTES) { setError('Context budget full.'); break }
      if (!queue.some(q => q.file.name === file.name)) valid.push({ id: crypto.randomUUID(), file })
    }
    if (valid.length) setQueue(prev => [...prev, ...valid])
  }

  const removeFromQueue = (id: string) => {
    setQueue(prev => prev.filter(q => q.id !== id))
    if (previewFile?.id === id) setPreviewFile(null)
  }

  const openPreview = (qf: QueuedFile) => {
    setPreviewFile(qf)
    const ext = '.' + (qf.file.name.split('.').pop() ?? '').toLowerCase()
    if (ext === '.txt' || ext === '.md') {
      const reader = new FileReader()
      reader.onload = e => setPreviewText(e.target?.result as string ?? '')
      reader.readAsText(qf.file)
    } else { setPreviewText(null) }
  }

  const handleSendQueue = async () => {
    if (!queue.length || loading || submittingRef.current) return
    submittingRef.current = true
    setLoading(true)
    setError('')
    for (let i = 0; i < queue.length; i++) {
      setSendingIdx(i)
      setLoadingLabel(`Reading ${queue[i].file.name} (${i + 1}/${queue.length})…`)
      try {
        await processContextFile(campaignId, queue[i].file)
      } catch (e: unknown) {
        setError(`Failed on "${queue[i].file.name}": ${e instanceof Error ? e.message : 'Unknown error'}`)
        setLoading(false); setSendingIdx(null); setLoadingLabel(''); submittingRef.current = false; return
      }
    }
    setSendingIdx(null); setQueue([]); setPreviewFile(null); submittingRef.current = false
    await loadAnalysis()
  }

  const handleAnswersSubmit = async () => {
    if (!analysis) return
    setLoading(true); setLoadingLabel('Updating profile…'); setError('')
    try {
      const answersText = analysis.questions
        .map((q, i) => `Q: ${q.question}\nA: ${answers[i] ?? ''}`)
        .filter((_, i) => answers[i]?.trim()).join('\n\n')
      if (answersText) await processRawContext(campaignId, answersText)
      setLoadingLabel('Re-analyzing…')
      await loadAnalysis()
      setAnswers({})
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update')
      setLoading(false); setLoadingLabel('')
    }
  }

  const scoreColor = (s: number) => s >= 75 ? '#34d399' : s >= 50 ? '#fbbf24' : '#f87171'
  const canSubmit = queue.length > 0 || rawText.trim().length > 0

  // ── Shared card style ─────────────────────────────────────────────────────
  const card: React.CSSProperties = {
    background: 'rgba(34,211,238,0.025)',
    border: '1px solid rgba(34,211,238,0.1)',
    borderRadius: '12px',
    padding: '20px',
  }

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', width: '100%', padding: '32px 16px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* ── Header ── */}
      <div>
        <p style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.5)', marginBottom: '6px' }}>
          — Campaign: {campaignName}
        </p>
        <h2 style={{ fontFamily: '"Orbitron", monospace', fontWeight: 700, fontSize: '22px', letterSpacing: '0.08em', color: 'rgba(226,232,240,0.95)', lineHeight: 1, marginBottom: '8px' }}>
          Build Your Profile
        </h2>
        <p style={{ fontFamily: 'monospace', fontSize: '12px', color: 'rgba(100,116,139,0.6)', lineHeight: 1.6 }}>
          Share your background — CV, work history, skills. The AI checks what's missing and asks targeted questions.
        </p>
      </div>

      {/* ── Loading state ── */}
      {loading && (
        <div style={{ ...card, display: 'flex', alignItems: 'center', gap: '16px', padding: '24px' }}>
          <div style={{ width: '36px', height: '36px', border: '2px solid rgba(34,211,238,0.2)', borderTopColor: '#22d3ee', borderRadius: '50%', animation: 'spin 0.8s linear infinite', flexShrink: 0 }} />
          <div>
            <p style={{ fontFamily: 'monospace', fontSize: '12px', color: 'rgba(226,232,240,0.8)', marginBottom: '3px' }}>{loadingLabel || 'Processing…'}</p>
            <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.4)' }}>This may take a few seconds</p>
          </div>
        </div>
      )}

      {/* ── Step 1: Paste / Upload ── */}
      {step === 'paste' && !loading && (
        <>
          {/* Drop zone */}
          <div
            style={{
              ...card,
              minHeight: '140px',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px',
              cursor: 'pointer',
              border: `1px dashed ${dragOver ? 'rgba(34,211,238,0.5)' : 'rgba(34,211,238,0.15)'}`,
              background: dragOver ? 'rgba(34,211,238,0.05)' : 'rgba(34,211,238,0.015)',
              transition: 'all 0.15s',
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files.length) addFilesToQueue(e.dataTransfer.files) }}
          >
            <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'rgba(34,211,238,0.07)', border: '1px solid rgba(34,211,238,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.8" strokeLinecap="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <div style={{ textAlign: 'center' }}>
              <p style={{ fontFamily: 'monospace', fontSize: '12px', color: 'rgba(148,163,184,0.7)', marginBottom: '4px' }}>
                Drop files here, or <span style={{ color: '#22d3ee', textDecoration: 'underline' }}>browse</span>
              </p>
              <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.4)' }}>
                PDF, DOCX, TXT, MD · Plain text works best
              </p>
            </div>
            <input ref={fileInputRef} type="file" accept=".pdf,.docx,.doc,.txt,.md" multiple style={{ display: 'none' }}
              onChange={e => { if (e.target.files?.length) addFilesToQueue(e.target.files); e.target.value = '' }} />
          </div>

          {/* File queue */}
          {queue.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontFamily: 'monospace', fontSize: '9px', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)' }}>Context budget</span>
                <span style={{ fontFamily: 'monospace', fontSize: '10px', color: contextFull ? '#f87171' : contextPct > 70 ? '#fbbf24' : 'rgba(100,116,139,0.5)' }}>
                  {fmtBytes(totalQueueBytes)} / {fmtBytes(CONTEXT_BUDGET_BYTES)}
                </span>
              </div>
              <div style={{ height: '3px', borderRadius: '2px', background: 'rgba(255,255,255,0.05)', overflow: 'hidden', marginBottom: '4px' }}>
                <div style={{ height: '100%', borderRadius: '2px', transition: 'width 0.3s', width: `${contextPct}%`, background: contextFull ? '#f87171' : contextPct > 70 ? '#fbbf24' : '#22d3ee', boxShadow: contextFull ? '0 0 6px #f87171' : '0 0 6px rgba(34,211,238,0.4)' }} />
              </div>
              {queue.map((qf, i) => (
                <div key={qf.id} style={{
                  display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px', borderRadius: '8px',
                  background: sendingIdx === i ? 'rgba(34,211,238,0.06)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${sendingIdx === i ? 'rgba(34,211,238,0.2)' : 'rgba(255,255,255,0.06)'}`,
                }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={sendingIdx === i ? '#22d3ee' : 'rgba(100,116,139,0.5)'} strokeWidth="1.5" strokeLinecap="round">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
                  </svg>
                  <button onClick={() => openPreview(qf)} style={{ flex: 1, background: 'none', border: 'none', color: 'rgba(148,163,184,0.8)', fontFamily: 'monospace', fontSize: '11px', textAlign: 'left', cursor: 'pointer', padding: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {qf.file.name}
                  </button>
                  <span style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.4)', flexShrink: 0 }}>{fmtBytes(qf.file.size)}</span>
                  {sendingIdx === i
                    ? <div style={{ width: '14px', height: '14px', border: '2px solid rgba(34,211,238,0.3)', borderTopColor: '#22d3ee', borderRadius: '50%', animation: 'spin 0.7s linear infinite', flexShrink: 0 }} />
                    : <button onClick={() => removeFromQueue(qf.id)} style={{ background: 'none', border: 'none', color: 'rgba(100,116,139,0.35)', cursor: 'pointer', padding: 0, flexShrink: 0 }}
                        onMouseEnter={e => (e.currentTarget.style.color = '#f87171')}
                        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.35)')}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </button>
                  }
                </div>
              ))}
            </div>
          )}

          {/* File preview */}
          {previewFile && (
            <div style={{ ...card, padding: 0, overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid rgba(34,211,238,0.08)' }}>
                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: 'rgba(148,163,184,0.7)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{previewFile.file.name}</span>
                <button onClick={() => setPreviewFile(null)} style={{ background: 'none', border: 'none', color: 'rgba(100,116,139,0.4)', cursor: 'pointer', padding: 0, flexShrink: 0, marginLeft: '8px' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
              <div style={{ maxHeight: '220px', overflowY: 'auto', padding: '12px 14px', fontFamily: 'monospace', fontSize: '11px', color: 'rgba(100,116,139,0.7)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {previewText !== null
                  ? (previewText || <span style={{ fontStyle: 'italic' }}>Empty file</span>)
                  : <span style={{ fontStyle: 'italic', color: 'rgba(100,116,139,0.4)' }}>Preview not available for {previewFile.file.name.split('.').pop()?.toUpperCase()} — content extracted on send.</span>
                }
              </div>
            </div>
          )}

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ flex: 1, height: '1px', background: 'rgba(34,211,238,0.08)' }} />
            <span style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.35)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>or paste text</span>
            <div style={{ flex: 1, height: '1px', background: 'rgba(34,211,238,0.08)' }} />
          </div>

          {/* Paste area */}
          <div style={card}>
            <p style={{ fontFamily: 'monospace', fontSize: '11px', fontWeight: 600, color: 'rgba(226,232,240,0.8)', marginBottom: '8px' }}>Paste your profile</p>
            <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.5)', marginBottom: '14px', lineHeight: 1.6 }}>
              Copy from your CV, LinkedIn, or just type it out. Plain text works best — no tables or columns.
            </p>
            <textarea
              value={rawText}
              onChange={e => setRawText(e.target.value)}
              rows={10}
              placeholder={`Example:\n\nJane Doe\n5 years experience in healthcare administration\nWorked at Nairobi General Hospital 2020–2023 as Ward Manager\nManaged a team of 12 nurses, reduced patient wait time by 30%\nSkills: Patient coordination, scheduling, EMR systems, team leadership\nEmail: jane@example.com · Phone: +254 700 000 000`}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid rgba(34,211,238,0.12)',
                borderRadius: '8px',
                padding: '12px 14px',
                color: 'rgba(226,232,240,0.85)',
                fontFamily: 'monospace',
                fontSize: '12px',
                lineHeight: 1.6,
                resize: 'none',
                outline: 'none',
              }}
              onFocus={e => (e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)')}
              onBlur={e => (e.currentTarget.style.borderColor = 'rgba(34,211,238,0.12)')}
            />
          </div>

          {error && <p style={{ fontFamily: 'monospace', fontSize: '11px', color: '#f87171' }}>{error}</p>}

          <button
            onClick={queue.length > 0 ? handleSendQueue : handlePasteSubmit}
            disabled={!canSubmit}
            style={{
              alignSelf: 'flex-start',
              padding: '12px 28px',
              background: canSubmit ? 'rgba(34,211,238,0.1)' : 'transparent',
              border: `1px solid ${canSubmit ? 'rgba(34,211,238,0.4)' : 'rgba(255,255,255,0.07)'}`,
              borderRadius: '10px',
              color: canSubmit ? '#22d3ee' : 'rgba(255,255,255,0.18)',
              fontFamily: '"Orbitron", monospace',
              fontSize: '11px', fontWeight: 700,
              letterSpacing: '0.16em', textTransform: 'uppercase',
              cursor: canSubmit ? 'pointer' : 'not-allowed',
              display: 'flex', alignItems: 'center', gap: '10px',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => { if (canSubmit) e.currentTarget.style.background = 'rgba(34,211,238,0.17)' }}
            onMouseLeave={e => { e.currentTarget.style.background = canSubmit ? 'rgba(34,211,238,0.1)' : 'transparent' }}
          >
            {queue.length > 0
              ? `Analyze ${queue.length} file${queue.length > 1 ? 's' : ''}`
              : 'Analyze Profile'}
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
          </button>
        </>
      )}

      {/* ── Step 2 & 3: Analysis results ── */}
      {(step === 'gaps' || step === 'ready') && analysis && !loading && (() => {
        const isReady = step === 'ready'

        const handleToggleTitle = async (title: string) => {
          if (addedTitles.has(title)) return  // already in campaign
          try {
            await addCampaignCategories(campaignId, [title])
            setAddedTitles(prev => new Set([...prev, title]))
            onCategoriesAdded([title])
          } catch { /* silently ignore */ }
        }

        const newSuggestions = (analysis.suggested_titles ?? []).filter(t => !addedTitles.has(t))
        const alreadySuggested = (analysis.suggested_titles ?? []).filter(t => addedTitles.has(t))

        return (
          <>
            {/* Mandatory check banner — shown when not yet met */}
            {!analysis.has_mandatory && (
              <div style={{ ...card, background: 'rgba(248,113,113,0.05)', border: '1px solid rgba(248,113,113,0.25)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <p style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: '#f87171' }}>
                  Required before campaign can run
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {[
                    { ok: analysis.has_contact, label: 'Contact info (email or phone)' },
                    { ok: analysis.has_experience, label: 'At least one work experience or project' },
                  ].map(({ ok, label }) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {ok
                        ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                        : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      }
                      <span style={{ fontFamily: 'monospace', fontSize: '12px', color: ok ? 'rgba(52,211,153,0.8)' : 'rgba(248,113,113,0.85)' }}>{label}</span>
                    </div>
                  ))}
                </div>
                <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.5)', lineHeight: 1.5 }}>
                  Add the missing info below and re-analyze to proceed.
                </p>
              </div>
            )}

            {/* Score card */}
            <div style={{ ...card, display: 'flex', alignItems: 'center', gap: '20px' }}>
              <div style={{ position: 'relative', flexShrink: 0 }}>
                <ScoreRing score={analysis.score} />
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontFamily: 'monospace', fontSize: '15px', fontWeight: 700, color: scoreColor(analysis.score) }}>{analysis.score}</span>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <p style={{ fontFamily: '"Orbitron", monospace', fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', color: 'rgba(226,232,240,0.9)' }}>Profile Readiness</p>
                  <span style={{ fontFamily: 'monospace', fontSize: '9px', letterSpacing: '0.14em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: '4px', background: isReady ? 'rgba(52,211,153,0.1)' : 'rgba(251,191,36,0.1)', border: `1px solid ${isReady ? 'rgba(52,211,153,0.25)' : 'rgba(251,191,36,0.25)'}`, color: isReady ? '#34d399' : '#fbbf24' }}>
                    {isReady ? 'Ready' : 'Needs info'}
                  </span>
                </div>
                <div style={{ height: '4px', borderRadius: '2px', background: 'rgba(255,255,255,0.05)', overflow: 'hidden', marginBottom: '10px' }}>
                  <div style={{ height: '100%', borderRadius: '2px', transition: 'width 0.6s ease', width: `${analysis.score}%`, background: scoreColor(analysis.score), boxShadow: `0 0 8px ${scoreColor(analysis.score)}` }} />
                </div>
                <p style={{ fontFamily: 'monospace', fontSize: '11px', color: 'rgba(100,116,139,0.65)', lineHeight: 1.5 }}>{analysis.summary}</p>
              </div>
            </div>

            {/* Suggested job titles */}
            {(analysis.suggested_titles ?? []).length > 0 && (
              <div style={card}>
                <p style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.7)', marginBottom: '6px' }}>
                  Suggested job categories
                </p>
                <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.5)', marginBottom: '12px', lineHeight: 1.5 }}>
                  Based on your CV — click to add to this campaign's search targets.
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {newSuggestions.map(title => (
                    <button
                      key={title}
                      onClick={() => handleToggleTitle(title)}
                      style={{
                        padding: '5px 12px', borderRadius: '20px', cursor: 'pointer', transition: 'all 0.15s',
                        fontFamily: 'monospace', fontSize: '11px', fontWeight: 600,
                        background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.3)', color: '#22d3ee',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.18)'; e.currentTarget.style.borderColor = 'rgba(34,211,238,0.6)' }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.08)'; e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)' }}
                    >
                      + {title}
                    </button>
                  ))}
                  {alreadySuggested.map(title => (
                    <span
                      key={title}
                      style={{
                        padding: '5px 12px', borderRadius: '20px',
                        fontFamily: 'monospace', fontSize: '11px', fontWeight: 600,
                        background: 'rgba(52,211,153,0.07)', border: '1px solid rgba(52,211,153,0.25)', color: 'rgba(52,211,153,0.6)',
                        display: 'inline-flex', alignItems: 'center', gap: '5px',
                      }}
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                      {title}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Gaps */}
            {analysis.gaps.length > 0 && (
              <div style={card}>
                <p style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: isReady ? 'rgba(100,116,139,0.4)' : 'rgba(251,191,36,0.7)', marginBottom: '14px' }}>
                  {isReady ? 'Optional improvements' : "What's missing"}
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {analysis.gaps.map((gap, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                      <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: isReady ? 'rgba(100,116,139,0.4)' : '#fbbf24', boxShadow: isReady ? 'none' : '0 0 4px #fbbf24', flexShrink: 0, marginTop: '5px' }} />
                      <span style={{ fontFamily: 'monospace', fontSize: '12px', color: isReady ? 'rgba(100,116,139,0.5)' : 'rgba(148,163,184,0.75)', lineHeight: 1.5 }}>{gap}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Questions */}
            {analysis.questions.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <p style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.6)' }}>
                  Answer these to strengthen your profile
                </p>
                {analysis.questions.map((q, i) => (
                  <div key={i} style={card}>
                    <p style={{ fontFamily: 'monospace', fontSize: '9px', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.5)', marginBottom: '6px' }}>{q.gap}</p>
                    <p style={{ fontFamily: 'monospace', fontSize: '12px', color: 'rgba(226,232,240,0.85)', marginBottom: '12px', lineHeight: 1.5 }}>{q.question}</p>
                    <textarea
                      value={answers[i] ?? ''}
                      onChange={e => setAnswers(prev => ({ ...prev, [i]: e.target.value }))}
                      rows={3}
                      placeholder="Your answer…"
                      style={{
                        width: '100%', boxSizing: 'border-box',
                        background: 'rgba(0,0,0,0.3)',
                        border: '1px solid rgba(34,211,238,0.1)',
                        borderRadius: '8px',
                        padding: '10px 12px',
                        color: 'rgba(226,232,240,0.85)',
                        fontFamily: 'monospace',
                        fontSize: '12px',
                        lineHeight: 1.6,
                        resize: 'none',
                        outline: 'none',
                      }}
                      onFocus={e => (e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)')}
                      onBlur={e => (e.currentTarget.style.borderColor = 'rgba(34,211,238,0.1)')}
                    />
                  </div>
                ))}
              </div>
            )}

            {error && <p style={{ fontFamily: 'monospace', fontSize: '11px', color: '#f87171' }}>{error}</p>}

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
              {/* Start Campaign — always visible, disabled until mandatory is met */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <button
                  onClick={analysis.has_mandatory ? onReady : undefined}
                  disabled={!analysis.has_mandatory}
                  style={{
                    padding: '13px 32px',
                    background: !analysis.has_mandatory
                      ? 'transparent'
                      : isReady ? 'rgba(52,211,153,0.1)' : 'rgba(34,211,238,0.08)',
                    border: `1px solid ${!analysis.has_mandatory
                      ? 'rgba(255,255,255,0.08)'
                      : isReady ? 'rgba(52,211,153,0.35)' : 'rgba(34,211,238,0.3)'}`,
                    borderRadius: '10px',
                    color: !analysis.has_mandatory
                      ? 'rgba(255,255,255,0.2)'
                      : isReady ? '#34d399' : '#22d3ee',
                    fontFamily: '"Orbitron", monospace',
                    fontSize: '11px', fontWeight: 700,
                    letterSpacing: '0.16em', textTransform: 'uppercase',
                    cursor: analysis.has_mandatory ? 'pointer' : 'not-allowed',
                    transition: 'all 0.15s',
                    display: 'flex', alignItems: 'center', gap: '10px',
                  }}
                  onMouseEnter={e => { if (analysis.has_mandatory) e.currentTarget.style.background = isReady ? 'rgba(52,211,153,0.17)' : 'rgba(34,211,238,0.16)' }}
                  onMouseLeave={e => { if (analysis.has_mandatory) e.currentTarget.style.background = isReady ? 'rgba(52,211,153,0.1)' : 'rgba(34,211,238,0.08)' }}
                >
                  Start Campaign
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </button>
                {!analysis.has_mandatory && (
                  <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(248,113,113,0.6)', paddingLeft: '2px' }}>
                    Add contact info and at least one work experience first
                  </p>
                )}
              </div>
              {analysis.questions.length > 0 && (
                <button
                  onClick={handleAnswersSubmit}
                  disabled={Object.values(answers).every(a => !a.trim())}
                  style={{
                    padding: '12px 24px',
                    background: 'rgba(34,211,238,0.1)',
                    border: '1px solid rgba(34,211,238,0.4)',
                    borderRadius: '10px',
                    color: '#22d3ee',
                    fontFamily: '"Orbitron", monospace',
                    fontSize: '10px', fontWeight: 700,
                    letterSpacing: '0.16em', textTransform: 'uppercase',
                    cursor: 'pointer', transition: 'all 0.15s',
                    opacity: Object.values(answers).every(a => !a.trim()) ? 0.4 : 1,
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.17)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.1)')}
                >
                  Submit Answers
                </button>
              )}
              <button
                onClick={() => setStep('paste')}
                style={{ background: 'none', border: 'none', color: 'rgba(100,116,139,0.5)', fontFamily: 'monospace', fontSize: '11px', cursor: 'pointer', padding: 0, transition: 'color 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'rgba(148,163,184,0.8)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.5)')}
              >
                ← Add more context
              </button>
            </div>
          </>
        )
      })()}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
