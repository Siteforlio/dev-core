import { useState, useEffect, useRef } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'

const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.txt', '.md']
// Soft context budget: ~400 KB raw across all queued files.
// Backend cleans + caps each file to ~12 000 chars, so this is a generous ceiling.
const CONTEXT_BUDGET_BYTES = 400 * 1024

interface QueuedFile {
  id: string
  file: File
}

interface Props {
  campaignId: string
  campaignName: string
  onReady: () => void
}

interface GapAnalysis {
  score: number
  is_ready: boolean
  gaps: string[]
  questions: { gap: string; question: string }[]
  summary: string
}

type Step = 'paste' | 'gaps' | 'ready'

function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}

export default function CampaignProfileBuilder({ campaignId, campaignName, onReady }: Props) {
  const { getCampaignProfile, analyzeProfileGaps, processRawContext, processContextFile } = useJobHunter()

  const [step, setStep] = useState<Step>('paste')
  const [rawText, setRawText] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Queue of staged files — not yet sent
  const [queue, setQueue] = useState<QueuedFile[]>([])
  const [sendingIdx, setSendingIdx] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [analysis, setAnalysis] = useState<GapAnalysis | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [loadingLabel, setLoadingLabel] = useState('')
  const submittingRef = useRef(false)
  const [error, setError] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const totalQueueBytes = queue.reduce((s, q) => s + q.file.size, 0)
  const contextPct = Math.min(100, Math.round((totalQueueBytes / CONTEXT_BUDGET_BYTES) * 100))
  const contextFull = totalQueueBytes >= CONTEXT_BUDGET_BYTES

  useEffect(() => {
    getCampaignProfile(campaignId).then(p => {
      // If already has data, go straight to gap analysis
      if (p.raw_context || (p.work_experience as unknown[])?.length) {
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
      setLoading(false)
      setLoadingLabel('')
    } finally {
      submittingRef.current = false
    }
  }

  const [previewFile, setPreviewFile] = useState<QueuedFile | null>(null)
  const [previewText, setPreviewText] = useState<string | null>(null)

  const addFilesToQueue = (files: FileList | File[]) => {
    setError('')
    const arr = Array.from(files)
    const valid: QueuedFile[] = []
    for (const file of arr) {
      const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase()
      if (!ALLOWED_EXTS.includes(ext)) {
        setError(`"${file.name}" — unsupported type. Allowed: ${ALLOWED_EXTS.join(', ')}`)
        continue
      }
      if (totalQueueBytes + file.size > CONTEXT_BUDGET_BYTES) {
        setError('Context budget full. Remove a file before adding more.')
        break
      }
      // Deduplicate by name
      if (!queue.some(q => q.file.name === file.name)) {
        valid.push({ id: crypto.randomUUID(), file })
      }
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
    } else {
      setPreviewText(null) // binary — no text preview
    }
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
        setLoading(false)
        setSendingIdx(null)
        setLoadingLabel('')
        submittingRef.current = false
        return
      }
    }
    setSendingIdx(null)
    setQueue([])
    setPreviewFile(null)
    submittingRef.current = false
    await loadAnalysis()
  }

  const handleAnswersSubmit = async () => {
    if (!analysis) return
    setLoading(true)
    setLoadingLabel('Updating profile…')
    setError('')
    try {
      // Append answers as additional raw context
      const answersText = analysis.questions
        .map((q, i) => `Q: ${q.question}\nA: ${answers[i] ?? ''}`)
        .filter((_, i) => answers[i]?.trim())
        .join('\n\n')

      if (answersText) {
        await processRawContext(campaignId, answersText)
      }
      setLoadingLabel('Re-analyzing your profile…')
      await loadAnalysis()
      setAnswers({})
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update profile')
      setLoading(false)
      setLoadingLabel('')
    }
  }

  const scoreColor = (score: number) =>
    score >= 80 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400'

  const scoreBg = (score: number) =>
    score >= 80 ? 'bg-green-500' : score >= 50 ? 'bg-yellow-500' : 'bg-red-500'

  return (
    <div className="max-w-2xl mx-auto w-full px-4 py-8 flex flex-col gap-6">
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Campaign: {campaignName}</p>
        <h2 className="text-2xl font-bold text-white">Build Your Profile</h2>
        <p className="text-gray-400 text-sm mt-1">
          The AI reads your profile, checks what's missing, and asks targeted questions to hit 90%+ ATS match.
        </p>
      </div>

      {/* ── Step 1: Paste context ── */}
      {step === 'paste' && loading && (
        <div className="flex flex-col items-center justify-center gap-4 py-16">
          <svg className="animate-spin h-8 w-8 text-blue-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
          <p className="text-sm text-gray-400">{loadingLabel || 'Processing…'}</p>
        </div>
      )}

      {step === 'paste' && !loading && (
        <div className="flex flex-col gap-4">

          {/* ── Drop zone ── */}
          <div
            className="rounded-xl flex flex-col items-center justify-center gap-3 cursor-pointer transition-all"
            style={{
              minHeight: 160,
              border: `2px dashed ${dragOver ? '#3b82f6' : 'rgba(255,255,255,0.1)'}`,
              background: dragOver ? 'rgba(59,130,246,0.05)' : 'rgba(255,255,255,0.02)',
              padding: '2rem 1.5rem',
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => {
              e.preventDefault()
              setDragOver(false)
              if (e.dataTransfer.files.length) addFilesToQueue(e.dataTransfer.files)
            }}
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-gray-500">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <div className="text-center">
              <p className="text-sm text-gray-400">
                Drop files here, or <span className="text-blue-400 hover:text-blue-300">browse</span>
              </p>
              <p className="text-xs text-gray-600 mt-1">Prefer plain text (.txt, .md) — PDFs and DOCX lose formatting</p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md"
              multiple
              className="hidden"
              onChange={e => {
                if (e.target.files?.length) addFilesToQueue(e.target.files)
                e.target.value = ''
              }}
            />
          </div>

          {/* ── File queue ── */}
          {queue.length > 0 && (
            <div className="flex flex-col gap-1.5">
              {/* Context budget meter */}
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-gray-600 uppercase tracking-widest font-semibold">Context budget</span>
                <span className={`text-[10px] font-mono ${contextFull ? 'text-red-400' : contextPct > 70 ? 'text-yellow-400' : 'text-gray-500'}`}>
                  {fmtBytes(totalQueueBytes)} / {fmtBytes(CONTEXT_BUDGET_BYTES)}
                </span>
              </div>
              <div className="h-1 w-full rounded-full bg-gray-800 overflow-hidden mb-2">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${contextPct}%`,
                    background: contextFull ? '#ef4444' : contextPct > 70 ? '#eab308' : '#3b82f6',
                  }}
                />
              </div>

              {queue.map((qf, i) => (
                <div
                  key={qf.id}
                  className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 group transition-colors"
                  style={{
                    background: sendingIdx === i ? 'rgba(59,130,246,0.08)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${sendingIdx === i ? 'rgba(59,130,246,0.25)' : 'rgba(255,255,255,0.06)'}`,
                  }}
                >
                  {/* File icon */}
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                    className={sendingIdx === i ? 'text-blue-400' : 'text-gray-600'}>
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>

                  {/* Name — clickable to preview */}
                  <button
                    className="flex-1 text-left text-xs text-gray-300 hover:text-white truncate transition-colors"
                    onClick={() => openPreview(qf)}
                    title="Click to preview"
                  >
                    {qf.file.name}
                  </button>

                  <span className="text-[10px] text-gray-600 font-mono flex-shrink-0">{fmtBytes(qf.file.size)}</span>

                  {sendingIdx === i ? (
                    <svg className="animate-spin h-3.5 w-3.5 text-blue-400 flex-shrink-0" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                    </svg>
                  ) : (
                    <button
                      onClick={() => removeFromQueue(qf.id)}
                      className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all flex-shrink-0"
                      title="Remove"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* ── File preview panel ── */}
          {previewFile && (
            <div
              className="rounded-xl flex flex-col overflow-hidden"
              style={{ border: '1px solid rgba(255,255,255,0.08)', background: '#0a0a0a' }}
            >
              <div className="flex items-center justify-between px-3 py-2 border-b border-gray-900">
                <span className="text-xs text-gray-400 font-medium truncate">{previewFile.file.name}</span>
                <button
                  onClick={() => setPreviewFile(null)}
                  className="text-gray-600 hover:text-white ml-2 flex-shrink-0"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
              <div
                className="overflow-y-auto p-3 text-xs text-gray-400 font-mono leading-relaxed whitespace-pre-wrap [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
                style={{ maxHeight: 240 }}
              >
                {previewText !== null
                  ? previewText || <span className="text-gray-600 italic">Empty file</span>
                  : <span className="text-gray-600 italic">Preview not available for {previewFile.file.name.split('.').pop()?.toUpperCase()} files — content will be extracted when you send.</span>
                }
              </div>
            </div>
          )}

          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-gray-800" />
            <span className="text-xs text-gray-600">or paste text</span>
            <div className="flex-1 h-px bg-gray-800" />
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-3">
            <p className="text-sm text-gray-300 font-medium">Paste plain text</p>
            <p className="text-xs text-gray-500">
              Copy-paste from your CV, LinkedIn, or just type it out. <strong className="text-gray-400">Plain text works best</strong> — no tables, no columns, no formatting. The AI reads it directly.
            </p>
            <textarea
              ref={textareaRef}
              value={rawText}
              onChange={e => setRawText(e.target.value)}
              rows={10}
              placeholder={`Example:\n\nSolomon Jesse\nsenior engineer with 6 years exp\nWorked at Google 2021–2023 as Senior SWE, built distributed caching layer serving 50M requests/day, reduced p99 latency by 40%\nCurrently founding engineer at startup, built the entire backend from scratch in FastAPI + PostgreSQL\nSkills: Python, Go, TypeScript, React, Kubernetes, AWS\nLinkedIn: linkedin.com/in/solomonjesse\nEducation: BSc Computer Science, University of Nairobi, 2018`}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600 resize-none"
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex gap-3 items-center flex-wrap">
            <button
              onClick={queue.length > 0 ? handleSendQueue : handlePasteSubmit}
              disabled={loading || (queue.length === 0 && !rawText.trim())}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-6 py-2.5 rounded-lg font-semibold text-sm transition-colors flex items-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                  </svg>
                  {loadingLabel}
                </>
              ) : (
                queue.length > 0
                  ? `Analyze ${queue.length} file${queue.length > 1 ? 's' : ''} →`
                  : 'Analyze My Profile →'
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Gap analysis + questions ── */}
      {step === 'gaps' && analysis && (
        <div className="flex flex-col gap-5">
          {/* Score bar */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-300">Profile Readiness</p>
              <span className={`text-lg font-bold ${scoreColor(analysis.score)}`}>{analysis.score}/100</span>
            </div>
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${scoreBg(analysis.score)}`}
                style={{ width: `${analysis.score}%` }}
              />
            </div>
            <p className="text-xs text-gray-500">{analysis.summary}</p>
          </div>

          {/* Gaps */}
          {analysis.gaps.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-2">
              <p className="text-sm font-medium text-gray-300 mb-1">What's missing</p>
              {analysis.gaps.map((gap, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-gray-400">
                  <span className="text-yellow-500 mt-0.5 flex-shrink-0">!</span>
                  <span>{gap}</span>
                </div>
              ))}
            </div>
          )}

          {/* Questions */}
          {analysis.questions.length > 0 && (
            <div className="flex flex-col gap-3">
              <p className="text-sm font-medium text-gray-300">Answer these to strengthen your profile</p>
              {analysis.questions.map((q, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-2">
                  <p className="text-xs text-blue-400 font-medium">{q.gap}</p>
                  <p className="text-sm text-gray-300">{q.question}</p>
                  <textarea
                    value={answers[i] ?? ''}
                    onChange={e => setAnswers(prev => ({ ...prev, [i]: e.target.value }))}
                    rows={3}
                    placeholder="Your answer…"
                    className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600 resize-none mt-1"
                  />
                </div>
              ))}
            </div>
          )}

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex gap-3 items-center">
            {analysis.questions.length > 0 && (
              <button
                onClick={handleAnswersSubmit}
                disabled={loading || Object.values(answers).every(a => !a.trim())}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-6 py-2.5 rounded-lg font-semibold text-sm transition-colors"
              >
                {loading ? loadingLabel : 'Submit Answers →'}
              </button>
            )}
            <button
              onClick={() => setStep('paste')}
              className="text-gray-500 hover:text-gray-300 text-sm transition-colors"
            >
              ← Paste more context
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3: Ready ── */}
      {step === 'ready' && analysis && (
        <div className="flex flex-col gap-5">
          <div className="bg-green-950/40 border border-green-800/50 rounded-lg p-5 flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="text-green-400 text-lg">✓</span>
              <p className="text-green-300 font-semibold">Profile Ready</p>
              <span className="ml-auto text-green-400 font-bold text-lg">{analysis.score}/100</span>
            </div>
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-green-500 transition-all" style={{ width: `${analysis.score}%` }} />
            </div>
            <p className="text-sm text-gray-400 mt-1">{analysis.summary}</p>
          </div>

          {analysis.gaps.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-2">Optional improvements</p>
              {analysis.gaps.map((gap, i) => (
                <p key={i} className="text-xs text-gray-600 py-0.5">· {gap}</p>
              ))}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={onReady}
              className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-2.5 rounded-lg font-semibold text-sm transition-colors"
            >
              Start Campaign →
            </button>
            <button
              onClick={() => setStep('gaps')}
              className="text-gray-500 hover:text-gray-300 text-sm transition-colors"
            >
              ← Improve further
            </button>
          </div>
        </div>
      )}

    </div>
  )
}
