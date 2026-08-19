import { useState, useEffect, useRef } from 'react'
import { useIntegrations } from '../../hooks/useIntegrations'

/* ── Underline input ── */
function Field({
  label, value, onChange, placeholder, type = 'text',
}: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string
}) {
  const [focused, setFocused] = useState(false)
  return (
    <div style={{ position: 'relative', paddingBottom: '2px' }}>
      <label style={{
        display: 'block',
        fontSize: '9px',
        fontFamily: 'monospace',
        fontWeight: 700,
        letterSpacing: '0.18em',
        textTransform: 'uppercase',
        color: focused ? 'rgba(34,211,238,0.7)' : 'rgba(148,163,184,0.35)',
        marginBottom: '6px',
        transition: 'color 0.15s',
      }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          background: 'transparent',
          border: 'none',
          borderBottom: `1px solid ${focused ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.08)'}`,
          color: 'rgba(226,232,240,0.9)',
          fontFamily: 'monospace',
          fontSize: '12px',
          padding: '4px 0 8px',
          outline: 'none',
          width: '100%',
          transition: 'border-color 0.15s',
        }}
      />
      {/* animated underline on focus */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        height: '1px',
        width: focused ? '100%' : '0%',
        background: 'linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2))',
        transition: 'width 0.25s ease',
        boxShadow: '0 0 8px rgba(34,211,238,0.5)',
      }} />
    </div>
  )
}

interface IntegrationCardProps {
  icon: React.ReactNode
  title: string
  subtitle: string
  tag: string
  configured: boolean
  open: boolean
  onToggle: () => void
  children: React.ReactNode
  accentColor: string
}

