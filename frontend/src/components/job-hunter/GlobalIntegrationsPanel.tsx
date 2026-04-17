import { useState, useEffect } from 'react'
import { useIntegrations } from '../../hooks/useIntegrations'

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
      setSavingLabel('Testing connection…')
      await testEmail(emailForm)
      setSavingLabel('Saving…')
      await setEmail(emailForm)
      setStatus(s => ({ ...s, emailConfigured: true }))
      setSuccess('Email monitoring connected and saved.')
      setEmailOpen(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to connect')
    } finally { setSaving(false); setSavingLabel('') }
  }

  const saveCalDAV = async () => {
    setSaving(true); setError(''); setSuccess('')
    try {
      setSavingLabel('Testing connection…')
      const msg = await testCalDAV(caldavForm)
      setSavingLabel('Saving…')
      await setCalDAV(caldavForm)
      setStatus(s => ({ ...s, caldavConfigured: true }))
      setSuccess(`Calendar sync connected and saved. ${msg}`)
      setCalDAVOpen(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to connect')
    } finally { setSaving(false); setSavingLabel('') }
  }

  const saveLinkedIn = async () => {
    setSaving(true); setError(''); setSuccess('')
    const creds = linkedinMode === 'cookie'
      ? { session_cookie: linkedinForm.session_cookie }
      : { email: linkedinForm.email, password: linkedinForm.password }
    try {
      setSavingLabel('Testing auth…')
      await testLinkedIn(creds)
      setSavingLabel('Saving…')
      await setLinkedIn(creds)
      setStatus(s => ({ ...s, linkedinConfigured: true }))
      setSuccess('LinkedIn connected and saved.')
      setLinkedInOpen(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to connect')
    } finally { setSaving(false); setSavingLabel('') }
  }

  return (
    <div className="max-w-lg mx-auto flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-white">Integrations</h2>
        <p className="text-xs text-gray-500 mt-0.5">Configure once — toggle per campaign from the campaign settings.</p>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}
      {success && <p className="text-xs text-green-400">{success}</p>}

      {/* Email */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-white font-medium">Email Monitoring</p>
            <p className="text-xs text-gray-500">IMAP/SMTP — Gmail, Outlook, Apple Mail</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${status.emailConfigured ? 'bg-green-900 text-green-300' : 'bg-gray-800 text-gray-500'}`}>
              {status.emailConfigured ? 'Connected' : 'Not set'}
            </span>
            <button
              onClick={() => setEmailOpen(o => !o)}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              {emailOpen ? 'Cancel' : status.emailConfigured ? 'Update' : 'Configure'}
            </button>
          </div>
        </div>

        {emailOpen && (
          <div className="flex flex-col gap-2 pt-2 border-t border-gray-800">
            {[
              { label: 'IMAP Host', key: 'host', placeholder: 'imap.gmail.com' },
              { label: 'Email Address', key: 'username', placeholder: 'you@gmail.com' },
              { label: 'App Password', key: 'password', placeholder: '••••••••', type: 'password' },
              { label: 'SMTP Host (optional)', key: 'smtp_host', placeholder: 'smtp.gmail.com' },
            ].map(({ label, key, placeholder, type }) => (
              <div key={key} className="flex flex-col gap-1">
                <label className="text-xs text-gray-400">{label}</label>
                <input
                  type={type ?? 'text'}
                  value={emailForm[key as keyof typeof emailForm] as string}
                  onChange={e => setEmailForm(f => ({ ...f, [key]: e.target.value }))}
                  placeholder={placeholder}
                  className="bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            ))}
            <p className="text-xs text-gray-600">For Gmail: use an App Password (not your account password). Enable IMAP in Gmail settings first.</p>
            <button
              onClick={saveEmail}
              disabled={saving || !emailForm.host || !emailForm.username || !emailForm.password}
              className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-3 py-1.5 rounded font-medium transition-colors self-end"
            >
              {saving ? savingLabel : 'Test & Save'}
            </button>
          </div>
        )}
      </div>

      {/* CalDAV */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-white font-medium">Calendar Sync</p>
            <p className="text-xs text-gray-500">CalDAV — Google, Apple, Outlook</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${status.caldavConfigured ? 'bg-green-900 text-green-300' : 'bg-gray-800 text-gray-500'}`}>
              {status.caldavConfigured ? 'Connected' : 'Not set'}
            </span>
            <button
              onClick={() => setCalDAVOpen(o => !o)}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              {caldavOpen ? 'Cancel' : status.caldavConfigured ? 'Update' : 'Configure'}
            </button>
          </div>
        </div>

        {caldavOpen && (
          <div className="flex flex-col gap-2 pt-2 border-t border-gray-800">
            {[
              { label: 'CalDAV URL', key: 'url', placeholder: 'https://caldav.icloud.com/' },
              { label: 'Username', key: 'username', placeholder: 'you@icloud.com' },
              { label: 'Password / App Password', key: 'password', placeholder: '••••••••', type: 'password' },
            ].map(({ label, key, placeholder, type }) => (
              <div key={key} className="flex flex-col gap-1">
                <label className="text-xs text-gray-400">{label}</label>
                <input
                  type={type ?? 'text'}
                  value={caldavForm[key as keyof typeof caldavForm]}
                  onChange={e => setCalDAVForm(f => ({ ...f, [key]: e.target.value }))}
                  placeholder={placeholder}
                  className="bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            ))}
            <div className="text-xs text-gray-600 flex flex-col gap-0.5">
              <span>Google: <code className="text-gray-500 break-all">https://www.google.com/calendar/dav/[email]/events/</code></span>
              <span>Apple: <code className="text-gray-500 break-all">https://caldav.icloud.com/</code></span>
              <span>Outlook: <code className="text-gray-500 break-all">https://outlook.office365.com/caldav/v1/[email]/calendar/</code></span>
            </div>
            <button
              onClick={saveCalDAV}
              disabled={saving || !caldavForm.url || !caldavForm.username || !caldavForm.password}
              className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-3 py-1.5 rounded font-medium transition-colors self-end"
            >
              {saving ? savingLabel : 'Test & Save'}
            </button>
          </div>
        )}
      </div>

      {/* LinkedIn */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-white font-medium">LinkedIn Scraping</p>
            <p className="text-xs text-gray-500">Auto-discover jobs + enable hiring manager outreach</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${status.linkedinConfigured ? 'bg-green-900 text-green-300' : 'bg-gray-800 text-gray-500'}`}>
              {status.linkedinConfigured ? 'Connected' : 'Not set'}
            </span>
            <button
              onClick={() => setLinkedInOpen(o => !o)}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              {linkedinOpen ? 'Cancel' : status.linkedinConfigured ? 'Update' : 'Configure'}
            </button>
          </div>
        </div>

        {linkedinOpen && (
          <div className="flex flex-col gap-3 pt-2 border-t border-gray-800">
            <div className="flex gap-1 bg-gray-800 rounded p-0.5 self-start">
              {(['cookie', 'password'] as const).map(m => (
                <button
                  key={m}
                  onClick={() => setLinkedInMode(m)}
                  className={`text-xs px-3 py-1 rounded transition-colors ${linkedinMode === m ? 'bg-gray-600 text-white' : 'text-gray-500 hover:text-gray-300'}`}
                >
                  {m === 'cookie' ? 'Session Cookie' : 'Email & Password'}
                </button>
              ))}
            </div>

            {linkedinMode === 'cookie' ? (
              <>
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-gray-400">li_at Cookie Value</label>
                  <input
                    type="password"
                    value={linkedinForm.session_cookie}
                    onChange={e => setLinkedInForm(f => ({ ...f, session_cookie: e.target.value }))}
                    placeholder="AQE…"
                    className="bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 font-mono"
                  />
                </div>
                <div className="text-xs text-gray-600 flex flex-col gap-0.5">
                  <p className="font-medium text-gray-500">How to get your cookie:</p>
                  <p>1. Open LinkedIn in Chrome and log in (via Google is fine)</p>
                  <p>2. Press F12 → Application tab → Cookies → https://www.linkedin.com</p>
                  <p>3. Find <code className="text-gray-400">li_at</code> → copy the Value column</p>
                  <p className="text-gray-700 mt-1">Cookie is valid until you log out of LinkedIn. Re-paste if it expires.</p>
                </div>
              </>
            ) : (
              <>
                {[
                  { label: 'LinkedIn Email', key: 'email', placeholder: 'you@email.com' },
                  { label: 'Password', key: 'password', placeholder: '••••••••', type: 'password' },
                ].map(({ label, key, placeholder, type }) => (
                  <div key={key} className="flex flex-col gap-1">
                    <label className="text-xs text-gray-400">{label}</label>
                    <input
                      type={type ?? 'text'}
                      value={linkedinForm[key as keyof typeof linkedinForm]}
                      onChange={e => setLinkedInForm(f => ({ ...f, [key]: e.target.value }))}
                      placeholder={placeholder}
                      className="bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                ))}
                <p className="text-xs text-gray-600">For accounts that sign in with email/password directly. Google/SSO accounts should use Session Cookie instead.</p>
              </>
            )}

            <button
              onClick={saveLinkedIn}
              disabled={saving || (linkedinMode === 'cookie' ? !linkedinForm.session_cookie : !linkedinForm.email || !linkedinForm.password)}
              className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-3 py-1.5 rounded font-medium transition-colors self-end"
            >
              {saving ? savingLabel : 'Test & Save'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
