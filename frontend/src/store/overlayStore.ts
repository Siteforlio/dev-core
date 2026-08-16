import { create } from 'zustand'
import type { TranscriptEntry, OverlayPosition, OverlayState, ToolEvent, AssessmentMode } from '../types/devcore'

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
  // Assessment mode state
  assessmentMode: AssessmentMode | null
  toolEvents: ToolEvent[]
  agentThinking: string
  agentGuidance: string
  agentSolution: { code: string; language: string; explanation: string } | null
  activeTool: string | null
  // Reading mode — controls how AI responses are displayed in overlay
  readingMode: 'normal' | 'narrow' | 'large' | 'teleprompter'

  setSessionId:      (id: string | null) => void
  setSessionTitle:   (title: string) => void
  setState:          (s: OverlayState) => void
  appendSuggestion:  (delta: string) => void
  clearSuggestion:   () => void
  addTranscript:     (entry: TranscriptEntry) => void
  setTranscript:     (entries: TranscriptEntry[]) => void
  setLatency:        (ms: number) => void
  setAudioSource:    (src: 'mic' | 'system' | 'both') => void
  setMicDeviceId:    (id: number | null) => void
  setSysDeviceId:    (id: number | null) => void
  setTranscriptOpen: (open: boolean) => void
  setPosition:       (pos: OverlayPosition) => void
  setError:          (err: { code: string; message: string } | null) => void
  setAssessmentMode: (mode: AssessmentMode | null) => void
  addToolEvent:      (event: ToolEvent) => void
  clearToolEvents:   () => void
  setAgentThinking:  (text: string) => void
  setAgentGuidance:  (text: string) => void
  setAgentSolution:  (s: { code: string; language: string; explanation: string } | null) => void
  setActiveTool:     (tool: string | null) => void
  setReadingMode:    (mode: 'normal' | 'narrow' | 'large' | 'teleprompter') => void
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
  assessmentMode: null,
  toolEvents: [],
  agentThinking: '',
  agentGuidance: '',
  agentSolution: null,
  activeTool: null,
  readingMode: 'normal',

  setSessionId:      (id)   => set({ sessionId: id }),
  setSessionTitle:   (title)=> set({ sessionTitle: title }),
  setState:          (s)    => set({ state: s }),
  appendSuggestion:  (d)    => set((st) => ({ suggestion: st.suggestion + d })),
  clearSuggestion:   ()     => set({ suggestion: '' }),
  addTranscript:     (e)    => set((st) => ({ transcript: [...st.transcript.slice(-19), e] })),
  setTranscript:     (entries) => set({ transcript: entries }),
  setLatency:        (ms)   => set({ latencyMs: ms }),
  setAudioSource:    (src)  => set({ audioSource: src }),
  setMicDeviceId:    (id)   => set({ micDeviceId: id }),
  setSysDeviceId:    (id)   => set({ sysDeviceId: id }),
  setTranscriptOpen: (o)    => set({ transcriptOpen: o }),
  setPosition:       (p)    => set({ position: p }),
  setError:          (e)    => set({ error: e }),
  setAssessmentMode: (m)    => set({ assessmentMode: m }),
  addToolEvent:      (ev)   => set((st) => ({ toolEvents: [...st.toolEvents.slice(-99), ev], activeTool: ev.tool })),
  clearToolEvents:   ()     => set({ toolEvents: [], activeTool: null }),
  setAgentThinking:  (t)    => set({ agentThinking: t }),
  setAgentGuidance:  (t)    => set({ agentGuidance: t }),
  setAgentSolution:  (s)    => set({ agentSolution: s }),
  setActiveTool:     (t)    => set({ activeTool: t }),
  setReadingMode:    (m)    => set({ readingMode: m }),
}))
