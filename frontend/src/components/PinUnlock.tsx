import { useState, useEffect, useRef } from 'react'
import { useAuthStore } from '../store/authStore'

const PIN_LENGTH = 6

interface Props {
  onUnlocked: () => void
  onForgot: () => void
}

export default function PinUnlock({ onUnlocked, onForgot }: Props) {
  const [pin,         setPin]         = useState('')
  const [error,       setError]       = useState<string | null>(null)
  const [loading,     setLoading]     = useState(false)
  const [locked,      setLocked]      = useState(false)
  const [shake,       setShake]       = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const { setAuth, userId, name, languagePref } = useAuthStore.getState()
  const electronAPI = (window as any).electronAPI

  useEffect(() => { inputRef.current?.focus() }, [])

  const triggerShake = () => {
    setShake(true)
    setTimeout(() => setShake(false), 400)
  }

  const submit = async (pinValue: string) => {
    if (loading || locked) return
    setLoading(true)
    setError(null)

    const result = await electronAPI?.checkPin?.(pinValue)

    if (result?.ok) {
      // PIN correct — exchange stored refresh token for a fresh access token
      const tokens = await electronAPI?.refreshToken?.()
      if (tokens?.accessToken) {
        setAuth(
          tokens.accessToken,
          tokens.refreshToken || '',
          userId ?? '',
          name ?? '',
          languagePref ?? 'en',
        )
        onUnlocked()
      } else {
        // Stored token expired — fall back to full login
        setError('Session expired. Please log in again.')
        setTimeout(onForgot, 2000)
      }
    } else {
      setPin('')
      triggerShake()
      if (result?.reason === 'locked' || (result?.attemptsLeft ?? 1) <= 0) {
        setLocked(true)
        setError('Too many wrong attempts — please log in again.')
        setTimeout(onForgot, 3000)
      } else {
        const left = result?.attemptsLeft
        setError(left === 1 ? 'Wrong PIN — 1 attempt left' : `Wrong PIN${left != null ? ` — ${left} attempts left` : ''}`)
      }
    }
    setLoading(false)
  }

  const handleChange = (v: string) => {
    if (locked || loading) return
    const digits = v.replace(/\D/g, '').slice(0, PIN_LENGTH)
    setPin(digits)
    if (error) setError(null)
    if (digits.length === PIN_LENGTH) submit(digits)
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#020810',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', fontFamily: 'monospace',
    }}>
      <style>{`
        @keyframes pin-shake {
          0%,100%{transform:translateX(0)} 20%{transform:translateX(-6px)}
          40%{transform:translateX(6px)} 60%{transform:translateX(-4px)} 80%{transform:translateX(4px)}
        }
        @keyframes pin-fade { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

      {/* Glow backdrop */}
      <div style={{
        position: 'absolute', width: '300px', height: '300px', borderRadius: '50%',
        background: 'radial-gradient(circle,rgba(34,211,238,0.06) 0%,transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div style={{ animation: 'pin-fade 0.5s both', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {/* Lock icon */}
        <div style={{ marginBottom: '28px', opacity: locked ? 0.3 : 0.7, transition: 'opacity 0.3s' }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
        </div>

        <div style={{ fontSize: '9px', letterSpacing: '0.32em', color: 'rgba(34,211,238,0.45)', textTransform: 'uppercase', marginBottom: '6px' }}>
          DEVCORE
        </div>
        <div style={{ fontSize: '12px', color: 'rgba(226,232,240,0.4)', marginBottom: '40px', letterSpacing: '0.05em' }}>
          Enter PIN to continue
        </div>

        {/* PIN dots */}
        <div style={{
          display: 'flex', gap: '14px', marginBottom: '28px',
          animation: shake ? 'pin-shake 0.4s ease' : 'none',
        }}>
          {Array.from({ length: PIN_LENGTH }).map((_, i) => {
            const filled = i < pin.length
            return (
              <div key={i} style={{
                width: '13px', height: '13px', borderRadius: '50%',
                background: filled ? '#22d3ee' : 'transparent',
                border: `1.5px solid ${filled ? '#22d3ee' : 'rgba(34,211,238,0.25)'}`,
                boxShadow: filled ? '0 0 10px rgba(34,211,238,0.5)' : 'none',
                transition: 'all 0.12s ease',
              }} />
            )
          })}
        </div>

        {/* Hidden input — keyboard entry */}
        <input
          ref={inputRef}
          type="password"
          inputMode="numeric"
          value={pin}
          onChange={e => handleChange(e.target.value)}
          onBlur={() => setTimeout(() => inputRef.current?.focus(), 50)}
          style={{ position: 'absolute', opacity: 0, width: 0, height: 0, pointerEvents: 'none' }}
          disabled={locked || loading}
          autoComplete="off"
        />

        {/* Error / status */}
        <div style={{ height: '18px', marginBottom: '32px', textAlign: 'center' }}>
          {error && (
            <span style={{ fontSize: '11px', color: '#f87171', letterSpacing: '0.04em' }}>
              {error}
            </span>
          )}
          {loading && !error && (
            <span style={{ fontSize: '11px', color: 'rgba(34,211,238,0.5)', letterSpacing: '0.1em' }}>
              verifying…
            </span>
          )}
        </div>

        {/* Forgot PIN */}
        <button
          onClick={onForgot}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'rgba(100,116,139,0.4)', fontSize: '11px',
            letterSpacing: '0.08em', padding: '8px 12px',
            transition: 'color 0.2s',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.7)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.4)')}
        >
          Forgot PIN? Log in with password →
        </button>
      </div>
    </div>
  )
}
