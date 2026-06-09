import { useState, useEffect } from 'react'

const eAPI = () => (window as any).electronAPI
const SAVE_CREDS_SETTING = 'devcore_save_creds_enabled'

export default function SavedLoginSettings() {
  const [enabled, setEnabled]       = useState(() => localStorage.getItem(SAVE_CREDS_SETTING) !== '0')
  const [savedEmail, setSavedEmail] = useState<string | null>(null)
  const [clearing, setClearing]     = useState(false)
  const [status, setStatus]         = useState<string | null>(null)

  const isElectron = !!eAPI()?.loadCreds

  useEffect(() => {
    if (!isElectron) return
    eAPI().loadCreds().then((c: { email: string } | null) => {
      setSavedEmail(c?.email ?? null)
    }).catch(() => {})
  }, [])

  const toggleEnabled = () => {
    const next = !enabled
    setEnabled(next)
    localStorage.setItem(SAVE_CREDS_SETTING, next ? '1' : '0')
    setStatus(next ? 'Saved credentials enabled.' : 'Saved credentials disabled.')
    setTimeout(() => setStatus(null), 2500)
  }

  const handleClear = async () => {
    setClearing(true)
    try {
      await eAPI()?.clearCreds?.()
      setSavedEmail(null)
      setStatus('Saved credentials cleared.')
      setTimeout(() => setStatus(null), 2500)
    } finally {
      setClearing(false)
    }
  }

  return (
    <div style={{
      background: 'rgba(34,211,238,0.025)',
      border: '1px solid rgba(34,211,238,0.1)',
      borderRadius: '12px',
      padding: '24px',
    }}>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
        <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(34,211,238,0.07)', border: '1px solid rgba(34,211,238,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2"/>
            <path d="M7 11V7a5 5 0 0110 0v4"/>
            <circle cx="12" cy="16" r="1" fill="#22d3ee"/>
          </svg>
        </div>
        <div>
          <p style={{ fontFamily: '"Orbitron", monospace', fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', color: 'rgba(226,232,240,0.9)' }}>
            Saved Login
          </p>
          <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.5)', marginTop: '2px' }}>
            One-click sign-in with encrypted credentials
          </p>
        </div>
      </div>

      <div style={{ height: '1px', background: 'linear-gradient(90deg, rgba(34,211,238,0.1), transparent)', marginBottom: '20px' }} />

      {/* Toggle row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <p style={{ fontFamily: 'monospace', fontSize: '12px', color: 'rgba(226,232,240,0.8)', marginBottom: '3px' }}>
            Enable saved credentials
          </p>
          <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.45)' }}>
            Show quick-login button on sign-in screen
          </p>
        </div>
        <button
          onClick={toggleEnabled}
          style={{
            width: '44px', height: '24px', borderRadius: '12px', flexShrink: 0,
            background: enabled ? 'rgba(34,211,238,0.2)' : 'rgba(255,255,255,0.06)',
            border: `1px solid ${enabled ? 'rgba(34,211,238,0.4)' : 'rgba(255,255,255,0.1)'}`,
            cursor: 'pointer',
            position: 'relative',
            transition: 'all 0.2s',
            padding: 0,
          }}
        >
          <div style={{
            position: 'absolute',
            top: '3px',
            left: enabled ? '22px' : '3px',
            width: '16px', height: '16px',
            borderRadius: '50%',
            background: enabled ? '#22d3ee' : 'rgba(100,116,139,0.4)',
            boxShadow: enabled ? '0 0 8px rgba(34,211,238,0.5)' : 'none',
            transition: 'all 0.2s',
          }} />
        </button>
      </div>

      {/* Saved credential info */}
      {isElectron ? (
        savedEmail ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px',
            background: 'rgba(52,211,153,0.05)',
            border: '1px solid rgba(52,211,153,0.15)',
            borderRadius: '8px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#34d399', boxShadow: '0 0 6px #34d399', flexShrink: 0 }} />
              <div>
                <p style={{ fontFamily: 'monospace', fontSize: '11px', color: '#34d399', marginBottom: '1px' }}>
                  {savedEmail}
                </p>
                <p style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(52,211,153,0.45)', letterSpacing: '0.1em' }}>
                  CREDENTIALS SAVED · DPAPI ENCRYPTED
                </p>
              </div>
            </div>
            <button
              onClick={handleClear}
              disabled={clearing}
              style={{
                background: 'transparent',
                border: '1px solid rgba(248,113,113,0.2)',
                borderRadius: '6px',
                color: 'rgba(248,113,113,0.6)',
                fontFamily: 'monospace',
                fontSize: '10px',
                letterSpacing: '0.1em',
                padding: '5px 10px',
                cursor: clearing ? 'wait' : 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(248,113,113,0.08)'; e.currentTarget.style.borderColor = 'rgba(248,113,113,0.4)'; e.currentTarget.style.color = '#f87171' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'rgba(248,113,113,0.2)'; e.currentTarget.style.color = 'rgba(248,113,113,0.6)' }}
            >
              {clearing ? 'Clearing…' : 'Clear'}
            </button>
          </div>
        ) : (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '12px 16px',
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: '8px',
          }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'rgba(100,116,139,0.3)', flexShrink: 0 }} />
            <p style={{ fontFamily: 'monospace', fontSize: '11px', color: 'rgba(100,116,139,0.4)' }}>
              No credentials saved. You'll be prompted after your next login.
            </p>
          </div>
        )
      ) : (
        <div style={{
          padding: '12px 16px',
          background: 'rgba(251,191,36,0.04)',
          border: '1px solid rgba(251,191,36,0.12)',
          borderRadius: '8px',
        }}>
          <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(251,191,36,0.5)' }}>
            Saved login requires the Electron desktop app.
          </p>
        </div>
      )}

      {/* Status toast */}
      {status && (
        <p style={{ fontFamily: 'monospace', fontSize: '10px', color: '#22d3ee', marginTop: '12px', letterSpacing: '0.06em' }}>
          {status}
        </p>
      )}
    </div>
  )
}
