import React, { useState, useEffect } from 'react'
import { useOverlaySession } from '../../hooks/useOverlaySession'
import { useOverlayStore } from '../../store/overlayStore'
import { useAuthStore } from '../../store/authStore'
import { apiFetch } from '../../lib/apiFetch'
import type { SessionContext, AssessmentMode } from '../../types/devcore'

type SourceTab = 'job' | 'calendar' | 'describe'

interface AppliedJob {
  id: string
  title: string
  company: string
  status: string
  resumeText: string
  jdText: string
}

const ASSESSMENT_MODES: { key: AssessmentMode; label: string; sub: string; color: string; glow: string; bg: string; border: string; icon: React.ReactNode }[] = [
  {
    key: 'present',
    label: 'Present',
    sub: 'General meeting',
    color: '#2dd4bf',
    glow: 'rgba(45,212,191,0.15)',
    bg: 'rgba(45,212,191,0.07)',
    border: 'rgba(45,212,191,0.25)',
    icon: (
      <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
    ),
  },
  {
    key: 'coding',
    label: 'Coding',
    sub: 'LeetCode / DSA',
    color: '#fbbf24',
    glow: 'rgba(251,191,36,0.15)',
    bg: 'rgba(251,191,36,0.07)',
    border: 'rgba(251,191,36,0.25)',
    icon: (
      <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
        <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
      </svg>
    ),
  },
  {
    key: 'live',
    label: 'Live Coding',
    sub: 'Project build',
    color: '#34d399',
    glow: 'rgba(52,211,153,0.15)',
    bg: 'rgba(52,211,153,0.07)',
    border: 'rgba(52,211,153,0.25)',
    icon: (
      <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
        <rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/>
      </svg>
    ),
  },
  {
    key: 'ai_model',
    label: 'AI Model',
    sub: 'Degraded AI',
    color: '#38bdf8',
    glow: 'rgba(56,189,248,0.15)',
    bg: 'rgba(56,189,248,0.07)',
    border: 'rgba(56,189,248,0.25)',
    icon: (
      <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
        <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"/>
        <circle cx="9" cy="14" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="14" r="1" fill="currentColor" stroke="none"/>
      </svg>
    ),
  },
]

