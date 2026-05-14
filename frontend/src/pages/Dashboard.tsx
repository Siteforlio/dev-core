import { useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { useInterviewSession } from '../hooks/useInterviewSession'
import { useJobHunterStore } from '../store/jobHunterStore'
import { useJobHunter } from '../hooks/useJobHunter'
import Sidebar from '../components/job-hunter/Sidebar'
import SessionSetupForm from '../components/interview/SessionSetupForm'
import CampaignList from '../components/job-hunter/CampaignList'
import CampaignForm from '../components/job-hunter/CampaignForm'
import CampaignProfileBuilder from '../components/job-hunter/CampaignProfileBuilder'
import CampaignDashboard from '../components/job-hunter/CampaignDashboard'
import GlobalIntegrationsPanel from '../components/job-hunter/GlobalIntegrationsPanel'
import { SessionSetup } from '../components/devcore/SessionSetup'
import ProgressDashboard from '../components/interview/ProgressDashboard'
import type { Campaign } from '../types/jobHunter'

type Module = 'interview' | 'job-hunter' | 'settings'

export default function Dashboard() {
  const name = useAuthStore((s) => s.name)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const { startSession } = useInterviewSession()

  const [activeModule, setActiveModule] = useState<Module>('interview')
  const [showSessionSetup, setShowSessionSetup] = useState(false)

  const {
    activeView,
    selectedCampaignId,
    selectCampaign,
    setActiveView,
  } = useJobHunterStore()

  const { listCampaigns, getCampaignProfile } = useJobHunter()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loadingCampaigns, setLoadingCampaigns] = useState(false)
  const [newCampaign, setNewCampaign] = useState<Campaign | null>(null)

  useEffect(() => {
    if (activeModule !== 'job-hunter' || activeView !== 'campaigns') return
    setLoadingCampaigns(true)
    listCampaigns()
      .then(setCampaigns)
      .catch(() => {})
      .finally(() => setLoadingCampaigns(false))
  }, [activeModule, activeView])

  const handleCampaignCreated = (campaign: Campaign) => {
    setCampaigns((prev) => [campaign, ...prev])
    // Show profile builder before going to dashboard
    setNewCampaign(campaign)
    setActiveView('build-profile')
  }

  const handleCampaignDeleted = (campaignId: string) => {
    setCampaigns((prev) => prev.filter((c) => c.id !== campaignId))
  }

  const handleProfileReady = () => {
    if (newCampaign) {
      const id = newCampaign.id
      setNewCampaign(null)
      selectCampaign(id)
    }
  }

  const handleSelectCampaign = async (campaignId: string) => {
    try {
      const profile = await getCampaignProfile(campaignId)
      const hasMinimum = profile.full_name && profile.email &&
        (profile.skills as unknown[])?.length > 0 &&
        (profile.work_experience as unknown[])?.length > 0
      if (!hasMinimum) {
        const campaign = campaigns.find(c => c.id === campaignId) ?? { id: campaignId, name: '' }
        setNewCampaign(campaign as Campaign)
        setActiveView('build-profile')
        return
      }
    } catch {
      // If check fails, let them through — backend scrape guard is the real gate
    }
    selectCampaign(campaignId)
  }

  const handleStartInterviewPrep = (company: string, role: string) => {
    startSession(company, role, ['HR'], '', '', '').catch(() => {})
  }

  return (
    <div className="min-h-screen text-white flex flex-col" style={{ background: '#070f1c' }}>
      {/* Header */}
      <header
        className="flex items-center justify-between flex-shrink-0"
        style={{
          height: '56px',
          paddingRight: '0',
          background: '#050d18',
          borderBottom: '1px solid rgba(34,211,238,0.08)',
          // @ts-ignore
          WebkitAppRegion: 'drag',
        }}
      >
        {/* Logo slot — same width as sidebar (64px) so it lines up with the icons */}
        <div
          className="flex items-center justify-center flex-shrink-0"
          style={{ width: '64px', WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <img src="/devcore.png" width="42" height="42" alt="DevCore" style={{ objectFit: 'contain' }} />
        </div>
        <span
          className="flex-1 text-sm font-semibold tracking-[0.15em] uppercase"
          style={{ color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace' }}
        >
          {activeModule === 'interview' ? 'Interview Prep' : activeModule === 'job-hunter' ? 'Job Hunter' : 'Settings'}
        </span>
        {/* User chip */}
        <div
          className="flex items-center gap-3 px-3 py-1.5 rounded"
          style={{ background: 'rgba(34,211,238,0.05)', border: '1px solid rgba(34,211,238,0.1)', WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <div
            className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold flex-shrink-0"
            style={{ background: 'rgba(34,211,238,0.15)', color: '#22d3ee', fontFamily: 'monospace' }}
          >
            {(name ?? 'U')[0].toUpperCase()}
          </div>
          <span className="text-sm" style={{ color: 'rgba(148,163,184,0.8)', fontFamily: 'monospace' }}>
            {name}
          </span>
        </div>
        {/* Window controls */}
        <div
          className="flex items-center flex-shrink-0 ml-3"
          style={{ WebkitAppRegion: 'no-drag', height: '56px' } as React.CSSProperties}
        >
          {/* Minimize */}
          <button
            onClick={() => (window as any).electronAPI?.window?.minimize()}
            className="flex items-center justify-center transition-colors duration-100"
            style={{ width: '46px', height: '100%', color: 'rgba(148,163,184,0.5)' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = 'rgba(226,232,240,0.9)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'rgba(148,163,184,0.5)' }}
          >
            <svg width="11" height="11" viewBox="0 0 12 1" fill="currentColor"><rect width="12" height="1" rx="0.5"/></svg>
          </button>
          {/* Maximize */}
          <button
            onClick={() => (window as any).electronAPI?.window?.maximize()}
            className="flex items-center justify-center transition-colors duration-100"
            style={{ width: '46px', height: '100%', color: 'rgba(148,163,184,0.5)' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = 'rgba(226,232,240,0.9)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'rgba(148,163,184,0.5)' }}
          >
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2"><rect x="0.6" y="0.6" width="10.8" height="10.8" rx="1"/></svg>
          </button>
          {/* Close */}
          <button
            onClick={() => (window as any).electronAPI?.window?.close()}
            className="flex items-center justify-center transition-colors duration-100"
            style={{ width: '46px', height: '100%', color: 'rgba(148,163,184,0.5)' }}
            onMouseEnter={e => { e.currentTarget.style.background = '#e81123'; e.currentTarget.style.color = '#ffffff' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'rgba(148,163,184,0.5)' }}
          >
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><line x1="1" y1="1" x2="11" y2="11"/><line x1="11" y1="1" x2="1" y2="11"/></svg>
          </button>
        </div>
      </header>

      {/* Body: sidebar + content */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          activeModule={activeModule}
          onSelect={(mod) => {
            if (mod === 'job-hunter') setActiveView('campaigns')
            setActiveModule(mod)
          }}
          onLogout={clearAuth}
        />

        <main className="flex-1 overflow-y-auto">
          {activeModule === 'interview' ? (
            /* ── Interview Prep ── */
            <div className="flex h-full items-center justify-center p-8">
              <div className="flex gap-8 w-full max-w-5xl">
                <div style={{ flex: '0 0 440px' }}>
                  <div className="flex flex-col items-center gap-6">
                    <SessionSetupForm />
                    <div className="flex items-center gap-3 w-full max-w-sm">
                      <div className="flex-1 h-px" style={{ background: 'rgba(34,211,238,0.08)' }} />
                      <span className="text-[10px] font-mono uppercase tracking-[0.18em]" style={{ color: 'rgba(34,211,238,0.3)' }}>or</span>
                      <div className="flex-1 h-px" style={{ background: 'rgba(34,211,238,0.08)' }} />
                    </div>
                    <button
                      onClick={() => setShowSessionSetup(true)}
                      className="flex items-center gap-2.5 px-6 py-2.5 rounded-lg transition-all duration-150 w-full max-w-sm justify-center"
                      style={{
                        background: 'rgba(34,211,238,0.07)',
                        border: '1px solid rgba(34,211,238,0.2)',
                        color: '#22d3ee',
                        fontFamily: 'monospace',
                        fontSize: '11px',
                        fontWeight: 600,
                        letterSpacing: '0.14em',
                        textTransform: 'uppercase',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.background = 'rgba(34,211,238,0.13)'
                        e.currentTarget.style.borderColor = 'rgba(34,211,238,0.38)'
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.background = 'rgba(34,211,238,0.07)'
                        e.currentTarget.style.borderColor = 'rgba(34,211,238,0.2)'
                      }}
                    >
                      <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
                      Start DevCore Session
                    </button>
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <ProgressDashboard onStartNew={() => {}} />
                </div>
              </div>
            </div>
          ) : activeModule === 'settings' ? (
            /* ── Settings ── */
            <div className="p-6 h-full overflow-y-auto">
              <GlobalIntegrationsPanel />
            </div>
          ) : (
            /* ── Job Hunter ── */
            <div className="p-6 h-full flex flex-col gap-6">
              {activeView === 'create-campaign' ? (
                <CampaignForm onCreated={handleCampaignCreated} />
              ) : activeView === 'build-profile' && newCampaign ? (
                <CampaignProfileBuilder
                  campaignId={newCampaign.id}
                  campaignName={newCampaign.name}
                  onReady={handleProfileReady}
                />
              ) : activeView === 'dashboard' && selectedCampaignId ? (
                <CampaignDashboard
                  campaignId={selectedCampaignId}
                  onBack={() => setActiveView('campaigns')}
                  onStartInterviewPrep={handleStartInterviewPrep}
                  onGoToSettings={() => setActiveModule('settings')}
                />
              ) : loadingCampaigns ? (
                <div className="flex flex-1 items-center justify-center py-20">
                  <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <CampaignList
                  campaigns={campaigns}
                  onSelect={handleSelectCampaign}
                  onCreateNew={() => setActiveView('create-campaign')}
                  onDeleted={handleCampaignDeleted}
                />
              )}
            </div>
          )}
        </main>
      </div>
      {showSessionSetup && <SessionSetup onClose={() => setShowSessionSetup(false)} />}
    </div>
  )
}
