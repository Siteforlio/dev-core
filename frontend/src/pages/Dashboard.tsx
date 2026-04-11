import { useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { useInterviewSession } from '../hooks/useInterviewSession'
import { useJobHunterStore } from '../store/jobHunterStore'
import { useJobHunter } from '../hooks/useJobHunter'
import Sidebar from '../components/job-hunter/Sidebar'
import CompanySelector from '../components/interview/CompanySelector'
import ProfileOnboarding from '../components/job-hunter/ProfileOnboarding'
import CampaignList from '../components/job-hunter/CampaignList'
import CampaignForm from '../components/job-hunter/CampaignForm'
import CampaignDashboard from '../components/job-hunter/CampaignDashboard'
import type { Campaign } from '../types/jobHunter'

type Module = 'interview' | 'job-hunter'

export default function Dashboard() {
  const name = useAuthStore((s) => s.name)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const { startSession } = useInterviewSession()

  const [activeModule, setActiveModule] = useState<Module>('interview')
  const [interviewStarting, setInterviewStarting] = useState(false)
  const [interviewError, setInterviewError] = useState('')

  const {
    activeView,
    selectedCampaignId,
    profileComplete,
    selectCampaign,
    setProfileComplete,
    setActiveView,
  } = useJobHunterStore()

  const { listCampaigns } = useJobHunter()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loadingCampaigns, setLoadingCampaigns] = useState(false)

  useEffect(() => {
    if (activeModule !== 'job-hunter' || activeView !== 'campaigns') return
    setLoadingCampaigns(true)
    listCampaigns()
      .then(setCampaigns)
      .catch(() => {})
      .finally(() => setLoadingCampaigns(false))
  }, [activeModule, activeView])

  const handleInterviewSelect = async (company: string, role: string, rounds: string[]) => {
    setInterviewStarting(true)
    setInterviewError('')
    try {
      await startSession(company, role, rounds.length > 0 ? rounds : ['HR', 'behavioral', 'technical'])
    } catch {
      setInterviewError('Failed to start session. Is the backend running?')
      setInterviewStarting(false)
    }
  }

  const handleCampaignCreated = (campaign: Campaign) => {
    setCampaigns((prev) => [campaign, ...prev])
    selectCampaign(campaign.id)
  }

  const handleStartInterviewPrep = (_personaString: string, company: string, _role: string) => {
    // Switch to interview module and start a session pre-loaded with company context
    setActiveModule('interview')
    startSession(company, 'Interview Prep', ['HR']).catch(() => {})
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 flex-shrink-0">
        <span className="font-bold text-base tracking-tight">Developer Core</span>
        <div className="flex items-center gap-4">
          <span className="text-gray-500 text-sm">{name}</span>
          <button
            className="text-xs text-gray-600 hover:text-white underline transition-colors"
            onClick={clearAuth}
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Body: sidebar + content */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeModule={activeModule} onSelect={setActiveModule} />

        <main className="flex-1 overflow-y-auto">
          {activeModule === 'interview' ? (
            /* ── Interview Prep ── */
            <div className="flex h-full items-center justify-center p-8">
              {interviewStarting ? (
                <div className="text-gray-400 flex flex-col items-center gap-3">
                  <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">Generating your interview session…</span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  {interviewError && <p className="text-red-400 text-sm">{interviewError}</p>}
                  <CompanySelector onSelect={handleInterviewSelect} />
                </div>
              )}
            </div>
          ) : (
            /* ── Job Hunter ── */
            <div className="p-6 h-full flex flex-col gap-6">
              {!profileComplete ? (
                <ProfileOnboarding
                  onComplete={() => {
                    setProfileComplete(true)
                    setActiveView('campaigns')
                  }}
                />
              ) : activeView === 'create-campaign' ? (
                <CampaignForm onCreated={handleCampaignCreated} />
              ) : activeView === 'dashboard' && selectedCampaignId ? (
                <CampaignDashboard
                  campaignId={selectedCampaignId}
                  onStartInterviewPrep={handleStartInterviewPrep}
                />
              ) : loadingCampaigns ? (
                <div className="flex flex-1 items-center justify-center py-20">
                  <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <CampaignList
                  campaigns={campaigns}
                  onSelect={selectCampaign}
                  onCreateNew={() => setActiveView('create-campaign')}
                />
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
