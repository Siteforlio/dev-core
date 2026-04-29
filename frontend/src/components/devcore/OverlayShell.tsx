import { useEffect } from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import { useOverlaySession } from '../../hooks/useOverlaySession'
import { ListeningPill } from './ListeningPill'
import { SuggestionCard } from './SuggestionCard'
import { TranscriptCard } from './TranscriptCard'

export function OverlayShell() {
  useOverlaySession()  // registers IPC listeners
  const { transcriptOpen } = useOverlayStore()

  // Send content bounds to the main process so the cursor-polling loop
  // can toggle setIgnoreMouseEvents without any async IPC round-trip on click.
  // We use ResizeObserver so bounds stay accurate when the card expands/collapses.
  useEffect(() => {
    const el = document.getElementById('overlay-root')
    if (!el) return
    const api = (window as any).electronAPI?.devcore
    const sendBounds = () => {
      const r = el.getBoundingClientRect()
      api?.updateContentBounds?.({ x: r.left, y: r.top, width: r.width, height: r.height })
    }
    sendBounds()  // initial send
    const ro = new ResizeObserver(sendBounds)
    ro.observe(el)
    return () => ro.disconnect()
  }, [transcriptOpen])  // re-run when transcript panel opens/closes (changes width)

  return (
    <div id="overlay-root" className="fixed top-2 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 z-50">
      {/* Top pill — always visible */}
      <ListeningPill />
      {/* Cards row */}
      <div className="flex items-start gap-2">
        {transcriptOpen && <TranscriptCard />}
        <SuggestionCard />
      </div>
    </div>
  )
}
