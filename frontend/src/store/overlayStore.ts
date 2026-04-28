import { create } from 'zustand'
import type { TranscriptEntry, OverlayPosition, OverlayState } from '../types/devcore'

interface OverlayStore {
  sessionId: string | null
  state: OverlayState
  suggestion: string
  transcript: TranscriptEntry[]
  latencyMs: number
  audioSource: 'mic' | 'system' | 'both'
  transcriptOpen: boolean
  position: OverlayPosition
  error: { code: string; message: string } | null

  setSessionId:      (id: string | null) => void
  setState:          (s: OverlayState) => void
  appendSuggestion:  (delta: string) => void
  clearSuggestion:   () => void
  addTranscript:     (entry: TranscriptEntry) => void
  setLatency:        (ms: number) => void
  setAudioSource:    (src: 'mic' | 'system' | 'both') => void
  setTranscriptOpen: (open: boolean) => void
  setPosition:       (pos: OverlayPosition) => void
  setError:          (err: { code: string; message: string } | null) => void
}

export const useOverlayStore = create<OverlayStore>((set) => ({
  sessionId: null,
  state: 'idle',
  suggestion: '',
  transcript: [],
  latencyMs: 0,
  audioSource: 'both',
  transcriptOpen: false,
  position: 'top-center',
  error: null,

  setSessionId:      (id) => set({ sessionId: id }),
  setState:          (s)  => set({ state: s }),
  appendSuggestion:  (d)  => set((st) => ({ suggestion: st.suggestion + d })),
  clearSuggestion:   ()   => set({ suggestion: '' }),
  addTranscript:     (e)  => set((st) => ({ transcript: [...st.transcript.slice(-19), e] })),
  setLatency:        (ms) => set({ latencyMs: ms }),
  setAudioSource:    (src)=> set({ audioSource: src }),
  setTranscriptOpen: (o)  => set({ transcriptOpen: o }),
  setPosition:       (p)  => set({ position: p }),
  setError:          (e)  => set({ error: e }),
}))
