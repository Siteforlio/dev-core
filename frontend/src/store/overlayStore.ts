import { create } from 'zustand'
import type { TranscriptEntry, OverlayPosition, OverlayState } from '../types/devcore'

export interface AudioDevice { id: number; name: string }

interface OverlayStore {
  sessionId: string | null
  sessionTitle: string
  state: OverlayState
  suggestion: string
  transcript: TranscriptEntry[]
  latencyMs: number
  audioSource: 'mic' | 'system' | 'both'
  micDeviceId: number | null
  sysDeviceId: number | null
  transcriptOpen: boolean
  position: OverlayPosition
  error: { code: string; message: string } | null

  setSessionId:      (id: string | null) => void
  setSessionTitle:   (title: string) => void
  setState:          (s: OverlayState) => void
  appendSuggestion:  (delta: string) => void
  clearSuggestion:   () => void
  addTranscript:     (entry: TranscriptEntry) => void
  setLatency:        (ms: number) => void
  setAudioSource:    (src: 'mic' | 'system' | 'both') => void
  setMicDeviceId:    (id: number | null) => void
  setSysDeviceId:    (id: number | null) => void
  setTranscriptOpen: (open: boolean) => void
  setPosition:       (pos: OverlayPosition) => void
  setError:          (err: { code: string; message: string } | null) => void
}

export const useOverlayStore = create<OverlayStore>((set) => ({
  sessionId: null,
  sessionTitle: 'Untitled',
  state: 'idle',
  suggestion: '',
  transcript: [],
  latencyMs: 0,
  audioSource: 'both',
  micDeviceId: null,
  sysDeviceId: null,
  transcriptOpen: false,
  position: 'top-center',
  error: null,

  setSessionId:      (id) => set({ sessionId: id }),
  setSessionTitle:   (title) => set({ sessionTitle: title }),
  setState:          (s)  => set({ state: s }),
  appendSuggestion:  (d)  => set((st) => ({ suggestion: st.suggestion + d })),
  clearSuggestion:   ()   => set({ suggestion: '' }),
  addTranscript:     (e)  => set((st) => ({ transcript: [...st.transcript.slice(-19), e] })),
  setLatency:        (ms) => set({ latencyMs: ms }),
  setAudioSource:    (src)=> set({ audioSource: src }),
  setMicDeviceId:    (id) => set({ micDeviceId: id }),
  setSysDeviceId:    (id) => set({ sysDeviceId: id }),
  setTranscriptOpen: (o)  => set({ transcriptOpen: o }),
  setPosition:       (p)  => set({ position: p }),
  setError:          (e)  => set({ error: e }),
}))
