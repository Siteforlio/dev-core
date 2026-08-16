import { useEffect, useRef, useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'
import { useAuthStore } from '../../store/authStore'
import { getStoredExtId } from './ExtensionBanner'
import type { ApplicationDetail, ChatMessage } from '../../types/jobHunter'
import { API_BASE, API_ROOT } from '../../lib/apiBase'

// ── Palette — matches app's cool dark navy ───────────────────────────────────
const C = {
  bg:           '#0b1118',
  surface:      '#0f1824',
  surfaceHover: '#131f2e',
  border:       '#1a2840',
  borderMuted:  '#111e2e',
  textPrime:    '#dce8f8',
  textSecond:   '#6a8aaa',
  textMuted:    '#344f68',
  textDim:      '#1e3048',
  teal:         '#00c8bc',
  tealDim:      '#005f58',
  tealBg:       '#061a1f',
  tealBorder:   '#093d40',
  green:        '#34c98a',
  greenBg:      '#071a12',
  greenBorder:  '#0c3020',
  violet:       '#8b80f8',
  violetBg:     '#0d0f28',
  violetBorder: '#2a2568',
  blue:         '#5ba8e0',
  blueBg:       '#091828',
  blueBorder:   '#0e2a42',
  amber:        '#f0a840',
  amberBg:      '#1e1508',
  amberBorder:  '#402808',
}

// ── Inline SVG icons ─────────────────────────────────────────────────────────
const IconExternal = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 2H2.5A1.5 1.5 0 001 3.5v6A1.5 1.5 0 002.5 11h6A1.5 1.5 0 0010 9.5V7" />
    <path d="M7.5 1H11v3.5M11 1L5.5 6.5" />
  </svg>
)
const IconBolt = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 1.5L3.5 7h4.5L4.5 11" />
  </svg>
)
const IconCheck = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 6l3 3 5-5" />
  </svg>
)
const IconWand = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 11L8 4M8 4l1-2 1 1M8 4l-2-1 1-1" />
    <path d="M10 8l1-1M9 10.5l1-1M11.5 8.5l-1 1" />
  </svg>
)
const IconDoc = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 1H3a1 1 0 00-1 1v8a1 1 0 001 1h6a1 1 0 001-1V4.5L7 1z" />
    <path d="M7 1v3.5H10M4 7h4M4 9h2" />
  </svg>
)
const IconFolder = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 4a1 1 0 011-1h2.382a1 1 0 01.894.553L6 5h5a1 1 0 011 1v4a1 1 0 01-1 1H2a1 1 0 01-1-1V4z" />
  </svg>
)
const IconSparkle = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 1.5L7 5l3.5 1L7 7l-1 3.5L5 7 1.5 6 5 5z" />
  </svg>
)
const IconSend = () => (
  <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 11.5V2.5M3 6.5l4-4 4 4" />
  </svg>
)
const IconClose = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
    <path d="M2 2l8 8M10 2L2 10" />
  </svg>
)
const IconChevron = ({ open }: { open: boolean }) => (
  <svg
    width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor"
    strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
    style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
  >
    <path d="M2 4.5l4 4 4-4" />
  </svg>
)
const IconDownload = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 1v7M3.5 5.5L6 8l2.5-2.5M2 10h8" />
  </svg>
)

// ── Helpers ──────────────────────────────────────────────────────────────────
const getExtensionInfo = (): { installed: boolean; id: string | null } => {
  const domId = document.documentElement.getAttribute('data-jh-ext-id')
  if (domId) return { installed: true, id: domId }
  const storedId = getStoredExtId()
  if (storedId) return { installed: true, id: storedId }
  return { installed: false, id: null }
}

function BoldText({ text }: { text: string }) {
  const parts = text.split(/\*\*(.*?)\*\*/g)
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1
          ? <strong key={i} style={{ color: C.textPrime, fontWeight: 600 }}>{part}</strong>
          : <span key={i}>{part}</span>
      )}
    </>
  )
}

