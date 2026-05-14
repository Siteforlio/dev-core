// frontend/src/components/interview/SessionSetupForm.tsx
import { useState } from 'react'
import { useInterviewSession } from '../../hooks/useInterviewSession'

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
  hiring_manager: ['behavioral', 'technical'],
  skills_domain: ['technical'],
  panel_interview: ['behavioral', 'technical'],
  case_presentation: ['behavioral', 'technical'],
  final_executive: ['behavioral'],
  offer_negotiation: ['behavioral'],
}

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

export default function SessionSetupForm() {
  const { startSession } = useInterviewSession()
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [track, setTrack] = useState('technology')
  const [level, setLevel] = useState('mid_level')
  const [stage, setStage] = useState('hr_interview')
  const [jdText, setJdText] = useState('')
  const [managerName, setManagerName] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const canStart = company.trim() && role.trim()

  const handleStart = async () => {
    if (!canStart) return
    setLoading(true)
    setError('')
    try {
      const rounds = ROUND_MAP[stage] ?? ['behavioral']
      await startSession(company, role, rounds, track, level, stage, jdText || undefined, managerName || undefined)
    } catch {
      setError('Failed to start session. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const labelStyle: React.CSSProperties = {
    color: 'rgba(34,211,238,0.45)',
    fontFamily: 'monospace',
    fontSize: '10px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.16em',
  }

  return (
    <div className="flex flex-col gap-5 w-full" style={{ maxWidth: '440px' }}>
      <div>
        <p style={{ ...labelStyle, marginBottom: '4px' }}>Interview Prep</p>
        <h2 style={{ color: 'rgba(226,232,240,0.95)', fontFamily: 'monospace', fontSize: '20px', fontWeight: 700, letterSpacing: '0.04em' }}>
          Prepare for your interview
        </h2>
      </div>

      {error && <p style={{ color: '#f87171', fontSize: '12px', fontFamily: 'monospace' }}>{error}</p>}

      {/* Row 1: Company + Role */}
      <div className="flex gap-3">
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Company</label>
          <input style={inputBase} placeholder="e.g. Stripe" value={company} onChange={e => setCompany(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Role</label>
          <input style={inputBase} placeholder="e.g. CTO" value={role} onChange={e => setRole(e.target.value)} />
        </div>
      </div>

      {/* Row 2: Track */}
      <div className="flex flex-col gap-2">
        <label style={labelStyle}>Career Track</label>
        <div className="relative">
          <select style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
            value={track} onChange={e => setTrack(e.target.value)}>
            {CAREER_TRACKS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
        </div>
      </div>

      {/* Row 3: Level + Stage */}
      <div className="flex gap-3">
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Seniority Level</label>
          <div className="relative">
            <select style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
              value={level} onChange={e => setLevel(e.target.value)}>
              {LEVELS.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
          </div>
        </div>
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Interview Stage</label>
          <div className="relative">
            <select style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
              value={stage} onChange={e => setStage(e.target.value)}>
              {STAGES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
          </div>
        </div>
      </div>

      {/* Advanced toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(v => !v)}
        style={{ color: 'rgba(34,211,238,0.5)', fontFamily: 'monospace', fontSize: '11px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: 0 }}
      >
        {showAdvanced ? '▲' : '▼'} {showAdvanced ? 'Hide' : 'Add'} job description / manager (optional)
      </button>

      {showAdvanced && (
        <>
          <div className="flex flex-col gap-2">
            <label style={labelStyle}>Job Description</label>
            <textarea
              style={{ ...inputBase, height: '96px', resize: 'none' }}
              placeholder="Paste the JD here for personalized questions…"
              value={jdText}
              onChange={e => setJdText(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label style={labelStyle}>Hiring Manager Name (optional)</label>
            <input style={inputBase} placeholder="e.g. Jane Doe" value={managerName} onChange={e => setManagerName(e.target.value)} />
          </div>
        </>
      )}

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
