import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../store/authStore'

const MIN_DISPLAY_MS = 4200

const QUOTES = [
  { mod: 'Job Hunter',     color: '#22d3ee', text: 'Success is where preparation meets opportunity.',                         author: 'Seneca' },
  { mod: 'Interview Prep', color: '#34d399', text: "It's not cheating if you have prepared and practiced.",                   author: 'DevCore Philosophy' },
  { mod: 'Screen Overlay', color: '#38bdf8', text: 'The best tool becomes invisible — and indispensable.',                    author: 'Design Principle' },
  { mod: 'Job Hunter',     color: '#22d3ee', text: 'Your next opportunity is one application away. Make it count.',           author: 'Every great hire, ever' },
  { mod: 'Interview Prep', color: '#34d399', text: 'By failing to prepare, you are preparing to fail.',                       author: 'Benjamin Franklin' },
  { mod: 'Screen Overlay', color: '#38bdf8', text: 'Intelligence is the ability to adapt to change.',                         author: 'Stephen Hawking' },
  { mod: 'Job Hunter',     color: '#22d3ee', text: 'Apply strategically. Campaigns win — not desperate applications.',        author: 'Career Strategy' },
  { mod: 'Interview Prep', color: '#34d399', text: 'Rehearse until the nerves become fuel. Then perform.',                    author: 'DevCore' },
  { mod: 'Screen Overlay', color: '#38bdf8', text: 'Every expert was once a beginner with the right tools in their hands.',   author: 'Unknown' },
]

const STEPS = [
  [8,   'Loading modules\u2026'],
  [20,  'Checking session\u2026'],
  [42,  'Validating token\u2026'],
  [62,  'Refreshing credentials\u2026'],
  [81,  'Syncing configuration\u2026'],
  [95,  'Preparing workspace\u2026'],
  [100, 'Ready.'],
] as const

const MOD_IDS: Record<string, string> = {
  'Job Hunter':     'm-job',
  'Interview Prep': 'm-interview',
  'Screen Overlay': 'm-overlay',
}

interface Props {
  onDone: (authenticated: boolean) => void
}

