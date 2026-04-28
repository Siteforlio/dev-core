import React from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import { useOverlaySession } from '../../hooks/useOverlaySession'
import { ListeningPill } from './ListeningPill'
import { SuggestionCard } from './SuggestionCard'
import { TranscriptCard } from './TranscriptCard'

export function OverlayShell() {
  useOverlaySession()  // registers IPC listeners
  const { state, suggestion, transcriptOpen } = useOverlayStore()

  if (state === 'idle') return null

  const showCard = suggestion || state === 'thinking'

  return (
    <div className="fixed top-2 left-1/2 -translate-x-1/2 flex items-start gap-2 z-50">
      {transcriptOpen && <TranscriptCard />}
      {showCard ? <SuggestionCard /> : <ListeningPill />}
    </div>
  )
}
