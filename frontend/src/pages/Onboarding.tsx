import { useState } from 'react'
import { useAuthStore } from '../store/authStore'

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'sw', label: 'Swahili' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'pt', label: 'Portuguese' },
]

function UnderlineField({
  label, value, onChange, placeholder, type = 'text', disabled = false,
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; disabled?: boolean
}) {
  const [focused, setFocused] = useState(false)
  return (
    <div style={{ position: 'relative', paddingBottom: '2px' }}>
      <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: focused ? '#22d3ee' : 'rgba(100,116,139,0.45)', marginBottom: '8px', transition: 'color 0.15s' }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        disabled={disabled}
        placeholder={placeholder}
        style={{ background: 'transparent', border: 'none', borderBottom: `1px solid ${focused ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.08)'}`, color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace', fontSize: '13px', padding: '6px 0 10px', outline: 'none', width: '100%', transition: 'border-color 0.15s' }}
      />
      <div style={{ position: 'absolute', bottom: 0, left: 0, height: '1px', width: focused ? '100%' : '0%', background: 'linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2))', boxShadow: '0 0 8px rgba(34,211,238,0.5)', transition: 'width 0.3s ease' }} />
    </div>
  )
}

export default function Onboarding({ onGoToLogin, onRegistered }: { onGoToLogin: () => void; onRegistered?: () => void }) {
  const [name, setName]       = useState('')
  const [email, setEmail]     = useState('')
  const [password, setPassword] = useState('')
  const [lang, setLang]       = useState('en')
  const [consent, setConsent] = useState(false)
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)
  const [langOpen, setLangOpen] = useState(false)
  const setAuth = useAuthStore((s) => s.setAuth)

  const isValid = name.trim().length >= 2 && email.includes('@') && password.length >= 6 && consent

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!consent) { setError('You must agree to data usage to continue.'); return }
    setError('')
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, language_pref: lang, consent_given: consent }),
      })
      const body = await res.json()
      if (!res.ok) { setError(body.error?.message ?? 'Registration failed'); return }
      const { access_token, refresh_token, user_id, name: userName, language_pref } = body.data
      setAuth(access_token, refresh_token, user_id, userName, language_pref)
      onRegistered?.()
    } catch {
      setError('Could not reach the server.')
    } finally {
      setLoading(false)
    }
  }

  const selectedLang = LANGUAGES.find(l => l.value === lang)

  return (
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
        {/* Grid */}
        <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(34,211,238,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.025) 1px, transparent 1px)', backgroundSize: '52px 52px', pointerEvents: 'none' }} />

        {/* Scanline */}
        <div style={{ position: 'absolute', left: 0, right: 0, height: '2px', background: 'linear-gradient(90deg, transparent 0%, rgba(34,211,238,0.3) 30%, rgba(34,211,238,0.7) 50%, rgba(34,211,238,0.3) 70%, transparent 100%)', boxShadow: '0 0 20px rgba(34,211,238,0.4)', animation: 'scanline 6s 1s infinite linear', pointerEvents: 'none', zIndex: 1 }} />

        {/* Glow orb */}
        <div style={{ position: 'absolute', width: '360px', height: '360px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(34,211,238,0.06) 0%, transparent 70%)', pointerEvents: 'none' }} />

        {/* Corner accents */}
        <svg style={{ position: 'absolute', top: 24, left: 24 }} width="48" height="48" viewBox="0 0 48 48" fill="none">
          <path d="M0 48 L0 0 L48 0" stroke="rgba(34,211,238,0.3)" strokeWidth="1.5"/>
        </svg>
        <svg style={{ position: 'absolute', bottom: 24, right: 24 }} width="48" height="48" viewBox="0 0 48 48" fill="none">
          <path d="M48 0 L48 48 L0 48" stroke="rgba(34,211,238,0.3)" strokeWidth="1.5"/>
        </svg>

        {/* Content */}
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '28px', padding: '0 40px', textAlign: 'center' }}>
          {/* Logo */}
          <div style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', inset: '-20px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(34,211,238,0.12) 0%, transparent 70%)', animation: 'pulse-dot 3s ease-in-out infinite' }} />
            <img src="/devcore.png" width="80" height="80" alt="DevCore" style={{ objectFit: 'contain', display: 'block', filter: 'drop-shadow(0 0 20px rgba(34,211,238,0.5))' }} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'center', marginBottom: '6px' }}>
              <div style={{ height: '1px', width: '28px', background: 'rgba(34,211,238,0.3)' }} />
              <span style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.3em', color: 'rgba(34,211,238,0.6)', textTransform: 'uppercase' }}>new recruit</span>
              <div style={{ height: '1px', width: '28px', background: 'rgba(34,211,238,0.3)' }} />
            </div>
            <h1 style={{ fontFamily: '"Orbitron", monospace', fontWeight: 900, fontSize: '34px', letterSpacing: '0.12em', color: 'rgba(226,232,240,0.97)', lineHeight: 1, textShadow: '0 0 40px rgba(34,211,238,0.2)', animation: 'flicker 8s 3s infinite' }}>
              DEVCORE
            </h1>
            <p style={{ fontFamily: 'monospace', fontSize: '11px', color: 'rgba(100,116,139,0.5)', marginTop: '8px', letterSpacing: '0.06em' }}>
              interview intelligence platform
            </p>
          </div>

          {/* Feature list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%', maxWidth: '280px' }}>
            {[
              { icon: '◈', text: 'Real-time interview coaching' },
              { icon: '◈', text: 'AI job application scanner' },
              { icon: '◈', text: 'Campaign-based job hunting' },
              { icon: '◈', text: 'Screen overlay assistant' },
            ].map(({ icon, text }) => (
              <div key={text} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ color: '#22d3ee', fontSize: '12px', flexShrink: 0 }}>{icon}</span>
                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: 'rgba(148,163,184,0.5)', textAlign: 'left', letterSpacing: '0.04em' }}>{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ─── Right form panel ─── */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#030d1a', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '500px', height: '500px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(34,211,238,0.04) 0%, transparent 65%)', pointerEvents: 'none' }} />

        <form
          onSubmit={handleSubmit}
          style={{ position: 'relative', width: '340px', animation: 'auth-slide-in 0.5s ease both' }}
        >
          {/* Back + header */}
          <div style={{ marginBottom: '36px' }}>
            <button
              type="button"
              onClick={onGoToLogin}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', color: 'rgba(100,116,139,0.45)', fontFamily: 'monospace', fontSize: '10px', letterSpacing: '0.15em', textTransform: 'uppercase', cursor: 'pointer', padding: 0, marginBottom: '20px', transition: 'color 0.15s' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#22d3ee')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.45)')}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="15 18 9 12 15 6"/></svg>
              Back to sign in
            </button>
            <p style={{ fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.25em', textTransform: 'uppercase', color: 'rgba(34,211,238,0.5)', marginBottom: '8px' }}>
              — Initialize Profile
            </p>
            <h2 style={{ fontFamily: '"Orbitron", monospace', fontWeight: 700, fontSize: '22px', letterSpacing: '0.08em', color: 'rgba(226,232,240,0.95)', lineHeight: 1 }}>
              Create Account
            </h2>
            <p style={{ fontFamily: 'monospace', fontSize: '11px', color: 'rgba(100,116,139,0.5)', marginTop: '8px' }}>
              Set up your access credentials below.
            </p>
          </div>

          {/* Error */}
          {error && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: '8px', padding: '10px 14px', marginBottom: '24px' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <span style={{ fontFamily: 'monospace', fontSize: '11px', color: '#f87171' }}>{error}</span>
            </div>
          )}

          {/* Fields */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginBottom: '28px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <UnderlineField label="Full Name" value={name} onChange={setName} placeholder="Jane Doe" disabled={loading} />
              <UnderlineField label="Email" value={email} onChange={setEmail} placeholder="you@domain.com" disabled={loading} />
            </div>
            <UnderlineField label="Password" value={password} onChange={setPassword} placeholder="min. 6 characters" type="password" disabled={loading} />

            {/* Language selector */}
            <div style={{ position: 'relative' }}>
              <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: langOpen ? '#22d3ee' : 'rgba(100,116,139,0.45)', marginBottom: '8px', transition: 'color 0.15s' }}>
                Language
              </label>
              <button
                type="button"
                onClick={() => setLangOpen(o => !o)}
                disabled={loading}
                style={{ background: 'transparent', border: 'none', borderBottom: `1px solid ${langOpen ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.08)'}`, color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace', fontSize: '13px', padding: '6px 24px 10px 0', outline: 'none', width: '100%', textAlign: 'left', cursor: 'pointer', transition: 'border-color 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
              >
                {selectedLang?.label}
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(100,116,139,0.4)" strokeWidth="2.5" strokeLinecap="round" style={{ transform: langOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}><polyline points="6 9 12 15 18 9"/></svg>
              </button>
              {/* Animated underline */}
              <div style={{ position: 'absolute', bottom: 0, left: 0, height: '1px', width: langOpen ? '100%' : '0%', background: 'linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2))', boxShadow: '0 0 8px rgba(34,211,238,0.5)', transition: 'width 0.3s ease' }} />

              {langOpen && (
                <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: '#030d1a', border: '1px solid rgba(34,211,238,0.15)', borderRadius: '8px', marginTop: '4px', zIndex: 50, overflow: 'hidden' }}>
                  {LANGUAGES.map(l => (
                    <button
                      key={l.value}
                      type="button"
                      onClick={() => { setLang(l.value); setLangOpen(false) }}
                      style={{ width: '100%', background: l.value === lang ? 'rgba(34,211,238,0.07)' : 'transparent', border: 'none', color: l.value === lang ? '#22d3ee' : 'rgba(148,163,184,0.6)', fontFamily: 'monospace', fontSize: '12px', padding: '10px 14px', textAlign: 'left', cursor: 'pointer', transition: 'background 0.1s' }}
                      onMouseEnter={e => { if (l.value !== lang) e.currentTarget.style.background = 'rgba(255,255,255,0.04)' }}
                      onMouseLeave={e => { if (l.value !== lang) e.currentTarget.style.background = 'transparent' }}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Consent */}
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', cursor: 'pointer', marginBottom: '28px' }}>
            <div
              onClick={() => setConsent(v => !v)}
              style={{
                width: '16px', height: '16px', borderRadius: '4px', flexShrink: 0, marginTop: '1px',
                background: consent ? 'rgba(34,211,238,0.15)' : 'transparent',
                border: `1px solid ${consent ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.12)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.15s', cursor: 'pointer',
              }}
            >
              {consent && <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="3" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>}
            </div>
            <span style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.5)', lineHeight: 1.7, letterSpacing: '0.02em' }}>
              I agree that my anonymized interview data may be used to improve the platform for all users.
            </span>
          </label>

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
              ? <><span style={{ width: '14px', height: '14px', border: '2px solid rgba(34,211,238,0.4)', borderTopColor: '#22d3ee', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} /> Creating…</>
              : <>Initialize <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></>
            }
          </button>
        </form>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
