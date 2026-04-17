import { useState, useEffect } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'
import { useIntegrations } from '../../hooks/useIntegrations'

interface Props {
  campaignId: string
  onGoToGlobalSettings?: () => void
}

export default function CampaignSettings({ campaignId, onGoToGlobalSettings }: Props) {
  const { getCredentialsStatus, setCampaignToggles } = useJobHunter()
  const { getStatus } = useIntegrations()

  const [globalStatus, setGlobalStatus] = useState({ emailConfigured: false, caldavConfigured: false, linkedinConfigured: false })
  const [toggles, setToggles] = useState({ email_enabled: true, caldav_enabled: true, linkedin_enabled: true })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getStatus().then(setGlobalStatus).catch(() => {})
    getCredentialsStatus(campaignId).then((s) => {
      // credential status doubles as configured status — not toggle state
      // we just need the global status for display
    }).catch(() => {})
  }, [campaignId])

  const handleToggle = async (key: keyof typeof toggles) => {
    const next = { ...toggles, [key]: !toggles[key] }
    setToggles(next)
    setSaving(true)
    setSaved(false)
    try {
      await setCampaignToggles(campaignId, next)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      // revert
      setToggles(toggles)
    } finally {
      setSaving(false)
    }
  }

  const integrations = [
    {
      key: 'email_enabled' as const,
      label: 'Email Monitoring',
      description: 'Track replies, interview invites, and rejections',
      configured: globalStatus.emailConfigured,
    },
    {
      key: 'caldav_enabled' as const,
      label: 'Calendar Sync',
      description: 'Auto-schedule interview events to your calendar',
      configured: globalStatus.caldavConfigured,
    },
    {
      key: 'linkedin_enabled' as const,
      label: 'LinkedIn Scraping',
      description: 'Discover jobs and hiring managers on LinkedIn',
      configured: globalStatus.linkedinConfigured,
    },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Integrations</h3>
        {saving && <span className="text-xs text-gray-500">Saving…</span>}
        {saved && !saving && <span className="text-xs text-green-400">Saved</span>}
      </div>

      {integrations.map(({ key, label, description, configured }) => (
        <div key={key} className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm text-white font-medium">{label}</p>
              {!configured && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-500">Not configured</span>
              )}
            </div>
            <p className="text-xs text-gray-500 truncate">{description}</p>
          </div>
          <button
            onClick={() => handleToggle(key)}
            disabled={!configured}
            title={configured ? undefined : 'Configure in Settings first'}
            className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 ${
              !configured
                ? 'bg-gray-800 cursor-not-allowed opacity-40'
                : toggles[key]
                ? 'bg-blue-600'
                : 'bg-gray-700'
            }`}
          >
            <span
              className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                toggles[key] ? 'translate-x-4' : 'translate-x-0.5'
              }`}
            />
          </button>
        </div>
      ))}

      {(!globalStatus.emailConfigured || !globalStatus.caldavConfigured || !globalStatus.linkedinConfigured) && (
        <p className="text-xs text-gray-600">
          Some integrations are not configured.{' '}
          {onGoToGlobalSettings ? (
            <button
              onClick={onGoToGlobalSettings}
              className="text-blue-500 hover:text-blue-400 underline transition-colors"
            >
              Go to Settings
            </button>
          ) : (
            'Open Settings from the sidebar to connect them.'
          )}
        </p>
      )}
    </div>
  )
}
