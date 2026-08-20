import { useEffect, useRef, useState } from 'react'
import { useOverlayStore } from '../../store/overlayStore'

// Errors that should never auto-dismiss — user must see them
const PERSISTENT_ERRORS = new Set(['DEEPGRAM_MISSING'])
const DEFAULT_DISMISS_MS = 4_000
import { useOverlaySession } from '../../hooks/useOverlaySession'
import { ListeningPill } from './ListeningPill'
import { SuggestionCard } from './SuggestionCard'
import { TranscriptCard } from './TranscriptCard'

export function OverlayShell() {
  useOverlaySession()  // registers IPC listeners
  const { transcriptOpen, error: wsError, setError } = useOverlayStore()
  const [screenshotCount, setScreenshotCount] = useState(0)

  // Auto-dismiss transient errors — persistent ones stay until user acts
  useEffect(() => {
    if (!wsError || PERSISTENT_ERRORS.has(wsError.code)) return
    const id = setTimeout(() => setError(null), DEFAULT_DISMISS_MS)
    return () => clearTimeout(id)
  }, [wsError])
  const [needsMore, setNeedsMore] = useState(false)
  // Content position driven by main process via IPC (arrow key nudges)
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const posRef = useRef<{ x: number; y: number } | null>(null)

  useEffect(() => {
    const api = (window as any).electronAPI?.devcore
    if (!api) return
    const offCount  = api.onScreenshotCount?.((p: { count: number }) => {
      setScreenshotCount(p.count)
      if (p.count === 0) setNeedsMore(false)
    })
    const offResult = api.onScreenshotResult?.((p: { needsMore: boolean }) => {
      setNeedsMore(p.needsMore)
    })
    const offMove = api.onOverlayMove?.((p: { x: number; y: number }) => {
      setPos(p)
      posRef.current = p
      // Update content bounds immediately so cursor hit-test stays accurate
      const el = document.getElementById('overlay-root')
      if (el) {
        const r = el.getBoundingClientRect()
        api.updateContentBounds?.({ x: p.x, y: p.y, width: r.width, height: r.height })
      }
    })
    return () => { offCount?.(); offResult?.(); offMove?.() }
  }, [])

  // Send content bounds to the main process so the cursor-polling loop
  // can toggle setIgnoreMouseEvents without any async IPC round-trip on click.
  // We use ResizeObserver so bounds stay accurate when the card expands/collapses.
  useEffect(() => {
    const el = document.getElementById('overlay-root')
    if (!el) return
    const api = (window as any).electronAPI?.devcore
    const sendBounds = () => {
      const r = el.getBoundingClientRect()
      const p = posRef.current
      api?.updateContentBounds?.({
        x: p ? p.x : r.left,
        y: p ? p.y : r.top,
        width: r.width,
        height: r.height,
      })
    }
    sendBounds()  // initial send
    const ro = new ResizeObserver(sendBounds)
    ro.observe(el)
    return () => ro.disconnect()
  }, [transcriptOpen])  // re-run when transcript panel opens/closes (changes width)

  const handleClearScreenshots = () => {
    const api = (window as any).electronAPI?.devcore
    const sock = (window as any).__devcore_ws  // not available in renderer — use IPC
    // Send clear via WS through main process hotkey equivalent
    // The Ctrl+Shift+X hotkey handles this; here we provide a click target too
    api?.manualAsk?.({ text: '__screenshot_clear__', mode: 'clear', history: [] })
    setScreenshotCount(0)
    setNeedsMore(false)
  }

  // While waiting for main to send the initial position, render off-screen so
  // there's no flash of incorrectly-positioned content.
  const style: React.CSSProperties = pos
    ? { position: 'fixed', left: pos.x, top: pos.y }
    : { position: 'fixed', left: '50%', top: 8, transform: 'translateX(-50%)' }

  return (
    <div id="overlay-root" style={style} className="flex flex-col items-center gap-2 z-50">
      {/* Top pill — always visible */}
      <ListeningPill />

      {/* Critical WS error banner */}
      {wsError && (
        <div style={{
          maxWidth: 360,
          background: 'rgba(15,10,10,0.92)',
          border: '1px solid rgba(248,113,113,0.35)',
          borderRadius: 12,
          padding: '12px 16px',
          backdropFilter: 'blur(16px)',
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#f87171', fontSize: 13 }}>⚠</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11, fontWeight: 700, color: '#f87171', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              {wsError.code.replace(/_/g, ' ')}
            </span>
          </div>
          <p style={{ fontFamily: 'monospace', fontSize: 11, color: 'rgba(226,232,240,0.75)', lineHeight: 1.6, margin: 0 }}>
            {wsError.message}
          </p>
        </div>
      )}

      {/* Screenshot buffer indicator — shown when screenshots are buffered */}
      {screenshotCount > 0 && (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border bg-[rgba(15,20,40,0.75)] border-violet-400/30 backdrop-blur-xl shadow-lg">
          <span className="text-[11px]">📸</span>
          <span className="font-mono text-[11px] text-violet-300 tracking-wider">
            {screenshotCount} screenshot{screenshotCount > 1 ? 's' : ''} buffered
          </span>
          {needsMore && (
            <span className="font-mono text-[10px] text-amber-400 tracking-wider">· scroll & capture more</span>
          )}
          <button
            onClick={handleClearScreenshots}
            className="ml-1 text-[10px] text-white/30 hover:text-white/60 transition-colors font-mono"
            title="Clear buffer (Ctrl+Shift+X)"
          >
            ✕
          </button>
          <span className="font-mono text-[9px] text-white/20 tracking-wider">Ctrl+Shift+S</span>
        </div>
      )}

      {/* Cards row — transcript floats left, suggestion card stays fixed width */}
      <div className="flex items-start gap-2 flex-nowrap">
        {transcriptOpen && <TranscriptCard />}
        <div className="flex-shrink-0">
          <SuggestionCard />
        </div>
      </div>
    </div>
  )
}
