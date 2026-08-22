// frontend/src/components/interview/SessionSetupForm.tsx
import { useState } from 'react'
import { useInterviewSession } from '../../hooks/useInterviewSession'
import { apiFetch } from '../../lib/apiFetch'

// ── Constants ──────────────────────────────────────────────────────────────────

const CAREER_TRACKS = [
  { value: 'technology', label: 'Technology' },
  { value: 'finance_fintech', label: 'Finance & Fintech' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'business_consulting', label: 'Business & Consulting' },
  { value: 'sales_marketing', label: 'Sales & Marketing' },
  { value: 'design_creative', label: 'Design & Creative' },
  { value: 'legal_compliance', label: 'Legal & Compliance' },
  { value: 'hr_people', label: 'HR & People' },
  { value: 'education_training', label: 'Education & Training' },
  { value: 'operations_supply_chain', label: 'Operations & Supply Chain' },
]

const LEVELS = [
  { value: 'entry_junior', label: 'Entry / Junior' },
  { value: 'mid_level', label: 'Mid-level' },
  { value: 'senior', label: 'Senior' },
  { value: 'lead_manager', label: 'Lead / Manager' },
  { value: 'director_vp_csuite', label: 'Director / VP / C-Suite' },
]

const STAGES = [
  { value: 'phone_screen', label: 'Phone Screen' },
  { value: 'hr_interview', label: 'HR Interview' },
  { value: 'hiring_manager', label: 'Hiring Manager' },
  { value: 'skills_domain', label: 'Skills / Domain' },
  { value: 'panel_interview', label: 'Panel Interview' },
  { value: 'case_presentation', label: 'Case / Presentation' },
  { value: 'final_executive', label: 'Final / Executive' },
  { value: 'offer_negotiation', label: 'Offer Negotiation' },
]

