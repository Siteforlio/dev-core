import { useState, useEffect } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'
import type { Campaign } from '../../types/jobHunter'

const COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'SE', name: 'Sweden' },
  { code: 'NO', name: 'Norway' },
  { code: 'DK', name: 'Denmark' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'IE', name: 'Ireland' },
  { code: 'SG', name: 'Singapore' },
  { code: 'IN', name: 'India' },
  { code: 'NG', name: 'Nigeria' },
  { code: 'KE', name: 'Kenya' },
  { code: 'ZA', name: 'South Africa' },
  { code: 'GH', name: 'Ghana' },
  { code: 'BR', name: 'Brazil' },
  { code: 'MX', name: 'Mexico' },
  { code: 'AR', name: 'Argentina' },
  { code: 'PL', name: 'Poland' },
  { code: 'PT', name: 'Portugal' },
  { code: 'ES', name: 'Spain' },
  { code: 'IT', name: 'Italy' },
  { code: 'NZ', name: 'New Zealand' },
  { code: 'JP', name: 'Japan' },
  { code: 'AE', name: 'UAE' },
  { code: 'IL', name: 'Israel' },
  { code: 'EE', name: 'Estonia' },
]

const WORK_TYPE_OPTIONS = [
  { value: 'remote', label: 'Remote', desc: 'Fully remote anywhere' },
  { value: 'hybrid', label: 'Hybrid', desc: 'Partial in-office' },
  { value: 'onsite', label: 'On-site', desc: 'In-person only' },
  { value: 'any', label: 'Any', desc: 'All arrangements' },
]

function toggle<T>(arr: T[], item: T): T[] {
  return arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item]
}

interface Props {
  onCreated: (campaign: Campaign) => void
}

