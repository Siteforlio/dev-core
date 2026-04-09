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

  return (
    <div className="flex flex-col gap-4 p-8 max-w-md w-full">
      <h2 className="text-xl font-bold text-white">Prepare for an Interview</h2>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400 uppercase tracking-wide">Company</label>
        <select
          className="bg-gray-800 text-white p-2 rounded border border-gray-700 focus:border-blue-500 outline-none"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          <option value="">Select company</option>
          {companies.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} — {c.industry}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400 uppercase tracking-wide">Target Role</label>
        <select
          className="bg-gray-800 text-white p-2 rounded border border-gray-700 focus:border-blue-500 outline-none"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      <button
        disabled={!selected || loading}
        onClick={handleStart}
        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white p-2 rounded font-semibold transition-colors"
      >
        {loading ? 'Loading…' : 'Start Prep Session'}
      </button>
    </div>
  )
}