export function SessionSetup({ onClose }: { onClose: () => void }) {
  const [tab, setTab]                   = useState<SourceTab>('job')
  const [selectedJob, setSelectedJob]   = useState<string | null>(null)
  const [description, setDescription]   = useState('')
  const [files, setFiles]               = useState<string[]>([])
  const [jobs, setJobs]                 = useState<AppliedJob[]>([])
  const [starting, setStarting]         = useState(false)
  const [loadingContext, setLoadingContext] = useState(false)

  // Assessment mode state — 'present' is the default/floor
  const [assessmentMode, setAssessmentMode] = useState<AssessmentMode>('present')
  const [projectRoot, setProjectRoot]       = useState('')

  const { startSession }  = useOverlaySession()
  const token             = useAuthStore((s) => s.accessToken)
  const audioSource       = useOverlayStore((s) => s.audioSource)
  const micDeviceId       = useOverlayStore((s) => s.micDeviceId)
  const sysDeviceId       = useOverlayStore((s) => s.sysDeviceId)
  const setStoreMode      = useOverlayStore((s) => s.setAssessmentMode)

  useEffect(() => {
    if (!token) return
    apiFetch('/api/v1/job-hunter/applications?status=interview,screening&limit=20')
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(json => setJobs((json.data ?? []).map((a: any) => ({
        id: a.application_id,
        title: a.job_title,
        company: a.company,
        status: a.status,
        resumeText: '',
        jdText: '',
      }))))
      .catch(() => setJobs([]))
  }, [token])

  const selectJob = async (id: string) => {
    setSelectedJob(id)
    if (!token) return
    setLoadingContext(true)
    try {
      const r = await apiFetch(`/api/v1/job-hunter/applications/${id}/context`)
      if (!r.ok) return
      const json = await r.json()
      setJobs(prev => prev.map(j =>
        j.id === id ? { ...j, resumeText: json.resume_text ?? '', jdText: json.jd_text ?? '' } : j
      ))
    } catch { /* non-fatal */ } finally {
      setLoadingContext(false)
    }
  }

  const selectedJobData = jobs.find(j => j.id === selectedJob)

  // Clicking an active mode goes back to 'present' (the floor), not null
  const toggleAssessmentMode = (mode: AssessmentMode) => {
    setAssessmentMode(prev => prev === mode ? 'present' : mode)
  }

  const handleStart = async () => {
    if (starting) return
    setStarting(true)
    try {
      const ctx: SessionContext = {
        jobTitle:       tab === 'job' ? selectedJobData?.title ?? '' : '',
        company:        tab === 'job' ? selectedJobData?.company ?? '' : '',
        resumeText:     tab === 'job' ? selectedJobData?.resumeText ?? '' : '',
        jdText:         tab === 'job' ? selectedJobData?.jdText ?? '' : description,
        files,
        assessmentMode: assessmentMode,
        projectRoot:    assessmentMode === 'live' ? projectRoot.trim() : undefined,
      }
      const id = crypto.randomUUID()
      setStoreMode(assessmentMode)
      await startSession({ sessionId: id, context: ctx, audioSource, micDeviceId, sysDeviceId, token: token ?? '' })
      onClose()
    } catch (err) {
      console.error('[devcore] startSession failed:', err)
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-[14px] w-[520px] overflow-hidden shadow-[0_24px_64px_rgba(0,0,0,0.8)]">

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.07] bg-white/[0.015]">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)]" />
            <span className="font-display text-[11px] font-extrabold tracking-[0.15em] text-violet-400">DEVCORE</span>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/30">New Session</span>
        </div>

        {/* Body */}
        <div className="p-4 flex flex-col gap-4">

          {/* Context source tabs */}
          <div>
            <p className="font-mono text-[8.5px] uppercase tracking-widest text-white/30 mb-2">Context source</p>
            <div className="flex gap-2">
              {([['job','Applied Job'], ['calendar','Calendar'], ['describe','Describe']] as [SourceTab, string][]).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`flex-1 py-3 rounded-lg border text-[9px] font-mono uppercase tracking-wider transition-all ${tab === key ? 'border-violet-400/25 bg-violet-400/10 text-violet-400' : 'border-white/[0.07] bg-white/[0.025] text-white/30 hover:bg-white/[0.045]'}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="h-px bg-white/[0.07]" />

          {/* Context panel */}
          {tab === 'job' && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-[8.5px] uppercase tracking-widest text-white/30">Select from applied jobs</p>
              {jobs.length === 0 && (
                <p className="font-mono text-[9px] text-white/30 py-2">No interview-stage applications found. Use Describe tab instead.</p>
              )}
              {jobs.map(job => (
                <button
                  key={job.id}
                  onClick={() => selectJob(job.id)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border text-left transition-all ${selectedJob === job.id ? 'border-violet-400/25 bg-violet-400/10' : 'border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.04]'}`}
                >
                  <div className="w-8 h-8 rounded-md bg-white/[0.06] border border-white/[0.07] flex items-center justify-center font-display text-[11px] font-bold text-white/50 flex-shrink-0">{job.company[0]}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] text-white/90 font-medium truncate">{job.title}</p>
                    <p className="font-mono text-[9px] text-white/30 mt-0.5">{job.company}</p>
                  </div>
                  <span className="font-mono text-[8px] px-2 py-1 rounded-full border border-emerald-400/25 bg-emerald-400/[0.08] text-emerald-400 flex-shrink-0">{job.status}</span>
                </button>
              ))}
            </div>
          )}
          {tab === 'describe' && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-[8.5px] uppercase tracking-widest text-white/30">Describe the interview</p>
              <div className="bg-white/[0.025] border border-white/[0.07] rounded-lg p-3 focus-within:border-violet-400/25 transition-all">
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="e.g. Senior backend role at Stripe, system design round..."
                  className="w-full bg-transparent border-none outline-none resize-none text-[12px] text-white/90 placeholder-white/20 leading-relaxed min-h-[80px]"
                />
              </div>
            </div>
          )}
          {tab === 'calendar' && (
            <div className="flex items-center justify-center py-6">
              <p className="font-mono text-[10px] text-white/30">Connect a CalDAV calendar in Settings to see upcoming events.</p>
            </div>
          )}

          {/* Confirmation strip */}
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-emerald-400/15 bg-emerald-400/5">
            <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-emerald-400 flex-shrink-0"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <p className="text-[11px] text-white/50">
              {selectedJobData
                ? loadingContext
                  ? <><strong className="text-white/80">{selectedJobData.company} · {selectedJobData.title}</strong> — loading context…</>
                  : <><strong className="text-white/80">{selectedJobData.company} · {selectedJobData.title}</strong>{selectedJobData.jdText ? ' — JD + resume loaded.' : ' — ready.'}</>
                : 'Select a context source to load session context.'}
            </p>
          </div>

          {/* ── Assessment Mode ── */}
          <div className="h-px bg-white/[0.07]" />
          <div>
            <div className="flex items-center gap-2 mb-2.5">
              <p className="font-mono text-[8.5px] uppercase tracking-widest text-white/30">Assessment Mode</p>
              {assessmentMode !== 'present' && (
                <span className="font-mono text-[7.5px] px-1.5 py-0.5 rounded border border-amber-400/30 bg-amber-400/10 text-amber-400 uppercase tracking-wider">
                  assessment
                </span>
              )}
            </div>

            <div className="flex gap-2">
              {ASSESSMENT_MODES.map(({ key, label, sub, icon, color, bg, border, glow }) => {
                const active = assessmentMode === key
                return (
                  <button
                    key={key}
                    onClick={() => toggleAssessmentMode(key)}
                    className="flex-1 flex flex-col items-center gap-2 py-3 px-2 rounded-lg transition-all duration-150"
                    style={{
                      background: active ? bg : 'rgba(255,255,255,0.02)',
                      border: `1px solid ${active ? border : 'rgba(255,255,255,0.06)'}`,
                      color: active ? color : 'rgba(255,255,255,0.25)',
                      boxShadow: active ? `0 0 16px ${glow}` : 'none',
                    }}
                    onMouseEnter={e => {
                      if (!active) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
                        e.currentTarget.style.color = 'rgba(255,255,255,0.45)'
                      }
                    }}
                    onMouseLeave={e => {
                      if (!active) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.02)'
                        e.currentTarget.style.color = 'rgba(255,255,255,0.25)'
                      }
                    }}
                  >
                    <span>{icon}</span>
                    <span className="font-mono text-[9px] uppercase tracking-wider font-semibold">{label}</span>
                    <span className="font-mono text-[7.5px]" style={{ color: active ? `${color}99` : 'rgba(255,255,255,0.18)' }}>{sub}</span>
                  </button>
                )
              })}
            </div>

            {/* Live Coding — project folder input */}
            {assessmentMode === 'live' && (
              <div className="mt-2.5 bg-white/[0.02] border border-amber-400/15 rounded-lg px-3 py-2 focus-within:border-amber-400/30 transition-all">
                <p className="font-mono text-[7.5px] uppercase tracking-widest text-amber-400/50 mb-1.5">Project folder path</p>
                <input
                  type="text"
                  value={projectRoot}
                  onChange={e => setProjectRoot(e.target.value)}
                  placeholder="C:\Users\me\project  or  /Users/me/project"
                  className="w-full bg-transparent border-none outline-none text-[11px] text-white/80 placeholder-white/20 font-mono"
                  spellCheck={false}
                  autoComplete="off"
                />
              </div>
            )}

            {/* Coding mode — informational hint */}
            {assessmentMode === 'coding' && (
              <div className="mt-2.5 flex items-start gap-2 px-3 py-2 rounded-lg border border-amber-400/15 bg-amber-400/[0.04]">
                <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-amber-400/60 flex-shrink-0 mt-0.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                <p className="font-mono text-[8.5px] text-white/35 leading-relaxed">
                  Agent will read the problem from screen, extract visible test cases, generate an optimal solution and test it locally before surfacing it to you.
                </p>
              </div>
            )}

            {/* AI Model mode — informational hint */}
            {assessmentMode === 'ai_model' && (
              <div className="mt-2.5 flex items-start gap-2 px-3 py-2 rounded-lg border border-amber-400/15 bg-amber-400/[0.04]">
                <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-amber-400/60 flex-shrink-0 mt-0.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                <p className="font-mono text-[8.5px] text-white/35 leading-relaxed">
                  Agent will profile the AI model, generate optimized prompts for you to type, evaluate its output behind the scenes and coach you through re-prompting.
                </p>
              </div>
            )}
          </div>

        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.07] bg-white/[0.01]">
          <span className="font-mono text-[9px] text-white/20">Ctrl+Shift+Space to toggle overlay</span>
          {(() => {
            const m = ASSESSMENT_MODES.find(m => m.key === assessmentMode)!
            return (
              <button
                onClick={handleStart}
                disabled={starting}
                className="flex items-center gap-2 px-5 py-2 rounded-lg font-mono text-[10px] font-bold tracking-[0.12em] uppercase transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  background: m.bg,
                  border: `1px solid ${m.border}`,
                  color: m.color,
                  boxShadow: `0 0 20px ${m.glow}`,
                }}
                onMouseEnter={e => { e.currentTarget.style.filter = 'brightness(1.15)' }}
                onMouseLeave={e => { e.currentTarget.style.filter = 'none' }}
              >
                <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/>
                </svg>
                {starting ? 'Starting…' : assessmentMode === 'present' ? 'Start Session' : 'Start Assessment'}
              </button>
            )
          })()}
        </div>

      </div>
    </div>
  )
}
