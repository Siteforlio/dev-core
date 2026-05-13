import { useState, useEffect } from 'react'
import { useAuthStore } from '../../store/authStore'

interface Props {
  onSelect: (company: string, role: string, rounds: string[]) => void
}

const ROLES = [
  'Software Engineer',
  'Senior Software Engineer',
  'Staff Engineer',
  'Engineering Manager',
  'Data Scientist',
  'Product Manager',
]

export default function CompanySelector({ onSelect }: Props) {
  const [companies, setCompanies] = useState<{ name: string; industry: string }[]>([])
  const [selected, setSelected] = useState('')
  const [role, setRole] = useState(ROLES[0])
  const [loading, setLoading] = useState(false)
  const token = useAuthStore((s) => s.accessToken)

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/companies', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((b) => setCompanies(b.data ?? []))
      .catch(() => {})
  }, [token])

  const handleStart = async () => {
    if (!selected) return
    setLoading(true)
    const res = await fetch(`http://localhost:8000/api/v1/companies/${encodeURIComponent(selected)}/rounds`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const { data: rounds } = await res.json()
    setLoading(false)
    onSelect(selected, role, rounds)
  }

  const selectBase: React.CSSProperties = {
    background: 'rgba(7,15,28,0.8)',
    border: '1px solid rgba(34,211,238,0.15)',
    color: 'rgba(226,232,240,0.9)',
    fontFamily: 'monospace',
    fontSize: '13px',
    padding: '10px 14px',
    borderRadius: '6px',
    outline: 'none',
    width: '100%',
    appearance: 'none',
    WebkitAppearance: 'none',
    cursor: 'pointer',
  }

  return (
    <div
      className="flex flex-col gap-5 w-full"
      style={{ maxWidth: '420px' }}
    >
      {/* Title */}
      <div>
        <p
          className="text-[10px] font-semibold uppercase tracking-[0.2em] mb-1"
          style={{ color: 'rgba(34,211,238,0.5)', fontFamily: 'monospace' }}
        >
          Interview Prep
        </p>
        <h2
          className="text-xl font-bold"
          style={{ color: 'rgba(226,232,240,0.95)', fontFamily: 'monospace', letterSpacing: '0.04em' }}
        >
          Start a prep session
        </h2>
      </div>

      {/* Company */}
      <div className="flex flex-col gap-2">
        <label
          className="text-[10px] font-semibold uppercase tracking-[0.16em]"
          style={{ color: 'rgba(34,211,238,0.45)', fontFamily: 'monospace' }}
        >
          Company
        </label>
        <div className="relative">
          <select
            style={selectBase}
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            onFocus={e => (e.currentTarget.style.borderColor = 'rgba(34,211,238,0.4)')}
            onBlur={e => (e.currentTarget.style.borderColor = 'rgba(34,211,238,0.15)')}
          >
            <option value="">Select company…</option>
            {companies.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name} — {c.industry}
              </option>
            ))}
          </select>
          {/* Custom chevron */}
          <svg
            className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
            width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </div>

      {/* Role */}
      <div className="flex flex-col gap-2">
        <label
          className="text-[10px] font-semibold uppercase tracking-[0.16em]"
          style={{ color: 'rgba(34,211,238,0.45)', fontFamily: 'monospace' }}
        >
          Target Role
        </label>
        <div className="relative">
          <select
            style={selectBase}
            value={role}
            onChange={(e) => setRole(e.target.value)}
            onFocus={e => (e.currentTarget.style.borderColor = 'rgba(34,211,238,0.4)')}
            onBlur={e => (e.currentTarget.style.borderColor = 'rgba(34,211,238,0.15)')}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
          <svg
            className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
            width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </div>

      {/* Submit */}
      <button
        disabled={!selected || loading}
        onClick={handleStart}
        className="flex items-center justify-center gap-2 font-semibold text-xs uppercase tracking-[0.14em] py-3 rounded transition-all duration-150 disabled:opacity-30"
        style={{
          background: selected ? 'rgba(34,211,238,0.1)' : 'rgba(34,211,238,0.04)',
          border: `1px solid ${selected ? 'rgba(34,211,238,0.35)' : 'rgba(34,211,238,0.1)'}`,
          color: '#22d3ee',
          fontFamily: 'monospace',
        }}
        onMouseEnter={e => {
          if (!selected || loading) return
          e.currentTarget.style.background = 'rgba(34,211,238,0.16)'
          e.currentTarget.style.borderColor = 'rgba(34,211,238,0.5)'
        }}
        onMouseLeave={e => {
          e.currentTarget.style.background = selected ? 'rgba(34,211,238,0.1)' : 'rgba(34,211,238,0.04)'
          e.currentTarget.style.borderColor = selected ? 'rgba(34,211,238,0.35)' : 'rgba(34,211,238,0.1)'
        }}
      >
        {loading ? (
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
        ) : (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        )}
        {loading ? 'Loading…' : 'Start Prep Session'}
      </button>
    </div>
  )
}