function IntegrationCard({ icon, title, subtitle, tag, configured, open, onToggle, children, accentColor }: IntegrationCardProps) {
  return (
    <div style={{
      position: 'relative',
      background: 'rgba(255,255,255,0.025)',
      backdropFilter: 'blur(12px)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '16px',
      overflow: 'hidden',
      transition: 'border-color 0.2s',
      ...(open ? { borderColor: `${accentColor}30` } : {}),
    }}>
      {/* left accent bar */}
      <div style={{
        position: 'absolute',
        left: 0,
        top: 0,
        bottom: 0,
        width: '3px',
        background: open ? accentColor : 'transparent',
        boxShadow: open ? `0 0 12px ${accentColor}80` : 'none',
        transition: 'all 0.2s',
      }} />

      {/* Header row */}
      <div className="flex items-center gap-5" style={{ padding: '20px 24px 20px 28px' }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '12px',
          background: `${accentColor}12`,
          border: `1px solid ${accentColor}25`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="flex items-center gap-2">
            <p style={{ fontSize: '14px', fontFamily: 'monospace', fontWeight: 700, color: 'rgba(226,232,240,0.95)', letterSpacing: '0.02em' }}>
              {title}
            </p>
            <span style={{
              fontSize: '9px', fontFamily: 'monospace', fontWeight: 700,
              color: `${accentColor}80`,
              background: `${accentColor}10`,
              border: `1px solid ${accentColor}20`,
              padding: '2px 7px', borderRadius: '4px',
              letterSpacing: '0.14em', textTransform: 'uppercase',
            }}>{tag}</span>
          </div>
          <p style={{ fontSize: '11px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.6)', marginTop: '2px' }}>
            {subtitle}
          </p>
        </div>

        <div className="flex items-center gap-3" style={{ flexShrink: 0 }}>
          {configured && (
            <div className="flex items-center gap-1.5" style={{ color: '#34d399', fontSize: '11px', fontFamily: 'monospace' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>Live</span>
            </div>
          )}
          <button
            onClick={onToggle}
            style={{
              background: 'transparent',
              border: `1px solid ${open ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.07)'}`,
              color: open ? 'rgba(226,232,240,0.7)' : 'rgba(100,116,139,0.6)',
              fontFamily: 'monospace',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              padding: '6px 14px',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = 'rgba(226,232,240,0.9)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = open ? 'rgba(226,232,240,0.7)' : 'rgba(100,116,139,0.6)' }}
          >
            {open ? '✕ Close' : configured ? 'Update' : 'Set up →'}
          </button>
        </div>
      </div>

      {/* Expanded */}
      {open && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', padding: '24px 28px 28px' }}>
          {children}
        </div>
      )}
    </div>
  )
}

export default function GlobalIntegrationsPanel() {
  const {
    status, setup, loading, error: hookError,
    getStatus, getSetup,
    connectGoogle, connectMicrosoft,
    disconnectGoogle, disconnectMicrosoft,
    setLinkedIn, testLinkedIn,
  } = useIntegrations()

  const [googleOpen, setGoogleOpen] = useState(false)
  const [microsoftOpen, setMicrosoftOpen] = useState(false)
  const [linkedinOpen, setLinkedInOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savingLabel, setSavingLabel] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [linkedinMode, setLinkedInMode] = useState<'cookie' | 'password'>('cookie')
  const [linkedinForm, setLinkedInForm] = useState({ email: '', password: '', session_cookie: '' })

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollAttemptsRef = useRef(0)

  useEffect(() => {
    getStatus().catch(() => {})
    getSetup().catch(() => {})
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [])

  const startPolling = () => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    pollAttemptsRef.current = 0
    pollIntervalRef.current = setInterval(async () => {
      pollAttemptsRef.current += 1
      try {
        const s = await getStatus()
        if (s.googleConfigured || s.microsoftConfigured) {
          clearInterval(pollIntervalRef.current!)
          pollIntervalRef.current = null
        }
      } catch {
        // ignore poll errors
      }
      if (pollAttemptsRef.current >= 40) {
        clearInterval(pollIntervalRef.current!)
        pollIntervalRef.current = null
      }
    }, 3000)
  }

  const saveLinkedIn = async () => {
    setSaving(true); setError(''); setSuccess('')
    const creds = linkedinMode === 'cookie'
      ? { session_cookie: linkedinForm.session_cookie }
      : { email: linkedinForm.email, password: linkedinForm.password }
    try {
      setSavingLabel('Authenticating…'); await testLinkedIn(creds)
      setSavingLabel('Saving…'); await setLinkedIn(creds)
      setSuccess('LinkedIn connected.'); setLinkedInOpen(false)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
    finally { setSaving(false); setSavingLabel('') }
  }

  const SaveBtn = ({ onClick, disabled }: { onClick: () => void; disabled: boolean }) => (
    <div className="flex justify-end" style={{ marginTop: '24px' }}>
      <button
        onClick={onClick}
        disabled={disabled}
        style={{
          background: disabled ? 'transparent' : 'rgba(34,211,238,0.1)',
          border: `1px solid ${disabled ? 'rgba(255,255,255,0.06)' : 'rgba(34,211,238,0.35)'}`,
          color: disabled ? 'rgba(255,255,255,0.15)' : '#22d3ee',
          fontFamily: 'monospace',
          fontSize: '10px',
          fontWeight: 700,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          padding: '9px 22px',
          borderRadius: '8px',
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: 'all 0.15s',
        }}
        onMouseEnter={e => { if (!disabled) { e.currentTarget.style.background = 'rgba(34,211,238,0.18)'; e.currentTarget.style.boxShadow = '0 0 16px rgba(34,211,238,0.15)' } }}
        onMouseLeave={e => { e.currentTarget.style.background = disabled ? 'transparent' : 'rgba(34,211,238,0.1)'; e.currentTarget.style.boxShadow = 'none' }}
      >
        {saving ? savingLabel : 'Test & Save'}
      </button>
    </div>
  )

  const connectedCount = [status?.googleConfigured, status?.microsoftConfigured, status?.linkedinConfigured].filter(Boolean).length

  return (
    <div style={{ position: 'relative', minHeight: '100%', padding: '40px 48px', overflow: 'hidden' }}>

      {/* ── Background shapes ── */}
      {/* Large blurred orb top-right */}
      <div style={{
        position: 'fixed',
        top: '-120px',
        right: '-80px',
        width: '420px',
        height: '420px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(34,211,238,0.07) 0%, transparent 70%)',
        pointerEvents: 'none',
        zIndex: 0,
      }} />
      {/* Medium orb bottom-left */}
      <div style={{
        position: 'fixed',
        bottom: '60px',
        left: '80px',
        width: '300px',
        height: '300px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(56,189,248,0.05) 0%, transparent 70%)',
        pointerEvents: 'none',
        zIndex: 0,
      }} />
      {/* Faint diagonal grid */}
      <div style={{
        position: 'fixed',
        inset: 0,
        backgroundImage: 'linear-gradient(rgba(34,211,238,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.03) 1px, transparent 1px)',
        backgroundSize: '48px 48px',
        pointerEvents: 'none',
        zIndex: 0,
      }} />
      {/* Top-right corner geometric accent */}
      <div style={{
        position: 'fixed',
        top: '56px',
        right: '0',
        width: '200px',
        height: '200px',
        pointerEvents: 'none',
        zIndex: 0,
        opacity: 0.4,
      }}>
        <svg width="200" height="200" viewBox="0 0 200 200" fill="none">
          <circle cx="180" cy="20" r="80" stroke="rgba(34,211,238,0.08)" strokeWidth="1"/>
          <circle cx="180" cy="20" r="50" stroke="rgba(34,211,238,0.06)" strokeWidth="1"/>
          <circle cx="180" cy="20" r="25" stroke="rgba(34,211,238,0.1)" strokeWidth="1"/>
        </svg>
      </div>

      {/* ── Content ── */}
      <div style={{ position: 'relative', zIndex: 1, maxWidth: '640px' }}>

        {/* Page header */}
        <div style={{ marginBottom: '40px' }}>
          <div className="flex items-end justify-between">
            <div>
              <div className="flex items-center gap-3" style={{ marginBottom: '8px' }}>
                <div style={{ width: '28px', height: '1px', background: '#22d3ee', boxShadow: '0 0 8px rgba(34,211,238,0.6)' }} />
                <span style={{ fontSize: '10px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.25em', textTransform: 'uppercase', color: '#22d3ee' }}>
                  Settings
                </span>
              </div>
              <h1 style={{
                fontSize: '28px',
                fontFamily: '"Courier New", monospace',
                fontWeight: 700,
                color: 'rgba(226,232,240,0.95)',
                letterSpacing: '-0.01em',
                lineHeight: 1,
              }}>
                Integrations
              </h1>
              <p style={{ fontSize: '12px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.55)', marginTop: '8px' }}>
                Configure once — each campaign can toggle them independently.
              </p>
            </div>
            {/* Live counter */}
            <div style={{
              textAlign: 'right',
              paddingBottom: '2px',
            }}>
              <span style={{ fontSize: '36px', fontFamily: 'monospace', fontWeight: 700, color: connectedCount > 0 ? '#22d3ee' : 'rgba(255,255,255,0.1)', lineHeight: 1 }}>
                {connectedCount}
              </span>
              <span style={{ fontSize: '11px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.4)', display: 'block', marginTop: '2px' }}>
                / 3 connected
              </span>
            </div>
          </div>

          {/* Divider */}
          <div style={{ height: '1px', background: 'linear-gradient(90deg, rgba(34,211,238,0.2), transparent)', marginTop: '20px' }} />
        </div>

        {/* Notifications */}
        {(error || hookError) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.15)', borderRadius: '10px', padding: '12px 16px', marginBottom: '20px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <p style={{ fontSize: '11px', fontFamily: 'monospace', color: '#f87171' }}>{error || hookError}</p>
          </div>
        )}
        {success && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(52,211,153,0.06)', border: '1px solid rgba(52,211,153,0.15)', borderRadius: '10px', padding: '12px 16px', marginBottom: '20px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            <p style={{ fontSize: '11px', fontFamily: 'monospace', color: '#34d399' }}>{success}</p>
          </div>
        )}

        {/* Cards */}
        <div className="flex flex-col" style={{ gap: '12px' }}>

          {/* Google */}
          <IntegrationCard
            icon={
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
            }
            title="Google Calendar & Gmail"
            subtitle="OAuth 2.0 — sign in with your Google account"
            tag="OAuth"
            configured={status?.googleConfigured ?? false}
            open={googleOpen}
            onToggle={() => setGoogleOpen(o => !o)}
            accentColor="#4285F4"
          >
            <div className="flex flex-col" style={{ gap: '16px' }}>
              {setup && !setup.google_ready && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: '10px', padding: '12px 16px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" strokeWidth="2" strokeLinecap="round" style={{ marginTop: '1px', flexShrink: 0 }}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  <p style={{ fontSize: '11px', fontFamily: 'monospace', color: '#fbbf24', lineHeight: 1.6 }}>
                    Add <strong>GOOGLE_CLIENT_ID</strong> and <strong>GOOGLE_CLIENT_SECRET</strong> to your .env file to enable Google sign-in.
                  </p>
                </div>
              )}

              {status?.googleConfigured ? (
                <div className="flex items-center justify-between" style={{ marginTop: '4px' }}>
                  <span style={{ fontSize: '12px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.7)' }}>Your Google account is linked.</span>
                  <button
                    onClick={disconnectGoogle}
                    style={{
                      background: 'transparent',
                      border: '1px solid rgba(248,113,113,0.25)',
                      color: '#f87171',
                      fontFamily: 'monospace',
                      fontSize: '10px',
                      fontWeight: 700,
                      letterSpacing: '0.12em',
                      textTransform: 'uppercase',
                      padding: '6px 14px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(248,113,113,0.08)'; e.currentTarget.style.color = '#fca5a5' }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#f87171' }}
                  >
                    Disconnect
                  </button>
                </div>
              ) : (
                <div className="flex justify-end" style={{ marginTop: '4px' }}>
                  <button
                    onClick={() => { connectGoogle(); startPolling() }}
                    disabled={loading || !setup?.google_ready}
                    style={{
                      background: loading || !setup?.google_ready ? 'transparent' : 'rgba(66,133,244,0.1)',
                      border: `1px solid ${loading || !setup?.google_ready ? 'rgba(255,255,255,0.06)' : 'rgba(66,133,244,0.35)'}`,
                      color: loading || !setup?.google_ready ? 'rgba(255,255,255,0.15)' : '#4285F4',
                      fontFamily: 'monospace',
                      fontSize: '10px',
                      fontWeight: 700,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase',
                      padding: '9px 22px',
                      borderRadius: '8px',
                      cursor: loading || !setup?.google_ready ? 'not-allowed' : 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => { if (!loading && setup?.google_ready) { e.currentTarget.style.background = 'rgba(66,133,244,0.18)'; e.currentTarget.style.boxShadow = '0 0 16px rgba(66,133,244,0.15)' } }}
                    onMouseLeave={e => { e.currentTarget.style.background = loading || !setup?.google_ready ? 'transparent' : 'rgba(66,133,244,0.1)'; e.currentTarget.style.boxShadow = 'none' }}
                  >
                    {loading ? 'Opening browser…' : 'Connect Google'}
                  </button>
                </div>
              )}
            </div>
          </IntegrationCard>

          {/* Microsoft */}
          <IntegrationCard
            icon={
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
                <rect x="1" y="1" width="10" height="10" fill="#F25022"/>
                <rect x="13" y="1" width="10" height="10" fill="#7FBA00"/>
                <rect x="1" y="13" width="10" height="10" fill="#00A4EF"/>
                <rect x="13" y="13" width="10" height="10" fill="#FFB900"/>
              </svg>
            }
            title="Microsoft Calendar & Outlook"
            subtitle="OAuth 2.0 — sign in with your Microsoft account"
            tag="OAuth"
            configured={status?.microsoftConfigured ?? false}
            open={microsoftOpen}
            onToggle={() => setMicrosoftOpen(o => !o)}
            accentColor="#00A4EF"
          >
            <div className="flex flex-col" style={{ gap: '16px' }}>
              {setup && !setup.microsoft_ready && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: '10px', padding: '12px 16px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" strokeWidth="2" strokeLinecap="round" style={{ marginTop: '1px', flexShrink: 0 }}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  <p style={{ fontSize: '11px', fontFamily: 'monospace', color: '#fbbf24', lineHeight: 1.6 }}>
                    Add <strong>MICROSOFT_CLIENT_ID</strong> and <strong>MICROSOFT_CLIENT_SECRET</strong> to your .env file to enable Microsoft sign-in.
                  </p>
                </div>
              )}

              {status?.microsoftConfigured ? (
                <div className="flex items-center justify-between" style={{ marginTop: '4px' }}>
                  <span style={{ fontSize: '12px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.7)' }}>Your Microsoft account is linked.</span>
                  <button
                    onClick={disconnectMicrosoft}
                    style={{
                      background: 'transparent',
                      border: '1px solid rgba(248,113,113,0.25)',
                      color: '#f87171',
                      fontFamily: 'monospace',
                      fontSize: '10px',
                      fontWeight: 700,
                      letterSpacing: '0.12em',
                      textTransform: 'uppercase',
                      padding: '6px 14px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(248,113,113,0.08)'; e.currentTarget.style.color = '#fca5a5' }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#f87171' }}
                  >
                    Disconnect
                  </button>
                </div>
              ) : (
                <div className="flex justify-end" style={{ marginTop: '4px' }}>
                  <button
                    onClick={() => { connectMicrosoft(); startPolling() }}
                    disabled={loading || !setup?.microsoft_ready}
                    style={{
                      background: loading || !setup?.microsoft_ready ? 'transparent' : 'rgba(0,164,239,0.1)',
                      border: `1px solid ${loading || !setup?.microsoft_ready ? 'rgba(255,255,255,0.06)' : 'rgba(0,164,239,0.35)'}`,
                      color: loading || !setup?.microsoft_ready ? 'rgba(255,255,255,0.15)' : '#00A4EF',
                      fontFamily: 'monospace',
                      fontSize: '10px',
                      fontWeight: 700,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase',
                      padding: '9px 22px',
                      borderRadius: '8px',
                      cursor: loading || !setup?.microsoft_ready ? 'not-allowed' : 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => { if (!loading && setup?.microsoft_ready) { e.currentTarget.style.background = 'rgba(0,164,239,0.18)'; e.currentTarget.style.boxShadow = '0 0 16px rgba(0,164,239,0.15)' } }}
                    onMouseLeave={e => { e.currentTarget.style.background = loading || !setup?.microsoft_ready ? 'transparent' : 'rgba(0,164,239,0.1)'; e.currentTarget.style.boxShadow = 'none' }}
                  >
                    {loading ? 'Opening browser…' : 'Connect Microsoft'}
                  </button>
                </div>
              )}
            </div>
          </IntegrationCard>

          {/* LinkedIn */}
          <IntegrationCard
            icon={<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>}
            title="LinkedIn Scraping"
            subtitle="Auto-discover jobs + enable hiring manager outreach"
            tag="OAuth"
            configured={status?.linkedinConfigured ?? false}
            open={linkedinOpen}
            onToggle={() => setLinkedInOpen(o => !o)}
            accentColor="#38bdf8"
          >
            <div className="flex flex-col" style={{ gap: '20px' }}>
              {/* Mode toggle */}
              <div className="flex" style={{ gap: '2px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '3px', alignSelf: 'flex-start' }}>
                {(['cookie', 'password'] as const).map(m => (
                  <button key={m} onClick={() => setLinkedInMode(m)} style={{
                    background: linkedinMode === m ? 'rgba(56,189,248,0.12)' : 'transparent',
                    border: `1px solid ${linkedinMode === m ? 'rgba(56,189,248,0.25)' : 'transparent'}`,
                    color: linkedinMode === m ? '#38bdf8' : 'rgba(100,116,139,0.5)',
                    fontFamily: 'monospace',
                    fontSize: '10px', fontWeight: 700,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    padding: '6px 16px', borderRadius: '8px', cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}>
                    {m === 'cookie' ? 'Session Cookie' : 'Email & Password'}
                  </button>
                ))}
              </div>

              {linkedinMode === 'cookie' ? (
                <>
                  <Field label="li_at Cookie Value" value={linkedinForm.session_cookie} onChange={v => setLinkedInForm(f => ({ ...f, session_cookie: v }))} placeholder="AQE…" type="password" />
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                    {[
                      { step: '01', text: 'Open LinkedIn in Chrome & log in' },
                      { step: '02', text: 'F12 → Application → Cookies → linkedin.com' },
                      { step: '03', text: 'Find li_at → copy the Value column' },
                    ].map(({ step, text }) => (
                      <div key={step} style={{ background: 'rgba(56,189,248,0.04)', border: '1px solid rgba(56,189,248,0.1)', borderRadius: '8px', padding: '12px' }}>
                        <span style={{ fontSize: '18px', fontFamily: 'monospace', fontWeight: 700, color: 'rgba(56,189,248,0.15)', display: 'block', lineHeight: 1, marginBottom: '6px' }}>{step}</span>
                        <p style={{ fontSize: '10px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.55)', lineHeight: 1.6 }}>{text}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="grid grid-cols-2" style={{ gap: '24px' }}>
                  <Field label="LinkedIn Email" value={linkedinForm.email} onChange={v => setLinkedInForm(f => ({ ...f, email: v }))} placeholder="you@email.com" />
                  <Field label="Password" value={linkedinForm.password} onChange={v => setLinkedInForm(f => ({ ...f, password: v }))} placeholder="••••••••" type="password" />
                </div>
              )}
              <SaveBtn onClick={saveLinkedIn} disabled={saving || (linkedinMode === 'cookie' ? !linkedinForm.session_cookie : !linkedinForm.email || !linkedinForm.password)} />
            </div>
          </IntegrationCard>

        </div>
      </div>
    </div>
  )
}