export default function CampaignForm({ onCreated }: Props) {
  const { getCampaignMeta, createCampaign } = useJobHunter()

  const [allCategories, setAllCategories] = useState<string[]>([])
  const [name, setName] = useState('')
  const [categories, setCategories] = useState<string[]>([])
  const [categorySearch, setCategorySearch] = useState('')
  const [workTypes, setWorkTypes] = useState<string[]>(['remote'])
  const [anywhere, setAnywhere] = useState(false)
  const [country, setCountry] = useState('')
  const [countrySearch, setCountrySearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    getCampaignMeta()
      .then(({ categories }) => { if (!cancelled) setAllCategories(categories) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const filteredCategories = allCategories.filter(c =>
    c.toLowerCase().includes(categorySearch.toLowerCase())
  )

  const filteredCountries = COUNTRIES.filter(c =>
    c.name.toLowerCase().includes(countrySearch.toLowerCase()) ||
    c.code.toLowerCase().includes(countrySearch.toLowerCase())
  )

  const canSubmit = name.trim() && categories.length > 0 && workTypes.length > 0 && (anywhere || country)

  const handleSubmit = async () => {
    if (!canSubmit) return
    setLoading(true)
    setError('')
    try {
      const campaign = await createCampaign({
        name: name.trim(),
        categories,
        userCountry: anywhere ? undefined : country,
        anywhere,
        workTypes,
      })
      onCreated(campaign)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create campaign')
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto w-full px-4 py-8 flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold text-white">New Campaign</h2>
        <p className="text-gray-400 text-sm mt-1">
          Set your target roles and preferences. You'll build your profile next.
        </p>
      </div>

      <div className="flex flex-col gap-5">
        {/* Campaign Name */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-gray-400 uppercase tracking-wide font-medium">Campaign Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Senior Engineer 2026"
            className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-600"
          />
        </div>

        {/* Job Categories — multi-select */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs text-gray-400 uppercase tracking-wide font-medium">Job Categories</label>
            {categories.length > 0 && (
              <span className="text-xs text-blue-400 font-mono">{categories.length} selected</span>
            )}
          </div>
          <input
            type="text"
            value={categorySearch}
            onChange={e => setCategorySearch(e.target.value)}
            placeholder="Search categories…"
            className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-600"
          />
          <div className="grid grid-cols-2 gap-1.5 max-h-52 overflow-y-auto pr-1 [&::-webkit-scrollbar]:hidden">
            {filteredCategories.map(cat => {
              const selected = categories.includes(cat)
              return (
                <button
                  key={cat}
                  onClick={() => setCategories(prev => toggle(prev, cat))}
                  className={`text-left px-3 py-2 rounded-lg text-xs border transition-colors ${
                    selected
                      ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                      : 'border-gray-800 bg-gray-900 text-gray-400 hover:border-gray-600'
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    {selected && (
                      <svg width="10" height="10" viewBox="0 0 12 12" fill="none" className="flex-shrink-0">
                        <path d="M2 6l3 3 5-5" stroke="#60a5fa" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )}
                    {cat}
                  </span>
                </button>
              )
            })}
          </div>
          {filteredCategories.length === 0 && categorySearch && (
            <p className="text-xs text-gray-600">No categories match "{categorySearch}"</p>
          )}
          {categories.length === 0 && !categorySearch && (
            <p className="text-xs text-gray-600">Select one or more categories — the scraper searches all of them.</p>
          )}
        </div>

        {/* Work Arrangements — multi-select */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs text-gray-400 uppercase tracking-wide font-medium">Work Arrangement</label>
            {workTypes.length > 1 && (
              <span className="text-xs text-blue-400 font-mono">{workTypes.length} selected</span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {WORK_TYPE_OPTIONS.map(opt => {
              const selected = workTypes.includes(opt.value)
              return (
                <button
                  key={opt.value}
                  onClick={() => {
                    if (opt.value === 'any') {
                      // "Any" is exclusive — selecting it clears others
                      setWorkTypes(selected ? [] : ['any'])
                    } else {
                      // Selecting a specific type clears "any"
                      const without = workTypes.filter(w => w !== 'any')
                      setWorkTypes(toggle(without, opt.value))
                    }
                  }}
                  className={`text-left px-3 py-2.5 rounded-lg border transition-colors ${
                    selected
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-gray-800 bg-gray-900 hover:border-gray-600'
                  }`}
                >
                  <p className={`text-xs font-medium ${selected ? 'text-blue-300' : 'text-gray-300'}`}>
                    {opt.label}
                  </p>
                  <p className="text-xs text-gray-600 mt-0.5">{opt.desc}</p>
                </button>
              )
            })}
          </div>
        </div>

        {/* Country */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs text-gray-400 uppercase tracking-wide font-medium">Location</label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={anywhere}
                onChange={(e) => setAnywhere(e.target.checked)}
                className="w-3.5 h-3.5 rounded border-gray-600 bg-gray-800 accent-blue-500"
              />
              <span className="text-xs text-gray-400">Anywhere in the world</span>
            </label>
          </div>

          {!anywhere && (
            <div className="flex flex-col gap-1.5">
              <input
                type="text"
                value={countrySearch}
                onChange={(e) => setCountrySearch(e.target.value)}
                placeholder="Search country…"
                className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-600"
              />
              <div className="grid grid-cols-2 gap-1 max-h-40 overflow-y-auto pr-1 [&::-webkit-scrollbar]:hidden">
                {filteredCountries.map(c => (
                  <button
                    key={c.code}
                    onClick={() => setCountry(c.code)}
                    className={`text-left px-2.5 py-1.5 rounded text-xs border transition-colors ${
                      country === c.code
                        ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                        : 'border-gray-800 bg-gray-900 text-gray-400 hover:border-gray-700'
                    }`}
                  >
                    <span className="font-mono text-gray-500 mr-1">{c.code}</span>{c.name}
                  </button>
                ))}
              </div>
              {country && (
                <p className="text-xs text-gray-500">
                  Selected: <span className="text-gray-300">{COUNTRIES.find(c => c.code === country)?.name ?? country}</span>
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit || loading}
        className="self-start bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-6 py-2.5 rounded-lg font-semibold transition-colors"
      >
        {loading ? 'Creating…' : 'Create Campaign →'}
      </button>
    </div>
  )
}