// Minimal icon button
function IconBtn({
  onClick, disabled, children, color, bg, border, title,
}: {
  onClick?: () => void; disabled?: boolean; children: React.ReactNode
  color?: string; bg?: string; border?: string; title?: string
}) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: '5px',
        padding: '6px 11px', borderRadius: '8px', fontSize: '11px',
        fontWeight: 500, letterSpacing: '0.01em', whiteSpace: 'nowrap',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        transition: 'all 0.15s',
        color: hov ? (color ?? C.textPrime) : (color ?? C.textSecond),
        background: hov ? (bg ?? C.surfaceHover) : 'transparent',
        border: `1px solid ${hov ? (border ?? C.border) : C.borderMuted}`,
      }}
    >
      {children}
    </button>
  )
}

// Accent (filled) button
function AccentBtn({
  onClick, disabled, children, accent = C.teal, accentBg = C.tealBg, accentBorder = C.tealBorder,
}: {
  onClick?: () => void; disabled?: boolean; children: React.ReactNode
  accent?: string; accentBg?: string; accentBorder?: string
}) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: '5px',
        padding: '6px 13px', borderRadius: '8px', fontSize: '11px',
        fontWeight: 600, letterSpacing: '0.01em', whiteSpace: 'nowrap',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        transition: 'all 0.15s',
        color: accent,
        background: hov ? accentBg : 'transparent',
        border: `1px solid ${hov ? accentBorder : accentBorder}`,
        boxShadow: hov ? `0 0 12px ${accent}18` : 'none',
      }}
    >
      {children}
    </button>
  )
}

interface Props {
  campaignId: string
  applicationId: string
  onClose: () => void
  onApplied?: () => void
}

const QUICK_PROMPTS = [
  'Write cover letter',
  'What should I emphasise?',
  'Answer custom form questions',
  'Summarise this job',
]

