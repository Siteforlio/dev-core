import { useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { SaveCredsModal } from '../components/SaveCredsModal'
import { API_BASE } from '../lib/apiBase'

const eAPI = () => (window as any).electronAPI

const SAVE_CREDS_SETTING = 'devcore_save_creds_enabled'

function getSaveCredsSetting(): boolean {
  return localStorage.getItem(SAVE_CREDS_SETTING) !== '0'
}

/* Floating particle dot */
function Particle({ x, delay, duration }: { x: number; delay: number; duration: number }) {
  return (
    <div style={{
      position: 'absolute',
      bottom: 0,
      left: `${x}%`,
      width: '2px',
      height: '2px',
      borderRadius: '50%',
      background: '#22d3ee',
      animation: `float-up ${duration}s ${delay}s infinite ease-in`,
      pointerEvents: 'none',
    }} />
  )
}

export default function Login({ onGoToRegister, onLoggedIn }: { onGoToRegister: () => void; onLoggedIn?: () => void }) {
  const [email, setEmail]             = useState('')
  const [password, setPassword]       = useState('')
  const [showPass, setShowPass]       = useState(false)
  const [error, setError]             = useState('')
  const [loading, setLoading]         = useState(false)
  const [focusedField, setFocused]    = useState<string | null>(null)
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [savedCreds, setSavedCreds]   = useState<{ email: string } | null>(null)
  const [quickLoading, setQuickLoading] = useState(false)
  const setAuth = useAuthStore((s) => s.setAuth)

  const isValid = email.includes('@') && password.length >= 6

  // Load saved creds on mount (Electron only, setting must be enabled)
  useEffect(() => {
    if (!eAPI()?.loadCreds || !getSaveCredsSetting()) return
    eAPI().loadCreds().then((creds: { email: string } | null) => {
      if (creds?.email) setSavedCreds({ email: creds.email })
    }).catch(() => {})
  }, [])

  const _doAuth = async (emailVal: string, passwordVal: string): Promise<boolean> => {
    const res = await fetch(`${API_BASE()}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: emailVal, password: passwordVal }),
    })
    const body = await res.json()
    if (!res.ok) { setError(body.error?.message ?? 'Login failed'); return false }
    const { access_token, refresh_token, user_id, name, language_pref } = body.data
    setAuth(access_token, refresh_token, user_id, name, language_pref)
    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const ok = await _doAuth(email, password)
      if (!ok) return
      // Offer to save creds if Electron and setting enabled
      if (eAPI()?.saveCreds && getSaveCredsSetting()) {
        setShowSaveModal(true)
      } else {
        onLoggedIn?.()
      }
    } catch {
      setError('Could not reach the server.')
    } finally {
      setLoading(false)
    }
  }

  const handleQuickLogin = async () => {
    if (!eAPI()?.loadCreds) return
    setQuickLoading(true)
    setError('')
    try {
      const creds = await eAPI().loadCreds()
      if (!creds) { setSavedCreds(null); return }
      const ok = await _doAuth(creds.email, creds.password)
      if (ok) onLoggedIn?.()
    } catch {
      setError('Could not reach the server.')
    } finally {
      setQuickLoading(false)
    }
  }

  const handleSaveYes = async () => {
    await eAPI()?.saveCreds?.(email, password)
    setShowSaveModal(false)
    onLoggedIn?.()
  }

  const handleSaveNo = () => {
    setShowSaveModal(false)
    onLoggedIn?.()
  }

  const particles = [
    { x: 8,  delay: 0,   duration: 8  },
    { x: 22, delay: 2.5, duration: 11 },
    { x: 38, delay: 1,   duration: 9  },
    { x: 55, delay: 4,   duration: 7  },
    { x: 70, delay: 0.5, duration: 12 },
    { x: 84, delay: 3,   duration: 10 },
    { x: 93, delay: 1.8, duration: 8  },
  ]

  return (
    <>
      {showSaveModal && (
        <SaveCredsModal email={email} onYes={handleSaveYes} onNo={handleSaveNo} />
      )}

      <div style={{ display: 'flex', minHeight: '100vh', background: '#020810', overflow: 'hidden' }}>

        {/* ─── Left brand panel ─── */}
        <div style={{
          width: '52%',
          position: 'relative',
          background: 'linear-gradient(160deg, #020c1a 0%, #020810 60%, #010610 100%)',
          borderRight: '1px solid rgba(34,211,238,0.08)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          flexShrink: 0,
        }}>

          {/* Grid overlay */}
          <div style={{
            position: 'absolute', inset: 0,
            backgroundImage: 'linear-gradient(rgba(34,211,238,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.025) 1px, transparent 1px)',
            backgroundSize: '52px 52px',
            pointerEvents: 'none',
          }} />

          {/* Scanline sweep */}
          <div style={{
            position: 'absolute', left: 0, right: 0,
            height: '2px',
            background: 'linear-gradient(90deg, transparent 0%, rgba(34,211,238,0.3) 30%, rgba(34,211,238,0.7) 50%, rgba(34,211,238,0.3) 70%, transparent 100%)',
            boxShadow: '0 0 20px rgba(34,211,238,0.4)',
            animation: 'scanline 6s 1s infinite linear',
            pointerEvents: 'none',
            zIndex: 1,
          }} />

          {/* Big glow behind logo */}
          <div style={{
            position: 'absolute',
            width: '360px', height: '360px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(34,211,238,0.06) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />

          {/* Corner lines top-left */}
          <svg style={{ position: 'absolute', top: 24, left: 24 }} width="48" height="48" viewBox="0 0 48 48" fill="none">
            <path d="M0 48 L0 0 L48 0" stroke="rgba(34,211,238,0.3)" strokeWidth="1.5"/>
          </svg>
          {/* Corner lines bottom-right */}
          <svg style={{ position: 'absolute', bottom: 24, right: 24 }} width="48" height="48" viewBox="0 0 48 48" fill="none">
            <path d="M48 0 L48 48 L0 48" stroke="rgba(34,211,238,0.3)" strokeWidth="1.5"/>
          </svg>

          {/* Particles */}
          {particles.map((p, i) => <Particle key={i} {...p} />)}

          {/* Content */}
          <div style={{ position: 'relative', zIndex: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '32px' }}>
            {/* Logo */}
            <div style={{ position: 'relative' }}>
              <div style={{
                position: 'absolute', inset: '-20px',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(34,211,238,0.12) 0%, transparent 70%)',
                animation: 'pulse-dot 3s ease-in-out infinite',
              }} />
              <img src="./devcore.png" width="88" height="88" alt="DevCore" style={{ objectFit: 'contain', display: 'block', filter: 'drop-shadow(0 0 20px rgba(34,211,238,0.5))' }} />
            </div>

            {/* Name */}
            <div style={{ textAlign: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'center', marginBottom: '6px' }}>
                <div style={{ height: '1px', width: '32px', background: 'rgba(34,211,238,0.3)' }} />
                <span style={{ fontSize: '10px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.3em', color: 'rgba(34,211,238,0.6)', textTransform: 'uppercase' }}>
                  v1.0 · secure
                </span>
                <div style={{ height: '1px', width: '32px', background: 'rgba(34,211,238,0.3)' }} />
              </div>
              <h1 style={{
                fontFamily: '"Orbitron", monospace',
                fontWeight: 900,
                fontSize: '38px',
                letterSpacing: '0.12em',
                color: 'rgba(226,232,240,0.97)',
                lineHeight: 1,
                textShadow: '0 0 40px rgba(34,211,238,0.2)',
                animation: 'flicker 8s 3s infinite',
              }}>
                DEVCORE
              </h1>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center', marginTop: '10px' }}>
                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: 'rgba(100,116,139,0.6)', letterSpacing: '0.08em' }}>
                  interview intelligence platform
                </span>
                <span style={{ display: 'inline-block', width: '7px', height: '13px', background: '#22d3ee', animation: 'blink 1.1s step-end infinite', marginLeft: '2px', opacity: 0.9 }} />
              </div>
            </div>

            {/* System status readout */}
            <div style={{
              background: 'rgba(34,211,238,0.03)',
              border: '1px solid rgba(34,211,238,0.1)',
              borderRadius: '10px',
              padding: '16px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              width: '260px',
            }}>
              {[
                { label: 'INTERVIEW ENGINE', status: 'ONLINE', color: '#34d399' },
                { label: 'JOB SCANNER',      status: 'ACTIVE',  color: '#34d399' },
                { label: 'AI CORE',           status: 'READY',   color: '#22d3ee' },
                { label: 'OVERLAY SYSTEM',    status: 'STANDBY', color: '#fbbf24' },
              ].map(({ label, status, color }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'monospace', fontSize: '9px', letterSpacing: '0.14em', color: 'rgba(100,116,139,0.5)' }}>{label}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: color, animation: 'pulse-dot 2.5s ease-in-out infinite', boxShadow: `0 0 6px ${color}` }} />
                    <span style={{ fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.14em', color }}>{status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ─── Right form panel ─── */}
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#030d1a',
          position: 'relative',
          overflow: 'hidden',
        }}>
          {/* Faint radial behind form */}
          <div style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            width: '500px', height: '500px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(34,211,238,0.04) 0%, transparent 65%)',
            pointerEvents: 'none',
          }} />

          <form
            onSubmit={handleSubmit}
            style={{
              position: 'relative',
              width: '340px',
              animation: 'auth-slide-in 0.5s ease both',
            }}
          >
            {/* Header */}
            <div style={{ marginBottom: '40px' }}>
              <p style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.25em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.5)', marginBottom: '8px' }}>
                — Access Terminal
              </p>
              <h2 style={{ fontFamily: '"Orbitron", monospace', fontWeight: 700, fontSize: '22px', letterSpacing: '0.08em', color: 'rgba(226,232,240,0.95)', lineHeight: 1 }}>
                Sign In
              </h2>
              <p style={{ fontFamily: 'monospace', fontSize: '11px', color: 'rgba(100,116,139,0.5)', marginTop: '8px' }}>
                Enter your credentials to access the platform.
              </p>
            </div>

            {/* Quick login button (saved creds) */}
            {savedCreds && (
              <button
                type="button"
                onClick={handleQuickLogin}
                disabled={quickLoading}
                style={{
                  width: '100%',
                  padding: '13px',
                  marginBottom: '24px',
                  background: 'rgba(52,211,153,0.07)',
                  border: '1px solid rgba(52,211,153,0.25)',
                  borderRadius: '10px',
                  color: '#34d399',
                  fontFamily: 'monospace',
                  fontSize: '11px',
                  fontWeight: 600,
                  letterSpacing: '0.12em',
                  cursor: quickLoading ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '9px',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (!quickLoading) e.currentTarget.style.background = 'rgba(52,211,153,0.13)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(52,211,153,0.07)' }}
              >
                {quickLoading
                  ? <><span style={{ width: '13px', height: '13px', border: '2px solid rgba(52,211,153,0.4)', borderTopColor: '#34d399', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} /> Signing in…</>
                  : <>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                    Continue as {savedCreds.email}
                  </>
                }
              </button>
            )}

            {/* Error */}
            {error && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: '8px', padding: '10px 14px', marginBottom: '24px' }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: '#f87171' }}>{error}</span>
              </div>
            )}

            {/* Fields */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', marginBottom: '36px' }}>
              {/* Email */}
              <div style={{ position: 'relative' }}>
                <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: focusedField === 'email' ? '#22d3ee' : 'rgba(100,116,139,0.45)', marginBottom: '8px', transition: 'color 0.15s' }}>
                  Email Address
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  onFocus={() => setFocused('email')}
                  onBlur={() => setFocused(null)}
                  disabled={loading}
                  placeholder="you@domain.com"
                  style={{ background: 'transparent', border: 'none', borderBottom: `1px solid ${focusedField === 'email' ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.08)'}`, color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace', fontSize: '13px', padding: '6px 0 10px', outline: 'none', width: '100%', transition: 'border-color 0.15s' }}
                />
                <div style={{ position: 'absolute', bottom: 0, left: 0, height: '1px', width: focusedField === 'email' ? '100%' : '0%', background: 'linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2))', boxShadow: '0 0 8px rgba(34,211,238,0.5)', transition: 'width 0.3s ease' }} />
              </div>

              {/* Password */}
              <div style={{ position: 'relative' }}>
                <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: focusedField === 'password' ? '#22d3ee' : 'rgba(100,116,139,0.45)', marginBottom: '8px', transition: 'color 0.15s' }}>
                  Password
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPass ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    onFocus={() => setFocused('password')}
                    onBlur={() => setFocused(null)}
                    disabled={loading}
                    placeholder="••••••••"
                    style={{ background: 'transparent', border: 'none', borderBottom: `1px solid ${focusedField === 'password' ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.08)'}`, color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace', fontSize: '13px', padding: '6px 28px 10px 0', outline: 'none', width: '100%', transition: 'border-color 0.15s' }}
                  />
                  <button type="button" onClick={() => setShowPass(v => !v)} style={{ position: 'absolute', right: 0, bottom: '8px', background: 'none', border: 'none', color: 'rgba(100,116,139,0.4)', cursor: 'pointer', padding: 0 }}>
                    {showPass
                      ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                      : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    }
                  </button>
                </div>
                <div style={{ position: 'absolute', bottom: 0, left: 0, height: '1px', width: focusedField === 'password' ? '100%' : '0%', background: 'linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2))', boxShadow: '0 0 8px rgba(34,211,238,0.5)', transition: 'width 0.3s ease' }} />
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !isValid}
              style={{
                width: '100%',
                padding: '13px',
                background: isValid && !loading ? 'rgba(34,211,238,0.1)' : 'transparent',
                border: `1px solid ${isValid && !loading ? 'rgba(34,211,238,0.4)' : 'rgba(255,255,255,0.07)'}`,
                borderRadius: '10px',
                color: isValid && !loading ? '#22d3ee' : 'rgba(255,255,255,0.18)',
                fontFamily: '"Orbitron", monospace',
                fontWeight: 700,
                fontSize: '11px',
                letterSpacing: '0.2em',
                textTransform: 'uppercase',
                cursor: isValid && !loading ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px',
                transition: 'all 0.2s',
                boxShadow: isValid && !loading ? '0 0 20px rgba(34,211,238,0.08)' : 'none',
              }}
              onMouseEnter={e => { if (isValid && !loading) { e.currentTarget.style.background = 'rgba(34,211,238,0.17)'; e.currentTarget.style.boxShadow = '0 0 28px rgba(34,211,238,0.18)' } }}
              onMouseLeave={e => { e.currentTarget.style.background = isValid && !loading ? 'rgba(34,211,238,0.1)' : 'transparent'; e.currentTarget.style.boxShadow = isValid && !loading ? '0 0 20px rgba(34,211,238,0.08)' : 'none' }}
            >
              {loading
                ? <><span style={{ width: '14px', height: '14px', border: '2px solid rgba(34,211,238,0.4)', borderTopColor: '#22d3ee', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} /> Authenticating…</>
                : <>Authenticate <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></>
              }
            </button>

            {/* Divider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '24px 0' }}>
              <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.05)' }} />
              <span style={{ fontFamily: 'monospace', fontSize: '9px', letterSpacing: '0.15em', color: 'rgba(100,116,139,0.3)', textTransform: 'uppercase' }}>No account?</span>
              <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.05)' }} />
            </div>

            <button
              type="button"
              onClick={onGoToRegister}
              style={{ width: '100%', padding: '11px', background: 'transparent', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '10px', color: 'rgba(148,163,184,0.5)', fontFamily: 'monospace', fontSize: '11px', fontWeight: 600, letterSpacing: '0.15em', textTransform: 'uppercase', cursor: 'pointer', transition: 'all 0.15s' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.14)'; e.currentTarget.style.color = 'rgba(226,232,240,0.7)' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'rgba(148,163,184,0.5)' }}
            >
              Create Account
            </button>
          </form>
        </div>

        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </>
  )
}