export default function SplashScreen({ onDone }: Props) {
  const { accessToken, refreshToken, setAccessToken, clearAuth } = useAuthStore.getState()

  const canvasRef    = useRef<HTMLCanvasElement>(null)
  const animFrameRef = useRef<number>(0)
  const typeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stepTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [offline,    setOffline]    = useState(!navigator.onLine)
  const [pct,        setPct]        = useState(0)
  const [statusText, setStatusText] = useState('Initializing\u2026')
  const [statusDone, setStatusDone] = useState(false)

  /* Quote state */
  const [qModVisible,    setQModVisible]    = useState(false)
  const [qAuthorVisible, setQAuthorVisible] = useState(false)
  const [qColor,         setQColor]         = useState('#22d3ee')
  const [qModLabel,      setQModLabel]      = useState('')
  const [qAuthorText,    setQAuthorText]    = useState('')
  const [activeMod,      setActiveMod]      = useState('')
  const qTextRef = useRef<HTMLDivElement>(null)
  const qiRef    = useRef(0)

  /* ── Particle canvas ── */
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    let W = 0, H = 0

    const pts: { x: number; y: number; vx: number; vy: number; r: number; a: number }[] = []

    const resize = () => {
      W = canvas.width  = window.innerWidth
      H = canvas.height = window.innerHeight
    }
    window.addEventListener('resize', resize)
    resize()

    for (let i = 0; i < 80; i++) {
      pts.push({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - .5) * .25, vy: (Math.random() - .5) * .25,
        r: Math.random() * 1.4 + .4,    a: Math.random() * .45 + .1,
      })
    }

    const draw = () => {
      ctx.clearRect(0, 0, W, H)
      const g = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, Math.min(W, H) * .5)
      g.addColorStop(0, 'rgba(34,211,238,0.045)')
      g.addColorStop(1, 'transparent')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, W, H)

      for (const p of pts) {
        p.x += p.vx; p.y += p.vy
        if (p.x < 0 || p.x > W || p.y < 0 || p.y > H) {
          p.x = Math.random() * W; p.y = Math.random() * H
        }
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(34,211,238,${p.a})`
        ctx.fill()
      }
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y
          const d = Math.sqrt(dx * dx + dy * dy)
          if (d < 120) {
            ctx.beginPath()
            ctx.moveTo(pts[i].x, pts[i].y)
            ctx.lineTo(pts[j].x, pts[j].y)
            ctx.strokeStyle = `rgba(34,211,238,${0.07 * (1 - d / 120)})`
            ctx.lineWidth = .5
            ctx.stroke()
          }
        }
      }
      animFrameRef.current = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animFrameRef.current)
    }
  }, [])

  /* ── Offline detection ── */
  useEffect(() => {
    const goOnline  = () => setOffline(false)
    const goOffline = () => setOffline(true)
    window.addEventListener('online',  goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online',  goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])

  /* ── Quote typewriter ── */
  const typeQuote = (qi: number) => {
    const q = QUOTES[qi % QUOTES.length]
    setQModVisible(false)
    setQAuthorVisible(false)
    setQAuthorText('')
    if (qTextRef.current) qTextRef.current.textContent = ''

    setTimeout(() => {
      setQModLabel(q.mod.toUpperCase())
      setQColor(q.color)
      setActiveMod(q.mod)
      setQModVisible(true)
    }, 150)

    const el = qTextRef.current
    if (!el) return
    el.textContent = ''

    /* cursor node */
    const cursor = document.createElement('span')
    cursor.style.cssText = 'display:inline-block;width:2px;height:1.1em;background:#22d3ee;margin-left:2px;vertical-align:middle;animation:q-blink 0.7s step-end infinite;box-shadow:0 0 8px rgba(34,211,238,0.8)'
    el.appendChild(cursor)

    let i = 0
    typeTimerRef.current = setInterval(() => {
      if (i < q.text.length) {
        el.insertBefore(document.createTextNode(q.text[i]), cursor)
        i++
      } else {
        if (typeTimerRef.current) clearInterval(typeTimerRef.current)
        cursor.remove()
        setTimeout(() => {
          setQAuthorText('\u2014 ' + q.author)
          setQAuthorVisible(true)
          setTimeout(() => {
            qiRef.current++
            setQModVisible(false)
            setQAuthorVisible(false)
            setTimeout(() => typeQuote(qiRef.current), 400)
          }, 2600)
        }, 300)
      }
    }, 30)
  }

  /* ── Progress bar ── */
  const runProgress = (stepIndex: number) => {
    if (stepIndex >= STEPS.length) return
    const [p, label] = STEPS[stepIndex]
    setPct(p)
    setStatusText(label)
    if (stepIndex < STEPS.length - 1) {
      stepTimerRef.current = setTimeout(
        () => runProgress(stepIndex + 1),
        560 + Math.random() * 420,
      )
    } else {
      setTimeout(() => setStatusDone(true), 350)
    }
  }

  /* ── Auth check ── */
  useEffect(() => {
    const started = Date.now()
    const wait = (ms: number) => new Promise<void>(r => setTimeout(r, Math.max(0, ms)))

    async function checkAuth() {
      // Start animations
      setTimeout(() => { runProgress(0); typeQuote(0) }, 1800)

      // No stored session at all
      if (!refreshToken && !accessToken) {
        await wait(MIN_DISPLAY_MS - (Date.now() - started))
        onDone(false)
        return
      }

      // Try to refresh the token
      try {
        const res = await fetch('http://localhost:8000/api/v1/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
        if (res.ok) {
          const body = await res.json()
          setAccessToken(body.data.access_token)
          await wait(MIN_DISPLAY_MS - (Date.now() - started))
          onDone(true)
        } else {
          // Expired or invalid — but if we have an accessToken still try (offline case)
          if (accessToken) {
            await wait(MIN_DISPLAY_MS - (Date.now() - started))
            onDone(true)
          } else {
            clearAuth()
            await wait(MIN_DISPLAY_MS - (Date.now() - started))
            onDone(false)
          }
        }
      } catch {
        // Network error — trust existing token if present
        if (accessToken) {
          await wait(MIN_DISPLAY_MS - (Date.now() - started))
          onDone(true)
        } else {
          clearAuth()
          await wait(MIN_DISPLAY_MS - (Date.now() - started))
          onDone(false)
        }
      }
    }

    checkAuth()

    return () => {
      if (typeTimerRef.current) clearInterval(typeTimerRef.current)
      if (stepTimerRef.current) clearTimeout(stepTimerRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#020810', overflow: 'hidden', zIndex: 9999 }}>
      <style>{`
        @keyframes q-blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes sp-scan { 0%{top:-2px;opacity:0} 3%{opacity:1} 97%{opacity:1} 100%{top:100vh;opacity:0} }
        @keyframes sp-glow { 0%,100%{transform:scale(1);opacity:1} 50%{transform:scale(1.18);opacity:0.7} }
        @keyframes sp-logo { from{opacity:0;transform:scale(0.7) translateY(20px);filter:blur(12px)} to{opacity:1;transform:scale(1) translateY(0);filter:blur(0)} }
        @keyframes sp-brand { from{opacity:0;letter-spacing:0.5em;filter:blur(8px)} to{opacity:1;letter-spacing:0.18em;filter:blur(0)} }
        @keyframes sp-up { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

      {/* Particle canvas */}
      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, zIndex: 0 }} />

      {/* Grid overlay */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'none',
        backgroundImage: 'linear-gradient(rgba(34,211,238,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,0.03) 1px,transparent 1px)',
        backgroundSize: '60px 60px',
      }} />

      {/* Scanline */}
      <div style={{
        position: 'absolute', left: 0, right: 0, height: '2px', zIndex: 2, pointerEvents: 'none',
        background: 'linear-gradient(90deg,transparent,rgba(34,211,238,0.15) 20%,rgba(34,211,238,0.65) 50%,rgba(34,211,238,0.15) 80%,transparent)',
        boxShadow: '0 0 24px rgba(34,211,238,0.4)',
        animation: 'sp-scan 7s 0.5s infinite linear',
      }} />

      {/* Corner TL */}
      <div style={{ position: 'absolute', top: 24, left: 24, zIndex: 5, pointerEvents: 'none', opacity: 0.35, animation: 'sp-up 0.8s 0.5s both' }}>
        <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
          <path d="M0 52L0 0L52 0" stroke="#22d3ee" strokeWidth="1.5"/>
        </svg>
      </div>
      {/* Corner BR */}
      <div style={{ position: 'absolute', bottom: 24, right: 24, zIndex: 5, pointerEvents: 'none', opacity: 0.35, transform: 'rotate(180deg)', animation: 'sp-up 0.8s 0.5s both' }}>
        <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
          <path d="M0 52L0 0L52 0" stroke="#22d3ee" strokeWidth="1.5"/>
        </svg>
      </div>

      {/* Version */}
      <div style={{ position: 'absolute', top: 28, right: 32, zIndex: 20, fontFamily: 'monospace', fontSize: '9px', letterSpacing: '0.2em', color: 'rgba(34,211,238,0.3)', animation: 'sp-up 0.6s 1s both' }}>
        v1.0
      </div>

      {/* Offline banner */}
      {offline && (
        <div style={{
          position: 'absolute', top: 28, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.25)',
          borderRadius: '8px', padding: '8px 20px', fontFamily: 'monospace', fontSize: '10px',
          letterSpacing: '0.14em', color: '#fbbf24', display: 'flex', alignItems: 'center',
          gap: '8px', zIndex: 30, whiteSpace: 'nowrap',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="1" y1="1" x2="23" y2="23"/>
            <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55M5 12.55a10.94 10.94 0 0 1 5.17-2.39M10.71 5.05A16 16 0 0 1 22.56 9M1.42 9a15.91 15.91 0 0 1 4.7-2.88M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01"/>
          </svg>
          <span>No connection detected — retrying…</span>
        </div>
      )}

      {/* Main content */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>

        {/* Logo */}
        <div style={{ position: 'relative', marginBottom: '28px', animation: 'sp-logo 1s 0.3s both cubic-bezier(0.16,1,0.3,1)' }}>
          <div style={{
            position: 'absolute', inset: '-40px', borderRadius: '50%',
            background: 'radial-gradient(circle,rgba(34,211,238,0.15) 0%,transparent 70%)',
            animation: 'sp-glow 3s ease-in-out infinite',
          }} />
          <svg width="90" height="90" viewBox="0 0 90 90" fill="none" style={{ filter: 'drop-shadow(0 0 20px rgba(34,211,238,0.7)) drop-shadow(0 0 40px rgba(34,211,238,0.3))', display: 'block' }}>
            <polygon points="45,4 81,24 81,66 45,86 9,66 9,24" fill="rgba(34,211,238,0.06)" stroke="rgba(34,211,238,0.7)" strokeWidth="1.5"/>
            <polygon points="45,14 72,29.5 72,60.5 45,76 18,60.5 18,29.5" fill="none" stroke="rgba(34,211,238,0.2)" strokeWidth="1"/>
            <circle cx="45" cy="45" r="10" fill="none" stroke="#22d3ee" strokeWidth="1.8"/>
            <circle cx="45" cy="45" r="4" fill="#22d3ee"/>
            <line x1="45" y1="35" x2="45" y2="25" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="round"/>
            <line x1="45" y1="55" x2="45" y2="65" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="round"/>
            <line x1="36.3" y1="40" x2="27.8" y2="35" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="round"/>
            <line x1="53.7" y1="50" x2="62.2" y2="55" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="round"/>
            <line x1="36.3" y1="50" x2="27.8" y2="55" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="round"/>
            <line x1="53.7" y1="40" x2="62.2" y2="35" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="round"/>
            <circle cx="45" cy="23" r="2.5" fill="rgba(34,211,238,0.6)"/>
            <circle cx="45" cy="67" r="2.5" fill="rgba(34,211,238,0.6)"/>
            <circle cx="26.5" cy="33.5" r="2.5" fill="rgba(34,211,238,0.6)"/>
            <circle cx="63.5" cy="56.5" r="2.5" fill="rgba(34,211,238,0.6)"/>
            <circle cx="26.5" cy="56.5" r="2.5" fill="rgba(34,211,238,0.6)"/>
            <circle cx="63.5" cy="33.5" r="2.5" fill="rgba(34,211,238,0.6)"/>
          </svg>
        </div>

        {/* Brand */}
        <div style={{
          fontFamily: '"Orbitron", monospace', fontWeight: 900,
          fontSize: 'clamp(36px,6vw,62px)', letterSpacing: '0.18em',
          color: 'rgba(226,232,240,0.97)', textShadow: '0 0 60px rgba(34,211,238,0.25)',
          animation: 'sp-brand 0.9s 0.9s both cubic-bezier(0.16,1,0.3,1)', marginBottom: '6px',
        }}>
          DEVCORE
        </div>
        <div style={{
          fontSize: '10px', letterSpacing: '0.32em', color: 'rgba(34,211,238,0.5)',
          textTransform: 'uppercase', textAlign: 'center', fontFamily: 'monospace',
          animation: 'sp-up 0.6s 1.5s both', marginBottom: '52px',
          display: 'flex', alignItems: 'center', gap: '14px',
        }}>
          <span style={{ height: '1px', width: '32px', background: 'rgba(34,211,238,0.3)', display: 'block' }} />
          interview intelligence platform
          <span style={{ height: '1px', width: '32px', background: 'rgba(34,211,238,0.3)', display: 'block' }} />
        </div>

        {/* Quote block */}
        <div style={{ maxWidth: '580px', minHeight: '110px', textAlign: 'center', padding: '0 32px', animation: 'sp-up 0.5s 1.8s both' }}>
          <div style={{
            fontSize: '9px', fontWeight: 700, letterSpacing: '0.28em', textTransform: 'uppercase',
            marginBottom: '18px', display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: '10px', fontFamily: 'monospace',
            opacity: qModVisible ? 1 : 0, transition: 'opacity 0.4s',
          }}>
            <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: qColor, boxShadow: `0 0 8px ${qColor}`, flexShrink: 0 }} />
            <span>{qModLabel}</span>
          </div>
          <div
            ref={qTextRef}
            style={{
              fontSize: 'clamp(14px,2.2vw,19px)', lineHeight: 1.7,
              color: 'rgba(226,232,240,0.88)', fontStyle: 'italic',
              letterSpacing: '0.02em', minHeight: '64px', fontFamily: 'monospace',
            }}
          />
          <div style={{
            marginTop: '14px', fontSize: '11px', letterSpacing: '0.14em',
            color: 'rgba(100,116,139,0.6)', fontFamily: 'monospace',
            opacity: qAuthorVisible ? 1 : 0, transition: 'opacity 0.6s',
          }}>
            {qAuthorText}
          </div>
        </div>

        {/* Module indicators */}
        <div style={{ display: 'flex', gap: '32px', marginTop: '52px', animation: 'sp-up 0.6s 2s both' }}>
          {[
            {
              id: 'm-job', label: 'Job Hunter',
              icon: (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.6" strokeLinecap="round">
                  <rect x="2" y="7" width="20" height="14" rx="2"/>
                  <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
                  <line x1="12" y1="12" x2="12" y2="16"/>
                  <line x1="10" y1="14" x2="14" y2="14"/>
                </svg>
              ),
            },
            {
              id: 'm-interview', label: 'Interview Prep',
              icon: (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.6" strokeLinecap="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              ),
            },
            {
              id: 'm-overlay', label: 'Screen Overlay',
              icon: (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.6" strokeLinecap="round">
                  <rect x="2" y="3" width="20" height="14" rx="2"/>
                  <path d="M8 21h8M12 17v4"/>
                  <circle cx="17" cy="8" r="1.5" fill="#22d3ee" stroke="none"/>
                </svg>
              ),
            },
          ].map(({ id, label, icon }) => {
            const isActive = MOD_IDS[activeMod] === id
            return (
              <div key={id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', opacity: isActive ? 1 : 0.2, transition: 'all 0.5s' }}>
                <div style={{
                  width: '38px', height: '38px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  border: `1px solid ${isActive ? 'rgba(34,211,238,0.4)' : 'rgba(34,211,238,0.15)'}`,
                  background: isActive ? 'rgba(34,211,238,0.1)' : 'rgba(34,211,238,0.05)',
                  boxShadow: isActive ? '0 0 16px rgba(34,211,238,0.15)' : 'none',
                  transition: 'all 0.5s',
                }}>
                  {icon}
                </div>
                <div style={{
                  fontSize: '8px', fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase',
                  fontFamily: 'monospace', transition: 'color 0.5s',
                  color: isActive ? '#22d3ee' : 'rgba(100,116,139,0.5)',
                }}>
                  {label}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 20, padding: '0 0 36px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', animation: 'sp-up 0.5s 2.2s both' }}>
        <div style={{
          fontSize: '9px', letterSpacing: '0.2em', textTransform: 'uppercase', fontFamily: 'monospace',
          color: statusDone ? 'rgba(52,211,153,0.8)' : 'rgba(100,116,139,0.45)',
          transition: 'color 0.4s',
        }}>
          {statusDone ? '\u2713 Ready' : statusText}
        </div>
        <div style={{ width: '220px', height: '1px', background: 'rgba(255,255,255,0.06)', borderRadius: '1px', overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${pct}%`,
            background: 'linear-gradient(90deg,rgba(34,211,238,0.4),#22d3ee)',
            boxShadow: '0 0 8px rgba(34,211,238,0.6)',
            transition: 'width 0.5s ease',
          }} />
        </div>
      </div>
    </div>
  )
}
