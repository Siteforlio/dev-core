import { useState, useEffect } from 'react'
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
  const { getStatus, testEmail, setEmail, testCalDAV, setCalDAV, testLinkedIn, setLinkedIn } = useIntegrations()

  const [status, setStatus] = useState({ emailConfigured: false, caldavConfigured: false, linkedinConfigured: false })
  const [emailOpen, setEmailOpen] = useState(false)
  const [caldavOpen, setCalDAVOpen] = useState(false)
  const [linkedinOpen, setLinkedInOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savingLabel, setSavingLabel] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [emailForm, setEmailForm] = useState({ host: '', port: 993, username: '', password: '', smtp_host: '', smtp_port: 465 })
  const [caldavForm, setCalDAVForm] = useState({ url: '', username: '', password: '' })
  const [linkedinMode, setLinkedInMode] = useState<'cookie' | 'password'>('cookie')
  const [linkedinForm, setLinkedInForm] = useState({ email: '', password: '', session_cookie: '' })

  useEffect(() => {
    getStatus().then(setStatus).catch(() => {})
  }, [])

  const saveEmail = async () => {
    setSaving(true); setError(''); setSuccess('')
    try {
      setSavingLabel('Testing…'); await testEmail(emailForm)
      setSavingLabel('Saving…'); await setEmail(emailForm)
      setStatus(s => ({ ...s, emailConfigured: true }))
      setSuccess('Email monitoring connected.'); setEmailOpen(false)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
    finally { setSaving(false); setSavingLabel('') }
  }

  const saveCalDAV = async () => {
    setSaving(true); setError(''); setSuccess('')
    try {
      setSavingLabel('Testing…'); const msg = await testCalDAV(caldavForm)
      setSavingLabel('Saving…'); await setCalDAV(caldavForm)
      setStatus(s => ({ ...s, caldavConfigured: true }))
      setSuccess(`Calendar sync connected. ${msg}`); setCalDAVOpen(false)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
    finally { setSaving(false); setSavingLabel('') }
  }

  const saveLinkedIn = async () => {
    setSaving(true); setError(''); setSuccess('')
    const creds = linkedinMode === 'cookie'
      ? { session_cookie: linkedinForm.session_cookie }
      : { email: linkedinForm.email, password: linkedinForm.password }
    try {
      setSavingLabel('Authenticating…'); await testLinkedIn(creds)
      setSavingLabel('Saving…'); await setLinkedIn(creds)
      setStatus(s => ({ ...s, linkedinConfigured: true }))
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

  const connectedCount = [status.emailConfigured, status.caldavConfigured, status.linkedinConfigured].filter(Boolean).length

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
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.15)', borderRadius: '10px', padding: '12px 16px', marginBottom: '20px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <p style={{ fontSize: '11px', fontFamily: 'monospace', color: '#f87171' }}>{error}</p>
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

          {/* Email */}
          <IntegrationCard
            icon={<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>}
            title="Email Monitoring"
            subtitle="IMAP/SMTP — Gmail, Outlook, Apple Mail"
            tag="IMAP"
            configured={status.emailConfigured}
            open={emailOpen}
            onToggle={() => setEmailOpen(o => !o)}
            accentColor="#22d3ee"
          >
            <div className="flex flex-col" style={{ gap: '20px' }}>
              <div className="grid grid-cols-2" style={{ gap: '24px' }}>
                <Field label="IMAP Host" value={emailForm.host} onChange={v => setEmailForm(f => ({ ...f, host: v }))} placeholder="imap.gmail.com" />
                <Field label="Email Address" value={emailForm.username} onChange={v => setEmailForm(f => ({ ...f, username: v }))} placeholder="you@gmail.com" />
              </div>
              <div className="grid grid-cols-2" style={{ gap: '24px' }}>
                <Field label="App Password" value={emailForm.password} onChange={v => setEmailForm(f => ({ ...f, password: v }))} placeholder="••••••••" type="password" />
                <Field label="SMTP Host (optional)" value={emailForm.smtp_host} onChange={v => setEmailForm(f => ({ ...f, smtp_host: v }))} placeholder="smtp.gmail.com" />
              </div>
              <p style={{ fontSize: '10px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.4)', lineHeight: 1.7 }}>
                Gmail: generate an App Password at myaccount.google.com/apppasswords — do not use your account password.
              </p>
              <SaveBtn onClick={saveEmail} disabled={saving || !emailForm.host || !emailForm.username || !emailForm.password} />
            </div>
          </IntegrationCard>

          {/* CalDAV */}
          <IntegrationCard
            icon={<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>}
            title="Calendar Sync"
            subtitle="CalDAV — Google, Apple, Outlook"
            tag="CalDAV"
            configured={status.caldavConfigured}
            open={caldavOpen}
            onToggle={() => setCalDAVOpen(o => !o)}
            accentColor="#a78bfa"
          >
            <div className="flex flex-col" style={{ gap: '20px' }}>
              <Field label="CalDAV URL" value={caldavForm.url} onChange={v => setCalDAVForm(f => ({ ...f, url: v }))} placeholder="https://caldav.icloud.com/" />
              <div className="grid grid-cols-2" style={{ gap: '24px' }}>
                <Field label="Username" value={caldavForm.username} onChange={v => setCalDAVForm(f => ({ ...f, username: v }))} placeholder="you@icloud.com" />
                <Field label="Password / App Password" value={caldavForm.password} onChange={v => setCalDAVForm(f => ({ ...f, password: v }))} placeholder="••••••••" type="password" />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                {[
                  ['Google', 'calendar/dav/[email]/events/'],
                  ['Apple', 'caldav.icloud.com/'],
                  ['Outlook', 'office365.com/caldav/v1/[email]/'],
                ].map(([name, url]) => (
                  <div key={name} style={{ background: 'rgba(167,139,250,0.05)', border: '1px solid rgba(167,139,250,0.1)', borderRadius: '8px', padding: '10px 12px' }}>
                    <p style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, color: 'rgba(167,139,250,0.7)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: '4px' }}>{name}</p>
                    <p style={{ fontSize: '9px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.5)', wordBreak: 'break-all', lineHeight: 1.5 }}>{url}</p>
                  </div>
                ))}
              </div>
              <SaveBtn onClick={saveCalDAV} disabled={saving || !caldavForm.url || !caldavForm.username || !caldavForm.password} />
            </div>
          </IntegrationCard>

          {/* LinkedIn */}
          <IntegrationCard
            icon={<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>}
            title="LinkedIn Scraping"
            subtitle="Auto-discover jobs + enable hiring manager outreach"
            tag="OAuth"
            configured={status.linkedinConfigured}
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
