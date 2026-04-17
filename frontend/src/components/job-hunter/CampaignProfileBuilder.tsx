import { useState, useEffect, useRef } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'

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

export default function CampaignProfileBuilder({ campaignId, campaignName, onReady }: Props) {
  const { getCampaignProfile, upsertCampaignProfile, analyzeProfileGaps, processRawContext } = useJobHunter()

  const [step, setStep] = useState<Step>('paste')
  const [rawText, setRawText] = useState('')
  const [analysis, setAnalysis] = useState<GapAnalysis | null>(null)
  const [profile, setProfile] = useState<Record<string, unknown>>({})
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [loadingLabel, setLoadingLabel] = useState('')
  const [error, setError] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    getCampaignProfile(campaignId).then(p => {
      setProfile(p)
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
    if (!rawText.trim()) return
    setLoading(true)
    setLoadingLabel('Extracting your info…')
    setError('')
    try {
      const result = await processRawContext(campaignId, rawText)
      setAnalysis(result.gaps as GapAnalysis)
      setProfile(prev => ({ ...prev, ...result.extracted }))
      setStep(result.gaps.is_ready ? 'ready' : 'gaps')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to process context')
    } finally {
      setLoading(false)
      setLoadingLabel('')
    }
  }

  const handleAnswersSubmit = async () => {
    if (!analysis) return
    setLoading(true)
    setLoadingLabel('Updating profile…')
    setError('')
    try {
      // Convert Q&A answers back into structured profile fields as best we can
      // We append answers as raw_context additions and let AI re-extract
      const combined = (profile.raw_context as string || '') + '\n\n' +
        analysis.questions.map((q, i) => `Q: ${q.question}\nA: ${answers[i] ?? ''}`).join('\n\n')

      const result = await processRawContext(campaignId, combined)
      setAnalysis(result.gaps as GapAnalysis)
      if (result.gaps.is_ready) {
        setStep('ready')
      } else {
        setAnswers({})
        setError('')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update profile')
    } finally {
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
          The AI reads your info, identifies what's missing, and asks targeted questions to build a 90%+ ATS-matched resume.
        </p>
      </div>

      {/* ── Step 1: Paste context ── */}
      {step === 'paste' && (
        <div className="flex flex-col gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-3">
            <p className="text-sm text-gray-300 font-medium">Paste anything about yourself</p>
            <p className="text-xs text-gray-500">
              Copy-paste from your LinkedIn profile, old CV, portfolio page, or just describe your experience in plain text. The more detail the better — the AI extracts everything it needs.
            </p>
            <textarea
              ref={textareaRef}
              value={rawText}
              onChange={e => setRawText(e.target.value)}
              rows={12}
              placeholder={`Example:\n\nSolomon Jesse\nsenior engineer with 6 years exp\nWorked at Google 2021–2023 as Senior SWE, built distributed caching layer serving 50M requests/day, reduced p99 latency by 40%\nCurrently founding engineer at startup, built the entire backend from scratch in FastAPI + PostgreSQL\nSkills: Python, Go, TypeScript, React, Kubernetes, AWS\nLinkedIn: linkedin.com/in/solomonjesse\nEducation: BSc Computer Science, University of Nairobi, 2018`}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600 resize-none"
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex gap-3 items-center">
            <button
              onClick={handlePasteSubmit}
              disabled={!rawText.trim() || loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-6 py-2.5 rounded-lg font-semibold text-sm transition-colors"
            >
              {loading ? loadingLabel : 'Analyze My Profile →'}
            </button>
            <button
              onClick={() => { setStep('gaps'); loadAnalysis() }}
              disabled={loading}
              className="text-gray-500 hover:text-gray-300 text-sm transition-colors"
            >
              Fill in details manually →
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

      {/* Loading overlay */}
      {loading && !analysis && (
        <div className="flex items-center gap-3 text-gray-400 text-sm">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          {loadingLabel}
        </div>
      )}
    </div>
  )
}
