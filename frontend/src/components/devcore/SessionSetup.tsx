import React, { useState, useEffect } from 'react'
import { useOverlaySession } from '../../hooks/useOverlaySession'
import { useOverlayStore } from '../../store/overlayStore'
import type { SessionContext } from '../../types/devcore'

type SourceTab = 'job' | 'calendar' | 'describe'

interface AppliedJob {
  id: string
  title: string
  company: string
  status: string
  resumeText: string
  jdText: string
}

export function SessionSetup({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<SourceTab>('job')
  const [selectedJob, setSelectedJob] = useState<string | null>(null)
  const [description, setDescription] = useState('')
  const [files, setFiles] = useState<string[]>([])
  const [jobs, setJobs] = useState<AppliedJob[]>([])
  const { startSession } = useOverlaySession()
  const { setSessionId, setState } = useOverlayStore()

  useEffect(() => {
    const load = async () => {
      const token: string = await window.electronAPI?.getAccessToken?.() ?? ''
      return fetch('/api/v1/job-hunter/applications?status=interview,screening&limit=20', {
        headers: { Authorization: `Bearer ${token}` },
      })
    }
    load()
      .then(r => r.json())
      .then(json => setJobs((json.data ?? []).map((a: any) => ({
        id: a.id,
        title: a.job_title,
        company: a.company_name,
        status: a.status,
        resumeText: a.resume_text ?? '',
        jdText: a.jd_text ?? '',
      }))))
      .catch(() => setJobs([]))
  }, [])

  const selectedJobData = jobs.find(j => j.id === selectedJob)

  const handleStart = async () => {
    const ctx: SessionContext = {
      jobTitle:   tab === 'job' ? selectedJobData?.title ?? '' : '',
      company:    tab === 'job' ? selectedJobData?.company ?? '' : '',
      resumeText: tab === 'job' ? selectedJobData?.resumeText ?? '' : '',
      jdText:     tab === 'job' ? selectedJobData?.jdText ?? '' : description,
      files,
    }
    const token: string = await window.electronAPI?.getAccessToken?.() ?? ''
    const id = crypto.randomUUID()
    setSessionId(id)
    setState('listening')
    await startSession({ sessionId: id, context: ctx, audioSource: 'both', token })
    onClose()
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
          {/* Source tabs */}
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
          {/* Panel */}
          {tab === 'job' && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-[8.5px] uppercase tracking-widest text-white/30">Select from applied jobs</p>
              {jobs.length === 0 && (
                <p className="font-mono text-[9px] text-white/30 py-2">No interview-stage applications found. Use Describe tab instead.</p>
              )}
              {jobs.map(job => (
                <button
                  key={job.id}
                  onClick={() => setSelectedJob(job.id)}
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
                ? <><strong className="text-white/80">{selectedJobData.company} · {selectedJobData.title}</strong> — ready.</>
                : 'Select a context source to load session context.'}
            </p>
          </div>
        </div>
        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.07] bg-white/[0.01]">
          <span className="font-mono text-[9px] text-white/20">Ctrl+Shift+Space to toggle overlay</span>
          <button
            onClick={handleStart}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-violet-400 text-[#0a0014] font-display text-[11px] font-bold tracking-[0.1em] shadow-[0_0_20px_rgba(167,139,250,0.2)] hover:brightness-110 transition-all"
          >
            <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
            Start Session
          </button>
        </div>
      </div>
    </div>
  )
}
