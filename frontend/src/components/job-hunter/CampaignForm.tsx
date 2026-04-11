import { useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'
import type { Campaign } from '../../types/jobHunter'

interface Props {
  onCreated: (campaign: Campaign) => void
}

export default function CampaignForm({ onCreated }: Props) {
  const { createCampaign } = useJobHunter()
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [country, setCountry] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const canSubmit = name.trim() && category.trim() && country.trim()

  const handleSubmit = async () => {
    if (!canSubmit) return
    setLoading(true)
    setError('')
    try {
      const campaign = await createCampaign({
        name: name.trim(),
        broadCategory: category.trim(),
        userCountry: country.trim(),
      })
      onCreated(campaign)
    } catch {
      setError('Failed to create campaign. Please check the backend is running.')
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto w-full px-4 py-8 flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold text-white">New Campaign</h2>
        <p className="text-gray-400 text-sm mt-1">
          The AI infers sub-categories from your skills and starts applying automatically.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400 uppercase tracking-wide">Campaign Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Campaign name"
            className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-600"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400 uppercase tracking-wide">Job Category</label>
          <input
            type="text"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Job category (e.g. Software Engineering)"
            className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-600"
          />
          <p className="text-xs text-gray-600">
            AI will refine this into sub-categories based on your skills.
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400 uppercase tracking-wide">Your Country</label>
          <input
            type="text"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="Country code (e.g. US, GB, DE)"
            className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-600"
          />
          <p className="text-xs text-gray-600">
            Used to filter onsite roles. Remote roles are always included.
          </p>
        </div>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit || loading}
        className="self-start bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-6 py-2.5 rounded-lg font-semibold transition-colors"
      >
        {loading ? 'Launching…' : 'Launch Campaign'}
      </button>
    </div>
  )
}