const ROUND_MAP: Record<string, string[]> = {
  phone_screen: ['behavioral'],
  hr_interview: ['behavioral'],
  hiring_manager: ['behavioral', 'skills_task'],
  skills_domain: ['skills_domain'],
  panel_interview: ['behavioral', 'skills_task'],
  case_presentation: ['behavioral', 'skills_task'],
  final_executive: ['behavioral'],
  offer_negotiation: ['behavioral'],
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const inputBase: React.CSSProperties = {
  background: 'rgba(7,15,28,0.8)',
  border: '1px solid rgba(34,211,238,0.15)',
  color: 'rgba(226,232,240,0.9)',
  fontFamily: 'monospace',
  fontSize: '13px',
  padding: '10px 14px',
  borderRadius: '6px',
  outline: 'none',
  width: '100%',
}

const labelStyle: React.CSSProperties = {
  color: 'rgba(34,211,238,0.45)',
  fontFamily: 'monospace',
  fontSize: '10px',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.16em',
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function SessionSetupForm() {
  const { startSession } = useInterviewSession()

  // ── Intake state ──
  const [rawContext, setRawContext] = useState('')
  const [detecting, setDetecting] = useState(false)
  const [detected, setDetected] = useState(false)
  const [detectError, setDetectError] = useState('')

  // ── Extracted / editable params ──
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [track, setTrack] = useState('technology')
  const [level, setLevel] = useState('mid_level')
  const [stage, setStage] = useState('hr_interview')
  const [topics, setTopics] = useState<string[]>([])
  const [topicInput, setTopicInput] = useState('')
  const [aiSummary, setAiSummary] = useState('')
  const [jdText, setJdText] = useState('')

  // ── Launch state ──
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const canDetect = rawContext.trim().length > 20
  const canStart = company.trim() && role.trim()

  // ── AI detection ──────────────────────────────────────────────────────────

  const handleDetect = async () => {
    if (!canDetect) return
    setDetecting(true)
    setDetectError('')
    try {
      const res = await apiFetch('/api/v1/interview-sessions/interpret', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: rawContext }),
      })
      const { data, error: apiError } = await res.json()
      if (apiError) throw new Error(apiError.message ?? 'Detection failed')

      setCompany(data.company || '')
      setRole(data.role || '')
      setTrack(data.career_track || 'technology')
      setLevel(data.level || 'mid_level')
      setStage(data.interview_stage || 'hr_interview')
      setTopics(data.topics || [])
      setAiSummary(data.summary || '')
      // Keep raw context as jd_text so question generation can use it
      setJdText(rawContext)
      setDetected(true)
    } catch {
      setDetectError('Could not detect parameters. Try adding more detail or fill in manually below.')
    } finally {
      setDetecting(false)
    }
  }

  // ── Topics tag input ──────────────────────────────────────────────────────

  const addTopic = () => {
    const t = topicInput.trim()
    if (t && !topics.includes(t)) setTopics(prev => [...prev, t])
    setTopicInput('')
  }

  const removeTopic = (t: string) => setTopics(prev => prev.filter(x => x !== t))

  // ── Launch ────────────────────────────────────────────────────────────────

  const handleStart = async () => {
    if (!canStart) return
    setLoading(true)
    setError('')
    try {
      const rounds = ROUND_MAP[stage] ?? ['behavioral']
      await startSession(
        company, role, rounds, track, level, stage,
        jdText || undefined,
        undefined,
        topics.length ? topics : undefined,
      )
    } catch {
      setError('Failed to start session. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-5 w-full" style={{ maxWidth: '440px' }}>

      <div>
        <p style={{ ...labelStyle, marginBottom: '4px' }}>Interview Prep</p>
        <h2 style={{ color: 'rgba(226,232,240,0.95)', fontFamily: 'monospace', fontSize: '20px', fontWeight: 700, letterSpacing: '0.04em' }}>
          Prepare for your interview
        </h2>
      </div>

      {/* ── AI Intake ── */}
      <div className="flex flex-col gap-2">
        <label style={labelStyle}>Paste anything — JD, interview email, job page</label>
        <textarea
          style={{ ...inputBase, height: '110px', resize: 'none', lineHeight: 1.5 }}
          placeholder={`Paste the job description, interview invite, or any page about the interview.\n\nAI will extract company, role, topics, time limit, and more.`}
          value={rawContext}
          onChange={e => { setRawContext(e.target.value); if (detected) setDetected(false) }}
        />
        <button
          type="button"
          onClick={handleDetect}
          disabled={!canDetect || detecting}
          style={{
            alignSelf: 'flex-start',
            background: canDetect && !detecting ? 'rgba(34,211,238,0.1)' : 'rgba(34,211,238,0.04)',
            border: `1px solid ${canDetect && !detecting ? 'rgba(34,211,238,0.35)' : 'rgba(34,211,238,0.1)'}`,
            color: '#22d3ee',
            fontFamily: 'monospace',
            fontSize: '11px',
            fontWeight: 600,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            padding: '6px 14px',
            borderRadius: '6px',
            cursor: canDetect && !detecting ? 'pointer' : 'not-allowed',
            opacity: canDetect && !detecting ? 1 : 0.5,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          {detecting
            ? <><span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" /> Detecting…</>
            : '⚡ Detect Parameters'
          }
        </button>
        {detectError && (
          <p style={{ color: '#f87171', fontSize: '11px', fontFamily: 'monospace' }}>{detectError}</p>
        )}
      </div>

      {/* ── AI Summary pill ── */}
      {detected && aiSummary && (
        <div style={{
          background: 'rgba(34,211,238,0.06)',
          border: '1px solid rgba(34,211,238,0.18)',
          borderRadius: '6px',
          padding: '8px 12px',
          fontSize: '12px',
          color: 'rgba(34,211,238,0.75)',
          fontFamily: 'monospace',
          lineHeight: 1.5,
        }}>
          ✓ {aiSummary}
          <span style={{ color: 'rgba(34,211,238,0.35)', marginLeft: 8 }}>— adjust below if needed</span>
        </div>
      )}

      <div style={{ borderTop: '1px solid rgba(34,211,238,0.08)', marginTop: 2 }} />

      {error && <p style={{ color: '#f87171', fontSize: '12px', fontFamily: 'monospace' }}>{error}</p>}

      {/* ── Editable params ── */}

      {/* Company + Role */}
      <div className="flex gap-3">
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Company</label>
          <input style={inputBase} placeholder="e.g. Stripe" value={company} onChange={e => setCompany(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Role</label>
          <input style={inputBase} placeholder="e.g. Backend Engineer" value={role} onChange={e => setRole(e.target.value)} />
        </div>
      </div>

      {/* Career Track */}
      <div className="flex flex-col gap-2">
        <label style={labelStyle}>Career Track</label>
        <div className="relative">
          <select
            style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
            value={track}
            onChange={e => setTrack(e.target.value)}
          >
            {CAREER_TRACKS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
        </div>
      </div>

      {/* Level + Stage */}
      <div className="flex gap-3">
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Seniority Level</label>
          <div className="relative">
            <select
              style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
              value={level}
              onChange={e => setLevel(e.target.value)}
            >
              {LEVELS.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
          </div>
        </div>
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Interview Stage</label>
          <div className="relative">
            <select
              style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
              value={stage}
              onChange={e => setStage(e.target.value)}
            >
              {STAGES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
          </div>
        </div>
      </div>

      {/* Topics */}
      <div className="flex flex-col gap-2">
        <label style={labelStyle}>Topics to Test On</label>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            style={{ ...inputBase, flex: 1 }}
            placeholder="Add a topic and press Enter…"
            value={topicInput}
            onChange={e => setTopicInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTopic() } }}
          />
          <button
            type="button"
            onClick={addTopic}
            disabled={!topicInput.trim()}
            style={{
              background: 'rgba(34,211,238,0.08)',
              border: '1px solid rgba(34,211,238,0.2)',
              color: '#22d3ee',
              fontFamily: 'monospace',
              fontSize: '12px',
              padding: '0 12px',
              borderRadius: '6px',
              cursor: topicInput.trim() ? 'pointer' : 'not-allowed',
              opacity: topicInput.trim() ? 1 : 0.4,
              whiteSpace: 'nowrap',
            }}
          >
            + Add
          </button>
        </div>
        {topics.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {topics.map(t => (
              <span
                key={t}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  background: 'rgba(34,211,238,0.07)',
                  border: '1px solid rgba(34,211,238,0.18)',
                  borderRadius: '4px',
                  padding: '3px 8px 3px 10px',
                  fontSize: '11px',
                  color: 'rgba(34,211,238,0.8)',
                  fontFamily: 'monospace',
                }}
              >
                {t}
                <button
                  type="button"
                  onClick={() => removeTopic(t)}
                  style={{
                    background: 'none', border: 'none',
                    color: 'rgba(34,211,238,0.4)',
                    cursor: 'pointer', fontSize: '13px',
                    lineHeight: 1, padding: 0,
                  }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Launch */}
      <button
        disabled={!canStart || loading}
        onClick={handleStart}
        className="flex items-center justify-center gap-2 font-semibold text-xs uppercase tracking-[0.14em] py-3 rounded transition-all duration-150 disabled:opacity-30"
        style={{
          background: canStart ? 'rgba(34,211,238,0.1)' : 'rgba(34,211,238,0.04)',
          border: `1px solid ${canStart ? 'rgba(34,211,238,0.35)' : 'rgba(34,211,238,0.1)'}`,
          color: '#22d3ee',
          fontFamily: 'monospace',
        }}
      >
        {loading
          ? <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3" /></svg>
        }
        {loading ? 'Starting…' : 'Start Prep Session'}
      </button>

    </div>
  )
}