// ── Component ─────────────────────────────────────────────────────────────────
export default function ApplyPanel({ campaignId, applicationId, onClose, onApplied }: Props) {
  const {
    getApplicationDetail, generateCoverLetter, chatWithApplication,
    openInChrome, patchApplicationStatus, triggerTailoring,
  } = useJobHunter()

  const [detail, setDetail]           = useState<ApplicationDetail | null>(null)
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState('')
  const [messages, setMessages]       = useState<ChatMessage[]>([])
  const [input, setInput]             = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [coverLoading, setCoverLoading]   = useState(false)
  const [coverLetter, setCoverLetter]     = useState<string | null>(null)
  const [showCover, setShowCover]         = useState(false)
  const [chromeLoading, setChromeLoading] = useState(false)
  const [markingApplied, setMarkingApplied] = useState(false)
  const [tailorLoading, setTailorLoading]   = useState(false)
  const [tailorQueued, setTailorQueued]     = useState(false)
  const [showDesc, setShowDesc]           = useState(false)
  const [extInstalled, setExtInstalled]   = useState(false)
  const [extId, setExtId]                 = useState<string | null>(null)
  const [fillStatus, setFillStatus]       = useState<'idle'|'waiting'|'filling'|'done'|'error'>('idle')
  const [fillStatusMsg, setFillStatusMsg] = useState('')
  const fillPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const { installed, id } = getExtensionInfo()
    setExtInstalled(installed)
    setExtId(id)
  }, [])


  const stopFillPoll = () => {
    if (fillPollRef.current) { clearInterval(fillPollRef.current); fillPollRef.current = null }
  }

  const startFillPoll = (fillId: string, token: string) => {
    stopFillPoll()
    fillPollRef.current = setInterval(async () => {
      try {
        const res = await fetch(
          `${API_BASE()}/job-hunter/ext/pending-fill/${fillId}/status`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
        if (!res.ok) return
        const { data } = await res.json()
        const s = data.status as string
        if (s === 'filling') {
          setFillStatus('filling')
          setFillStatusMsg('Filling your form…')
        } else if (s === 'done') {
          stopFillPoll()
          setFillStatus('done')
          const parts = []
          if (data.filled != null) parts.push(`${data.filled} fields filled`)
          if (data.needsReview) parts.push(`${data.needsReview} need your review`)
          if (data.resumeUploaded) parts.push('resume uploaded')
          setFillStatusMsg(parts.join(' · ') || 'Done')
        } else if (s === 'error') {
          stopFillPoll()
          setFillStatus('error')
          setFillStatusMsg(data.error || 'Extension error')
        }
      } catch { /* silent */ }
    }, 2000)
    // Stop polling after 10 min (fill TTL)
    setTimeout(stopFillPoll, 600_000)
  }

  useEffect(() => () => stopFillPoll(), [])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pollRef        = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  const startPolling = () => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const d = await getApplicationDetail(campaignId, applicationId)
        if (d.resumePath) {
          setDetail(d)
          setCoverLetter(prev => prev ?? d.coverLetter)
          setTailorQueued(false)
          setMessages(prev => [...prev, {
            role: 'assistant' as const,
            content: `Resume ready — **${d.resumeFilename}**. Use the buttons above to view it or open the folder.`,
          }])
          stopPolling()
        }
      } catch { /* silent */ }
    }, 5000)
  }

  useEffect(() => () => stopPolling(), [])

  useEffect(() => {
    setLoading(true); setError(''); setMessages([]); setTailorQueued(false); stopPolling()
    getApplicationDetail(campaignId, applicationId)
      .then(d => {
        setDetail(d); setCoverLetter(d.coverLetter)
        setMessages([{
          role: 'assistant',
          content: d.resumeFilename
            ? `Context loaded for **${d.title}** at **${d.company}**. Resume ready — **${d.resumeFilename}**. Ask me anything or use the quick actions below.`
            : `Context loaded for **${d.title}** at **${d.company}**. No tailored resume yet — click Tailor resume to generate one.`,
        }])
      })
      .catch(() => setError('Failed to load application details.'))
      .finally(() => setLoading(false))
  }, [applicationId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!text.trim() || chatLoading) return
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setInput(''); setChatLoading(true)
    try {
      const reply = await chatWithApplication(campaignId, applicationId, text, messages)
      setMessages(prev => [...prev, { role: 'assistant', content: reply }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, something went wrong.' }])
    } finally {
      setChatLoading(false)
    }
  }

  const handleGenerateCoverLetter = async () => {
    setCoverLoading(true)
    try { const cl = await generateCoverLetter(campaignId, applicationId); setCoverLetter(cl); setShowCover(true) }
    catch { /* retry */ } finally { setCoverLoading(false) }
  }

  const handleOpenInChrome = async () => {
    if (!detail?.applyUrl) return
    setChromeLoading(true)
    setFillStatus('idle')
    setFillStatusMsg('')
    stopFillPoll()
    try {
      const token = useAuthStore.getState().accessToken

      // Create a pending fill in Redis so the extension can pick it up by polling
      let fillId: string | null = null
      if (token) {
        try {
          const res = await fetch(
            `${API_BASE()}/job-hunter/ext/pending-fill`,
            {
              method: 'POST',
              headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({
                app_id: applicationId,
                apply_url: detail.applyUrl,
                job_title: detail.title,
                company: detail.company,
              }),
            }
          )
          if (res.ok) {
            const { data } = await res.json()
            fillId = data.fillId
          }
        } catch { /* non-fatal — open without auto-fill */ }
      }

      // Get (or reuse cached) long-lived extension token — valid for 1 year
      let extToken = token
      if (token) {
        try {
          const tokRes = await fetch(`${API_BASE()}/job-hunter/ext/token`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
          })
          if (tokRes.ok) {
            const { data } = await tokRes.json()
            extToken = data.token
          }
        } catch { /* fall back to short-lived token */ }
      }

      // Open the link page in Chrome — it stores the long-lived token then redirects.
      const linkUrl = fillId && extToken
        ? `${API_BASE()}/job-hunter/ext/link?t=${encodeURIComponent(extToken)}&redirect=${encodeURIComponent(detail.applyUrl)}&fill=${fillId}`
        : detail.applyUrl

      try { await openInChrome(campaignId, applicationId, linkUrl) }
      catch { window.open(linkUrl, '_blank') }

      // Start polling for fill status if we registered a pending fill
      if (fillId && extToken) {
        setFillStatus('waiting')
        setFillStatusMsg('Waiting for extension to detect the form…')
        startFillPoll(fillId, extToken)
      }
    } finally { setChromeLoading(false) }
  }

  const handleMarkApplied = async () => {
    setMarkingApplied(true)
    try { await patchApplicationStatus(campaignId, applicationId, 'applied'); onApplied?.() }
    catch { /* retry */ } finally { setMarkingApplied(false) }
  }

  const handleTriggerTailoring = async () => {
    setTailorLoading(true)
    try { await triggerTailoring(campaignId, applicationId); setTailorQueued(true); startPolling() }
    catch { /* retry */ } finally { setTailorLoading(false) }
  }

  const resumeApiUrl = `${API_BASE()}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/resume`
  const getAuth     = () => { const t = useAuthStore.getState().accessToken; return t ? `Bearer ${t}` : '' }

  const handleViewResume = async () => {
    try {
      const res = await fetch(resumeApiUrl, { headers: { Authorization: getAuth() } })
      if (!res.ok) throw new Error()
      const url = URL.createObjectURL(await res.blob())
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch (e) { console.error('handleViewResume:', e) }
  }

  const handleOpenFolder = async () => {
    try {
      await fetch(
        `${API_BASE()}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/resume/reveal`,
        { method: 'POST', headers: { Authorization: getAuth() } }
      )
    } catch (e) { console.error('handleOpenFolder:', e) }
  }

  const handleExportCoverLetter = () => {
    if (!coverLetter) return
    const a  = document.createElement('a')
    a.href   = URL.createObjectURL(new Blob([coverLetter], { type: 'text/plain' }))
    a.download = `${detail?.company ?? 'cover'}-letter.txt`
    a.click(); URL.revokeObjectURL(a.href)
  }

  const isApplied = ['applied', 'interview', 'offer', 'responded'].includes(detail?.status ?? '')

  // ── Loading / error ──────────────────────────────────────────────────────

  if (loading) return (
    <div className="flex h-full items-center justify-center" style={{ background: C.bg }}>
      <div style={{
        width: 20, height: 20, borderRadius: '50%',
        border: `2px solid ${C.tealBorder}`,
        borderTopColor: C.teal,
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )

  if (error || !detail) return (
    <div className="flex flex-col h-full items-center justify-center gap-3" style={{ background: C.bg }}>
      <p style={{ color: '#c47a7a', fontSize: 13 }}>{error || 'Not found'}</p>
      <button onClick={onClose} style={{ color: C.textMuted, fontSize: 12 }}>Close</button>
    </div>
  )

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="relative flex flex-col h-full overflow-hidden" style={{ background: C.bg }}>
      <style>{`
        .ap-scrollhide::-webkit-scrollbar { display: none }
        .ap-scrollhide { -ms-overflow-style: none; scrollbar-width: none }
        .ap-btn-ghost:hover { background: ${C.surfaceHover} !important; border-color: ${C.border} !important; color: ${C.textPrime} !important }
        .ap-ta::placeholder { color: ${C.textDim} }
        .ap-ta:focus { outline: none; border-color: ${C.border} !important }
        .ap-qp:hover { border-color: ${C.border} !important; color: ${C.textSecond} !important }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div
        className="flex items-start justify-between flex-shrink-0"
        style={{ padding: '20px 22px 16px', borderBottom: `1px solid ${C.borderMuted}` }}
      >
        <div style={{ minWidth: 0, flex: 1, paddingRight: 12 }}>
          {/* Company breadcrumb */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span style={{
              fontSize: 10, fontWeight: 600, letterSpacing: '0.1em',
              textTransform: 'uppercase', color: C.teal,
            }}>
              {detail.company}
            </span>
            <span style={{ color: C.textDim, fontSize: 10 }}>·</span>
            <span style={{ fontSize: 10, color: C.textMuted, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {detail.location || 'Remote'}
            </span>
          </div>

          {/* Title */}
          <h1 style={{
            fontSize: 16, fontWeight: 600, color: C.textPrime,
            lineHeight: 1.3, letterSpacing: '-0.01em',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {detail.title}
          </h1>
        </div>

        {/* Right: status badge + close */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, marginTop: 2 }}>
          {isApplied && (
            <span style={{
              fontSize: 10, fontWeight: 600, letterSpacing: '0.08em',
              textTransform: 'uppercase', color: C.green,
              background: C.greenBg, border: `1px solid ${C.greenBorder}`,
              padding: '3px 8px', borderRadius: 20,
            }}>
              Applied
            </span>
          )}
          <button
            onClick={onClose}
            style={{
              width: 26, height: 26, borderRadius: 7, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              color: C.textMuted, background: 'transparent',
              border: `1px solid ${C.borderMuted}`, cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = C.textPrime; e.currentTarget.style.borderColor = C.border }}
            onMouseLeave={e => { e.currentTarget.style.color = C.textMuted; e.currentTarget.style.borderColor = C.borderMuted }}
          >
            <IconClose />
          </button>
        </div>
      </div>

      {/* ── Primary actions ─────────────────────────────────────────────── */}
      <div
        className="flex flex-wrap gap-2 flex-shrink-0"
        style={{ padding: '12px 22px', borderBottom: `1px solid ${C.borderMuted}` }}
      >
        {detail.applyUrl && (
          <a
            href={detail.applyUrl}
            target="_blank"
            rel="noreferrer"
            className="ap-btn-ghost"
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '6px 11px', borderRadius: 8, fontSize: 11,
              fontWeight: 500, color: C.textSecond, textDecoration: 'none',
              border: `1px solid ${C.borderMuted}`, transition: 'all 0.15s',
            }}
          >
            <IconExternal /> View posting
          </a>
        )}

        {!isApplied ? (
          <button
            onClick={handleOpenInChrome}
            disabled={chromeLoading}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '6px 13px', borderRadius: 8, fontSize: 11,
              fontWeight: 600, letterSpacing: '0.01em', cursor: 'pointer',
              transition: 'all 0.15s', whiteSpace: 'nowrap',
              color: C.teal, background: C.tealBg,
              border: `1px solid ${C.tealBorder}`,
              opacity: chromeLoading ? 0.6 : 1,
            }}
            onMouseEnter={e => (e.currentTarget.style.boxShadow = `0 0 14px ${C.teal}20`)}
            onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
          >
            <IconBolt />
            {chromeLoading ? 'Opening…' : extInstalled ? 'Open & Auto-Fill' : 'Open in Chrome'}
          </button>
        ) : (
          <button
            onClick={handleOpenInChrome}
            disabled={chromeLoading}
            className="ap-btn-ghost"
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '6px 11px', borderRadius: 8, fontSize: 11,
              fontWeight: 500, color: C.textSecond, cursor: 'pointer',
              border: `1px solid ${C.borderMuted}`, transition: 'all 0.15s',
              opacity: chromeLoading ? 0.6 : 1,
            }}
          >
            <IconBolt />
            {chromeLoading ? 'Opening…' : 'Open job'}
          </button>
        )}

        {!isApplied && (
          <button
            onClick={handleMarkApplied}
            disabled={markingApplied}
            className="ap-btn-ghost"
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '6px 11px', borderRadius: 8, fontSize: 11,
              fontWeight: 500, color: C.green, cursor: 'pointer',
              border: `1px solid ${C.greenBorder}`, background: C.greenBg,
              transition: 'all 0.15s', opacity: markingApplied ? 0.6 : 1,
            }}
          >
            <IconCheck />
            {markingApplied ? '…' : 'Mark applied'}
          </button>
        )}
      </div>

      {/* ── Extension fill status ────────────────────────────────────────── */}
      {fillStatus !== 'idle' && (
        <div style={{
          padding: '8px 22px',
          borderBottom: `1px solid ${C.borderMuted}`,
          display: 'flex', alignItems: 'center', gap: 8,
          flexShrink: 0,
        }}>
          {/* Status dot */}
          <div style={{
            width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
            background: fillStatus === 'done' ? C.green
                      : fillStatus === 'error' ? '#f87171'
                      : fillStatus === 'filling' ? C.violet
                      : C.teal,
            animation: (fillStatus === 'waiting' || fillStatus === 'filling') ? 'jh-pulse 1s infinite' : 'none',
          }} />
          <span style={{ fontSize: 11, color: C.textMuted, flex: 1 }}>{fillStatusMsg}</span>
          {(fillStatus === 'done' || fillStatus === 'error') && (
            <button
              onClick={() => { setFillStatus('idle'); setFillStatusMsg('') }}
              style={{ background: 'none', border: 'none', color: C.textDim, cursor: 'pointer', fontSize: 11 }}
            >
              ✕
            </button>
          )}
          <style>{`@keyframes jh-pulse{0%,100%{opacity:1}50%{opacity:0.3}}`}</style>
        </div>
      )}

      {/* ── Resume section ───────────────────────────────────────────────── */}
      <div
        className="flex-shrink-0"
        style={{ padding: '14px 22px', borderBottom: `1px solid ${C.borderMuted}` }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: C.textDim }}>
            Resume
          </span>
          {detail.resumeFilename && (
            <span style={{ fontSize: 12, color: C.textSecond, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
              {detail.resumeFilename}
            </span>
          )}
          {!detail.resumeFilename && tailorQueued && (
            <span style={{ fontSize: 11, color: C.teal, fontStyle: 'italic' }}>Tailoring in progress…</span>
          )}
          {!detail.resumeFilename && !tailorQueued && (
            <span style={{ fontSize: 11, color: C.textMuted, fontStyle: 'italic' }}>No tailored resume yet</span>
          )}
        </div>

        {/* Resume actions */}
        <div className="flex flex-wrap gap-1.5">
          {!detail.resumeFilename && (
            <button
              onClick={handleTriggerTailoring}
              disabled={tailorLoading || tailorQueued}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 10px', borderRadius: 7, fontSize: 11, fontWeight: 500,
                color: C.amber, background: C.amberBg, border: `1px solid ${C.amberBorder}`,
                cursor: (tailorLoading || tailorQueued) ? 'not-allowed' : 'pointer',
                opacity: (tailorLoading || tailorQueued) ? 0.5 : 1, transition: 'all 0.15s',
              }}
            >
              <IconWand />
              {tailorLoading ? 'Queuing…' : tailorQueued ? 'Queued' : 'Tailor resume'}
            </button>
          )}
          {detail.resumePath && (
            <>
              <button
                onClick={handleViewResume}
                className="ap-btn-ghost"
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '5px 10px', borderRadius: 7, fontSize: 11, fontWeight: 500,
                  color: C.blue, border: `1px solid ${C.blueBorder}`,
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                <IconDoc /> View PDF
              </button>
              <button
                onClick={handleOpenFolder}
                className="ap-btn-ghost"
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '5px 10px', borderRadius: 7, fontSize: 11, fontWeight: 500,
                  color: C.textSecond, border: `1px solid ${C.borderMuted}`,
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                <IconFolder /> Open folder
              </button>
            </>
          )}
          <button
            onClick={coverLetter ? () => setShowCover(true) : handleGenerateCoverLetter}
            disabled={coverLoading}
            className="ap-btn-ghost"
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '5px 10px', borderRadius: 7, fontSize: 11, fontWeight: 500,
              color: C.violet, border: `1px solid ${C.violetBorder}`,
              cursor: coverLoading ? 'not-allowed' : 'pointer',
              opacity: coverLoading ? 0.5 : 1, transition: 'all 0.15s',
            }}
          >
            <IconSparkle />
            {coverLoading ? 'Generating…' : coverLetter ? 'Cover letter' : 'Generate cover letter'}
          </button>
        </div>
      </div>

      {/* ── Cover letter overlay ─────────────────────────────────────────── */}
      {showCover && coverLetter && (
        <div
          className="absolute inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(6,9,14,0.92)', padding: 24 }}
        >
          <div style={{
            width: '100%', maxWidth: 560, maxHeight: '78vh',
            display: 'flex', flexDirection: 'column', borderRadius: 14,
            background: C.surface, border: `1px solid ${C.border}`,
            boxShadow: '0 24px 60px rgba(0,0,0,0.6)',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '14px 18px', borderBottom: `1px solid ${C.borderMuted}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <IconSparkle />
                <span style={{ fontSize: 13, fontWeight: 600, color: C.textPrime }}>
                  Cover Letter · {detail.company}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  onClick={handleExportCoverLetter}
                  className="ap-btn-ghost"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '5px 10px', borderRadius: 7, fontSize: 11,
                    color: C.textSecond, border: `1px solid ${C.borderMuted}`, cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  <IconDownload /> Export
                </button>
                <button
                  onClick={() => setShowCover(false)}
                  style={{
                    width: 26, height: 26, borderRadius: 7, display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    color: C.textMuted, background: 'transparent',
                    border: `1px solid ${C.borderMuted}`, cursor: 'pointer',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = C.textPrime)}
                  onMouseLeave={e => (e.currentTarget.style.color = C.textMuted)}
                >
                  <IconClose />
                </button>
              </div>
            </div>
            <div className="ap-scrollhide" style={{ flex: 1, overflowY: 'auto', padding: '18px' }}>
              <p style={{ fontSize: 13, color: C.textSecond, lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>
                {coverLetter}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Job description ──────────────────────────────────────────────── */}
      {detail.description && (
        <div className="flex-shrink-0" style={{ borderBottom: `1px solid ${C.borderMuted}` }}>
          <button
            onClick={() => setShowDesc(v => !v)}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 22px', background: 'transparent', border: 'none',
              cursor: 'pointer', transition: 'background 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = C.surfaceHover)}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: C.textMuted }}>
              Job Description
            </span>
            <span style={{ color: C.textMuted }}><IconChevron open={showDesc} /></span>
          </button>
          {showDesc && (
            <div className="ap-scrollhide" style={{ padding: '0 22px 14px', maxHeight: 180, overflowY: 'auto' }}>
              <p style={{ fontSize: 12, color: C.textMuted, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                {detail.description
                  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
                  .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ')
                  .replace(/<[^>]+>/g, '').replace(/\n{3,}/g, '\n\n').trim()}
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Chat ─────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Context status bar */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 7,
          padding: '7px 22px', borderBottom: `1px solid ${C.borderMuted}`,
          flexShrink: 0,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
            background: C.teal, boxShadow: `0 0 6px ${C.teal}`,
          }} />
          <span style={{ fontSize: 11, color: C.textMuted }}>
            Context loaded — {detail.company} · {detail.title}
          </span>
        </div>

        {/* Messages */}
        <div
          className="ap-scrollhide flex-1 overflow-y-auto"
          style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}
        >
          {messages.map((msg, i) => (
            <div key={i} style={{
              display: 'flex', gap: 10,
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
            }}>
              {/* Avatar */}
              <div style={{
                width: 24, height: 24, borderRadius: 7, flexShrink: 0, marginTop: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: msg.role === 'assistant' ? C.violetBg : C.surfaceHover,
                border: `1px solid ${msg.role === 'assistant' ? C.violetBorder : C.border}`,
                color: msg.role === 'assistant' ? C.violet : C.textMuted,
              }}>
                {msg.role === 'assistant' ? <IconSparkle /> : (
                  <span style={{ fontSize: 9, fontWeight: 700, color: C.textMuted }}>S</span>
                )}
              </div>

              {/* Bubble */}
              <div style={{
                padding: '9px 13px', borderRadius: 11, fontSize: 13,
                lineHeight: 1.6, maxWidth: '82%',
                background: msg.role === 'assistant' ? C.surface : C.surfaceHover,
                border: `1px solid ${msg.role === 'assistant' ? C.borderMuted : C.border}`,
                color: msg.role === 'assistant' ? C.textSecond : C.textPrime,
                borderTopLeftRadius: msg.role === 'assistant' ? 3 : 11,
                borderTopRightRadius: msg.role === 'user' ? 3 : 11,
              }}>
                <BoldText text={msg.content} />
              </div>
            </div>
          ))}

          {chatLoading && (
            <div style={{ display: 'flex', gap: 10 }}>
              <div style={{
                width: 24, height: 24, borderRadius: 7, flexShrink: 0, marginTop: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: C.violetBg, border: `1px solid ${C.violetBorder}`, color: C.violet,
              }}>
                <IconSparkle />
              </div>
              <div style={{
                padding: '9px 14px', borderRadius: 11, borderTopLeftRadius: 3, fontSize: 13,
                background: C.surface, border: `1px solid ${C.borderMuted}`, color: C.textMuted,
              }}>
                <span className="animate-pulse" style={{ letterSpacing: 3 }}>···</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick prompts */}
        <div style={{
          padding: '0 22px 10px', display: 'flex', flexWrap: 'wrap', gap: 6, flexShrink: 0,
        }}>
          {QUICK_PROMPTS.map(p => (
            <button
              key={p}
              onClick={() => sendMessage(p)}
              disabled={chatLoading}
              className="ap-qp"
              style={{
                fontSize: 11, padding: '5px 11px', borderRadius: 20,
                color: C.textMuted, border: `1px solid ${C.borderMuted}`,
                background: 'transparent', cursor: 'pointer',
                opacity: chatLoading ? 0.3 : 1, transition: 'all 0.15s',
              }}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input */}
        <div style={{
          padding: '0 22px 20px', display: 'flex', gap: 8, alignItems: 'flex-end', flexShrink: 0,
        }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) } }}
            rows={1}
            placeholder="Ask anything about this application…"
            className="ap-ta ap-scrollhide"
            style={{
              flex: 1, borderRadius: 10, padding: '10px 14px',
              fontSize: 13, lineHeight: 1.4, resize: 'none',
              background: C.surface, border: `1px solid ${C.border}`,
              color: C.textPrime, fontFamily: 'inherit',
            }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={chatLoading || !input.trim()}
            style={{
              width: 36, height: 36, borderRadius: 10, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: input.trim() && !chatLoading ? C.tealBg : C.surface,
              border: `1px solid ${input.trim() && !chatLoading ? C.tealBorder : C.borderMuted}`,
              color: input.trim() && !chatLoading ? C.teal : C.textDim,
              cursor: chatLoading || !input.trim() ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <IconSend />
          </button>
        </div>
      </div>
    </div>
  )
}

declare global {
  interface Window {
    electronAPI?: {
      openPath: (path: string) => void
      showItemInFolder: (path: string) => void
    }
  }
}
