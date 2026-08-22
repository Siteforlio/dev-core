import { useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { useOverlayStore } from '../store/overlayStore'
import { useInterviewSession } from '../hooks/useInterviewSession'
import { useJobHunterStore } from '../store/jobHunterStore'
import { useJobHunter } from '../hooks/useJobHunter'
import { useApiKeys, type ApiKeyInfo } from '../hooks/useApiKeys'
import Sidebar from '../components/job-hunter/Sidebar'
import SimulationBuilder from '../components/interview/SimulationBuilder'
import SessionSetupForm from '../components/interview/SessionSetupForm'
import CampaignList from '../components/job-hunter/CampaignList'
import CampaignForm from '../components/job-hunter/CampaignForm'
import CampaignProfileBuilder from '../components/job-hunter/CampaignProfileBuilder'
import CampaignDashboard from '../components/job-hunter/CampaignDashboard'
import GlobalIntegrationsPanel from '../components/job-hunter/GlobalIntegrationsPanel'
import SavedLoginSettings from '../components/SavedLoginSettings'
import ApiKeysPanel from '../components/ApiKeysPanel'
import { SessionSetup } from '../components/devcore/SessionSetup'
import DebriefDashboard from './DebriefDashboard'
import type { Campaign } from '../types/jobHunter'

type Module = 'debrief' | 'interview' | 'job-hunter' | 'settings'

/* ── Required-key names (at least one LLM must be set) ── */
const LLM_KEYS = ['deepseek_api_key', 'anthropic_api_key', 'gemini_api_key', 'groq_api_key', 'openai_api_key']

export default function Dashboard() {
  const name = useAuthStore((s) => s.name)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const { startSession } = useInterviewSession()
  const { getStatus: getKeyStatus } = useApiKeys()

  const [activeModule, setActiveModule] = useState<Module>('debrief')
  const [interviewMode, setInterviewMode] = useState<'simulation' | 'prep'>('simulation')
  const [showSessionSetup, setShowSessionSetup] = useState(false)
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null)
  const [missingLLM, setMissingLLM] = useState(false)
  const [keyCheckDone, setKeyCheckDone] = useState(false)


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

  /* ── Sync session state started from overlay into Dashboard's overlayStore ── */
  useEffect(() => {
    const api = (window as any).electronAPI?.devcore
    if (!api) return

    // On mount: verify real session status and clear stale state
    api.getStatus?.().then((s: { connected: boolean }) => {
      if (!s?.connected) {
        useOverlayStore.getState().setSessionId(null)
        useOverlayStore.getState().setSessionStartedAt(null)
      }
    }).catch(() => {})

    if (!api.onSessionStarted) return
    const offStarted = api.onSessionStarted(({ sessionId, startedAt }: { sessionId: string; startedAt: number }) => {
      useOverlayStore.getState().setSessionId(sessionId)
      useOverlayStore.getState().setSessionStartedAt(startedAt)
    })
    const offEnded = api.onSessionEnded?.(() => {
      useOverlayStore.getState().setSessionId(null)
      useOverlayStore.getState().setSessionStartedAt(null)
      useOverlayStore.getState().setState('idle')
    })
    return () => { offStarted?.(); offEnded?.() }
  }, [])

  /* ── Check for missing LLM key on mount + when returning from settings ── */
  useEffect(() => {
    getKeyStatus()
      .then((keys: ApiKeyInfo[]) => {
        const hasAnyLLM = keys.some(k => LLM_KEYS.includes(k.key_name) && k.configured)
        setMissingLLM(!hasAnyLLM)
        setKeyCheckDone(true)
      })
      .catch(() => setKeyCheckDone(true))
  }, [activeModule])

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
      // Profile exists if raw_context has been submitted or is_complete flag is set
      const hasProfile = !!(profile as any).raw_context?.trim() || !!(profile as any).is_complete
      if (!hasProfile) {
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
    <div className="text-white flex flex-col" style={{ background: '#070f1c', height: '100vh', overflow: 'hidden' }}>
      {/* Header — sticky, never scrolls */}
      <header
        className="flex items-center justify-between flex-shrink-0"
        style={{
          height: '56px',
          paddingRight: '0',
          background: '#050d18',
          borderBottom: '1px solid rgba(34,211,238,0.08)',
          position: 'sticky',
          top: 0,
          zIndex: 20,
          // @ts-ignore
          WebkitAppRegion: 'drag',
        }}
      >
        {/* Logo slot — same width as sidebar (64px) so it lines up with the icons */}
        <div
          className="flex items-center justify-center flex-shrink-0"
          style={{ width: '64px', WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <img src="./devcore.png" width="42" height="42" alt="DevCore" style={{ objectFit: 'contain' }} />
        </div>
        <span
          className="flex-1 text-sm font-semibold tracking-[0.15em] uppercase"
          style={{ color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace' }}
        >
          {activeModule === 'debrief' ? 'Dashboard' : activeModule === 'interview' ? 'Interview Prep' : activeModule === 'job-hunter' ? 'Job Hunter' : 'Settings'}
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
          {activeModule === 'debrief' ? (
            /* ── Debrief Dashboard ── */
            <DebriefDashboard onStartSession={() => setShowSessionSetup(true)} pendingSessionId={pendingSessionId} />
          ) : activeModule === 'interview' ? (
            /* ── Interview — tab toggle between Simulation and Prep ── */
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {/* Mode toggle */}
              <div style={{ display: 'flex', gap: 4, padding: '12px 20px', borderBottom: '1px solid rgba(34,211,238,0.07)', flexShrink: 0 }}>
                {(['simulation', 'prep'] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setInterviewMode(m)}
                    style={{
                      padding: '5px 16px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                      fontFamily: 'monospace', letterSpacing: '0.08em', textTransform: 'uppercase',
                      cursor: 'pointer', border: 'none',
                      background: interviewMode === m ? 'rgba(34,211,238,0.12)' : 'transparent',
                      color: interviewMode === m ? '#22d3ee' : 'rgba(148,163,184,0.5)',
                      outline: interviewMode === m ? '1px solid rgba(34,211,238,0.25)' : 'none',
                    }}
                  >
                    {m === 'simulation' ? 'Interview Simulation' : 'Interview Prep'}
                  </button>
                ))}
              </div>
              {interviewMode === 'simulation' ? (
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <SimulationBuilder />
                </div>
              ) : (
                <div style={{ flex: 1, overflowY: 'auto', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px' }}>
                  <SessionSetupForm />
                </div>
              )}
            </div>
          ) : activeModule === 'settings' ? (
            /* ── Settings ── */
            <div>
              <div className="p-6" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <SavedLoginSettings />
              </div>
              <ApiKeysPanel />
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
      {showSessionSetup && (
        <SessionSetup
          onClose={() => setShowSessionSetup(false)}
          onSessionStarted={(id) => {
            setPendingSessionId(id)
            setShowSessionSetup(false)
            // Set session state immediately so the hero button enters loading state
            // before the IPC devcore:session:started event arrives from the overlay.
            useOverlayStore.getState().setSessionId(id)
            useOverlayStore.getState().setSessionStartedAt(Date.now())
          }}
        />
      )}

      {/* ── Missing API Key Alert ── */}
      {keyCheckDone && missingLLM && activeModule !== 'settings' && (
        <>
          <style>{`
            @keyframes ak-pulse { 0%,100%{box-shadow:0 0 30px rgba(248,113,113,0.15)} 50%{box-shadow:0 0 60px rgba(248,113,113,0.3)} }
            @keyframes ak-slide { from{opacity:0;transform:translate(-50%,-50%) scale(0.92)} to{opacity:1;transform:translate(-50%,-50%) scale(1)} }
            @keyframes ak-icon-pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.12)} }
            @keyframes ak-scan { 0%{left:-100%} 100%{left:100%} }
          `}</style>
          <div style={{
            position: 'fixed', inset: 0, zIndex: 100,
            background: 'rgba(2,8,16,0.85)',
            backdropFilter: 'blur(8px)',
          }}>
            {/* Modal card */}
            <div style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%,-50%)',
              width: '480px', maxWidth: 'calc(100vw - 48px)',
              background: 'linear-gradient(165deg, #0c1524 0%, #070f1c 100%)',
              border: '1px solid rgba(248,113,113,0.25)',
              borderRadius: '20px',
              padding: '48px 40px 40px',
              animation: 'ak-slide 0.35s cubic-bezier(0.16,1,0.3,1) both, ak-pulse 3s ease-in-out infinite',
              overflow: 'hidden',
            }}>
              {/* Scanning line accent */}
              <div style={{
                position: 'absolute', top: 0, left: 0, width: '60%', height: '1px',
                background: 'linear-gradient(90deg, transparent, rgba(248,113,113,0.6), transparent)',
                animation: 'ak-scan 3s linear infinite',
                pointerEvents: 'none',
              }} />

              {/* Corner accents */}
              <svg style={{ position: 'absolute', top: 12, left: 12, opacity: 0.3 }} width="28" height="28" viewBox="0 0 28 28" fill="none">
                <path d="M0 28L0 0L28 0" stroke="#f87171" strokeWidth="1.5"/>
              </svg>
              <svg style={{ position: 'absolute', bottom: 12, right: 12, opacity: 0.3 }} width="28" height="28" viewBox="0 0 28 28" fill="none">
                <path d="M28 0L28 28L0 28" stroke="#f87171" strokeWidth="1.5"/>
              </svg>

              {/* Icon */}
              <div style={{
                width: '64px', height: '64px', borderRadius: '16px', margin: '0 auto 28px',
                background: 'rgba(248,113,113,0.08)',
                border: '1px solid rgba(248,113,113,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                animation: 'ak-icon-pulse 2s ease-in-out infinite',
              }}>
                <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
              </div>

              {/* Header */}
              <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: '8px',
                  background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.2)',
                  borderRadius: '6px', padding: '4px 12px', marginBottom: '16px',
                }}>
                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#f87171', boxShadow: '0 0 8px #f87171' }} />
                  <span style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#f87171' }}>
                    Action Required
                  </span>
                </div>
                <h2 style={{
                  fontFamily: '"Orbitron", monospace', fontWeight: 700, fontSize: '20px',
                  letterSpacing: '0.08em', color: 'rgba(226,232,240,0.95)', lineHeight: 1.2,
                }}>
                  No AI Provider Configured
                </h2>
              </div>

              {/* Body */}
              <div style={{
                background: 'rgba(248,113,113,0.04)', border: '1px solid rgba(248,113,113,0.1)',
                borderRadius: '12px', padding: '20px', marginBottom: '28px',
              }}>
                <p style={{
                  fontFamily: 'monospace', fontSize: '12px', color: 'rgba(226,232,240,0.75)',
                  lineHeight: 1.8, textAlign: 'center',
                }}>
                  DevCore needs at least one LLM API key to power interviews, job applications, and the overlay assistant.
                </p>
                <div style={{
                  marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px',
                }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '10px 14px', borderRadius: '8px',
                    background: 'rgba(34,211,238,0.04)', border: '1px solid rgba(34,211,238,0.1)',
                  }}>
                    <div style={{
                      width: '28px', height: '28px', borderRadius: '6px',
                      background: 'rgba(77,107,254,0.12)', border: '1px solid rgba(77,107,254,0.25)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="#4D6BFE" opacity="0.3"/>
                        <path d="M12 5a7 7 0 100 14 7 7 0 000-14zm0 2.5a1.25 1.25 0 110 2.5 1.25 1.25 0 010-2.5zM10 12h4v5h-1.5v-3.5h-1V17H10v-5z" fill="#4D6BFE"/>
                      </svg>
                    </div>
                    <div>
                      <p style={{ fontFamily: 'monospace', fontSize: '11px', fontWeight: 700, color: 'rgba(226,232,240,0.9)', marginBottom: '1px' }}>
                        DeepSeek
                      </p>
                      <p style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(100,116,139,0.5)' }}>
                        Recommended — free tier available at platform.deepseek.com
                      </p>
                    </div>
                    <span style={{
                      marginLeft: 'auto', fontSize: '9px', fontFamily: 'monospace', fontWeight: 700,
                      color: 'rgba(52,211,153,0.7)', letterSpacing: '0.1em', textTransform: 'uppercase',
                      flexShrink: 0,
                    }}>
                      FREE
                    </span>
                  </div>
                  <p style={{
                    fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.4)',
                    textAlign: 'center', marginTop: '4px',
                  }}>
                    Or configure any other provider: Anthropic, Gemini, Groq, or OpenAI
                  </p>
                </div>
              </div>

              {/* CTA button */}
              <button
                onClick={() => setActiveModule('settings')}
                style={{
                  width: '100%', padding: '14px',
                  background: 'rgba(248,113,113,0.12)',
                  border: '1px solid rgba(248,113,113,0.35)',
                  borderRadius: '12px',
                  color: '#f87171',
                  fontFamily: '"Orbitron", monospace', fontWeight: 700,
                  fontSize: '11px', letterSpacing: '0.18em', textTransform: 'uppercase',
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
                  transition: 'all 0.2s',
                  boxShadow: '0 0 20px rgba(248,113,113,0.08)',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(248,113,113,0.2)'; e.currentTarget.style.boxShadow = '0 0 32px rgba(248,113,113,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(248,113,113,0.12)'; e.currentTarget.style.boxShadow = '0 0 20px rgba(248,113,113,0.08)' }}
              >
                Open Settings
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                </svg>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
