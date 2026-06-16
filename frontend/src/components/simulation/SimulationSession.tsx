// frontend/src/components/simulation/SimulationSession.tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { useSimulationStore } from '../../store/simulationStore'
import { useSimulationSession } from '../../hooks/useSimulationSession'
import type { SimDebriefData } from '../../hooks/useSimulationSession'
import FeedbackStrip from '../interview/FeedbackStrip'
import type { EmotionState } from '../interview/FeedbackStrip'
import AIPip from './AIPip'
import SimControls from './SimControls'
import SimToolOverlay from './SimToolOverlay'
import SimDevicePicker from './SimDevicePicker'

interface Props {
  onDebrief: (data: SimDebriefData) => void
  onEnd: () => void
}

const EMOTION_COLOR: Record<string, string> = {
  confident: '#4ade80',
  engaged:   '#22d3ee',
  neutral:   '#94a3b8',
  uncertain: '#fbbf24',
  nervous:   '#f87171',
}

const SIM_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&display=swap');

  @keyframes sim-speak    { 0%,100%{transform:scale(1);opacity:.8} 50%{transform:scale(1.1);opacity:.2} }
  @keyframes sim-wwave    { 0%,100%{transform:scaleY(.3);opacity:.5} 50%{transform:scaleY(1);opacity:1} }
  @keyframes sim-tdot     { 0%,80%,100%{transform:translateY(0);opacity:.4} 40%{transform:translateY(-6px);opacity:1} }
  @keyframes sim-pulse-chip { 0%,100%{opacity:1} 50%{opacity:.55} }
  @keyframes sim-spin     { to{transform:rotate(360deg)} }
  @keyframes sim-emp      { 0%,100%{opacity:1} 50%{opacity:.3} }
  @keyframes sim-banner-in { from{transform:translateY(-100%);opacity:0} to{transform:translateY(0);opacity:1} }
  @keyframes sim-load-pulse { 0%,100%{opacity:0.4} 50%{opacity:1} }

  .sim-speaking .sim-speak-ring  { animation: sim-speak 1.6s ease-in-out infinite; }
  .sim-speaking .sim-speak-ring2 { animation: sim-speak 1.6s ease-in-out 0.4s infinite; }
  .sim-speaking .sim-wbar        { animation: sim-wwave 1.3s ease-in-out infinite; }
`

export default function SimulationSession({ onDebrief, onEnd }: Props) {
  const { activeSimSessionId, timeBudgetSeconds, scenarioType } = useSimulationStore()

  const [input, setInput] = useState('')
  const [micMuted, setMicMuted] = useState(false)
  const [textOpen, setTextOpen] = useState(false)
  const [faceActive, setFaceActive] = useState(false)
  const [emotion, setEmotion] = useState<EmotionState | null>(null)
  const [selectedMicId, setSelectedMicId] = useState<string | undefined>(undefined)
  const [selectedSpeakerId, setSelectedSpeakerId] = useState<string | undefined>(undefined)
  const [showDevices, setShowDevices] = useState(false)

  const userCamRef = useRef<HTMLVideoElement>(null)
  const userStreamRef = useRef<MediaStream | null>(null)
  const transcriptRef = useRef<HTMLDivElement>(null)

  // Open camera on mount, close on unmount
  useEffect(() => {
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'user' } })
      .then((stream) => {
        userStreamRef.current = stream
        if (userCamRef.current) userCamRef.current.srcObject = stream
      })
      .catch(() => {})
    return () => {
      userStreamRef.current?.getTracks().forEach((t) => t.stop())
      userStreamRef.current = null
    }
  }, [])

  const {
    turns, remaining, hardCutoff, cutoffMsg,
    sessionEnded, aiThinking, aiSpeaking, activeTool,
    wsReady, isRecording,
    sendText, endSession,
  } = useSimulationSession(onDebrief, onEnd, { micMuted, selectedMicId, selectedSpeakerId })

  // Auto-scroll transcript to bottom when new turns arrive
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [turns])

  const timerBarColor = remaining == null ? '#22d3ee'
    : remaining < 10 ? '#ef4444'
    : remaining < (timeBudgetSeconds ?? Infinity) * 0.2 ? '#fbbf24'
    : '#22d3ee'

  const timerPct = remaining == null || timeBudgetSeconds == null
    ? 100
    : Math.max(0, (remaining / timeBudgetSeconds) * 100)

  const disabled = sessionEnded || hardCutoff || aiThinking

  const handleSubmit = useCallback(() => {
    sendText(input)
    setInput('')
  }, [input, sendText])

  return (
    <div style={{
      position: 'relative', width: '100%', height: '100%',
      background: '#05090f', color: '#e2e8f0',
      fontFamily: "'DM Mono', monospace",
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <style>{SIM_CSS}</style>

      {/* Title bar */}
      <div style={{
        background: 'rgba(4,7,13,0.98)', padding: '9px 16px',
        display: 'flex', alignItems: 'center', gap: 8,
        borderBottom: '1px solid rgba(255,255,255,0.04)', flexShrink: 0, zIndex: 10,
      }}>
        {(['#ff5f57', '#febc2e', '#28c840'] as const).map((c) => (
          <div key={c} style={{ width: 9, height: 9, borderRadius: '50%', background: c, opacity: 0.8 }} />
        ))}
        <div style={{ marginLeft: 8, display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
          <span style={{ fontSize: '0.68rem', color: '#334155', letterSpacing: '0.05em' }}>
            Interview Simulation
          </span>
          {scenarioType && (
            <span style={{
              fontSize: '0.6rem', color: '#22d3ee', letterSpacing: '0.1em',
              textTransform: 'uppercase', background: 'rgba(34,211,238,0.06)',
              border: '1px solid rgba(34,211,238,0.12)', borderRadius: 4, padding: '2px 7px',
            }}>
              {scenarioType}
            </span>
          )}
          <span style={{ fontSize: '0.6rem', color: '#1e293b', marginLeft: 'auto', fontVariantNumeric: 'tabular-nums' }}>
            {activeSimSessionId?.slice(0, 8)}
          </span>
        </div>
      </div>

      {/* Timer bar */}
      {timeBudgetSeconds != null && (
        <div style={{ height: 2, background: 'rgba(255,255,255,0.05)', flexShrink: 0 }}>
          <div style={{
            height: '100%', width: `${timerPct}%`,
            background: timerBarColor, boxShadow: `0 0 8px ${timerBarColor}`,
            transition: 'width 1s linear, background 0.5s',
          }} />
        </div>
      )}

      {/* Loading overlay — shown until AI opening message arrives */}
      {!wsReady && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 100,
          background: 'radial-gradient(ellipse at 50% 40%, #0a1628 0%, #05090f 70%)',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 28,
        }}>
          {/* Rings */}
          <div style={{ position: 'relative', width: 72, height: 72 }}>
            <div style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              border: '1px solid rgba(34,211,238,0.08)',
              animation: 'sim-load-pulse 2s ease-in-out infinite',
            }} />
            <div style={{
              position: 'absolute', inset: 8, borderRadius: '50%',
              border: '1.5px solid rgba(34,211,238,0.12)',
              animation: 'sim-load-pulse 2s ease-in-out 0.3s infinite',
            }} />
            <div style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              border: '2px solid transparent',
              borderTopColor: '#22d3ee',
              animation: 'sim-spin 1.2s linear infinite',
            }} />
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.78rem', color: '#64748b', letterSpacing: '0.08em', marginBottom: 8 }}>
              {aiThinking ? 'Interviewer is preparing' : 'Connecting'}
            </div>
            <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
              {[0, 1, 2].map((i) => (
                <div key={i} style={{
                  width: 4, height: 4, borderRadius: '50%', background: '#22d3ee',
                  animation: `sim-tdot 1.2s ease-in-out ${i * 0.2}s infinite`,
                }} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Video area */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: '#04080f' }}>

        {/* Scanline */}
        <div style={{
          position: 'absolute', inset: 0, zIndex: 50, pointerEvents: 'none',
          backgroundImage: 'repeating-linear-gradient(0deg,transparent 0px,transparent 3px,rgba(0,0,0,0.07) 3px,rgba(0,0,0,0.07) 4px)',
          opacity: 0.5,
        }} />

        {/* User camera feed */}
        <video
          ref={userCamRef}
          autoPlay muted playsInline
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
        />
        {/* Bottom fade overlay */}
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '35%', background: 'linear-gradient(to top, rgba(3,6,12,0.85), transparent)', zIndex: 2 }} />

        <AIPip speaking={aiSpeaking} thinking={aiThinking} />

        {/* Emotion strip — real data from FeedbackStrip */}
        {faceActive && (
          <div style={{
            position: 'absolute', top: 16, left: 16,
            background: 'rgba(4,8,16,0.75)', backdropFilter: 'blur(12px)',
            border: `1px solid ${emotion ? 'rgba(74,222,128,0.15)' : 'rgba(255,255,255,0.06)'}`,
            borderRadius: 8, padding: '7px 12px',
            display: 'flex', alignItems: 'center', gap: 10,
            transition: 'all 0.3s', pointerEvents: 'none', zIndex: 8,
          }}>
            {emotion ? (
              <>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: EMOTION_COLOR[emotion.emotion] ?? '#4ade80',
                  animation: 'sim-emp 2s ease-in-out infinite', flexShrink: 0,
                }} />
                <div>
                  <div style={{ fontSize: '0.65rem', fontWeight: 500, color: EMOTION_COLOR[emotion.emotion] ?? '#4ade80', letterSpacing: '0.04em' }}>
                    {emotion.emotion.toUpperCase()}
                  </div>
                  <div style={{ fontSize: '0.57rem', color: 'rgba(255,255,255,0.25)' }}>
                    {emotion.eye_contact ? 'Eye contact ✓' : 'Look at camera'}
                  </div>
                </div>
                <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)' }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <div style={{ fontSize: '0.54rem', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Confidence</div>
                  <div style={{ fontSize: '0.65rem', fontWeight: 500, color: 'rgba(255,255,255,0.75)' }}>
                    {Math.round(emotion.confidence * 100)}%
                  </div>
                </div>
              </>
            ) : (
              <>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#475569', animation: 'sim-spin 1.5s linear infinite', flexShrink: 0 }} />
                <div style={{ fontSize: '0.63rem', color: '#475569' }}>Analyzing face…</div>
              </>
            )}
          </div>
        )}
        <FeedbackStrip
          active={!sessionEnded}
          enabled={faceActive}
          sharedStream={userStreamRef.current}
          onEmotionChange={setEmotion}
        />

        {activeTool && <SimToolOverlay tool={activeTool} />}

        {/* Hard cutoff banner */}
        {hardCutoff && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0,
            background: 'rgba(239,68,68,0.92)', backdropFilter: 'blur(4px)',
            padding: '12px 20px', fontSize: '0.85rem', fontWeight: 700,
            letterSpacing: '0.15em', textTransform: 'uppercase', textAlign: 'center', color: '#fff',
            zIndex: 30, animation: 'sim-banner-in 0.35s cubic-bezier(0.34,1.56,0.64,1) forwards',
          }}>
            TIME — {cutoffMsg}
          </div>
        )}

        {/* Scrollable transcript */}
        <div style={{
          position: 'absolute', bottom: textOpen ? 108 : 0, left: 0, right: 0,
          maxHeight: '48%', zIndex: 6,
          display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
          transition: 'bottom 0.25s',
          background: 'linear-gradient(to top, rgba(3,6,12,0.94) 0%, rgba(3,6,12,0.55) 65%, transparent 100%)',
        }}>
          <div ref={transcriptRef} style={{ overflowY: 'auto', padding: '32px 20px 16px', scrollbarWidth: 'none' }}>
            {turns.map((turn, i) => (
              <div key={turn.id} style={{
                marginBottom: i === turns.length - 1 ? 0 : 16,
                display: 'flex', flexDirection: 'column',
                alignItems: turn.speaker === 'user' ? 'flex-end' : 'flex-start',
              }}>
                <div style={{
                  fontSize: '0.56rem', fontWeight: 600, letterSpacing: '0.1em',
                  textTransform: 'uppercase', marginBottom: 4,
                  color: turn.speaker === 'ai' ? 'rgba(167,139,250,0.5)' : 'rgba(34,211,238,0.5)',
                }}>
                  {turn.speaker === 'ai' ? 'Interviewer' : 'You'}
                </div>
                <div style={{
                  fontSize: '0.8rem', lineHeight: 1.65,
                  color: turn.speaker === 'ai' ? 'rgba(226,232,240,0.9)' : 'rgba(186,230,253,0.85)',
                  maxWidth: '72%',
                  textAlign: turn.speaker === 'user' ? 'right' : 'left',
                }}>
                  {turn.text}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Text input */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'rgba(3,6,12,0.97)', borderTop: '1px solid rgba(255,255,255,0.04)',
          padding: '14px 16px', zIndex: 15,
          opacity: textOpen ? 1 : 0, transform: textOpen ? 'translateY(0)' : 'translateY(8px)',
          transition: 'all 0.2s', pointerEvents: textOpen ? 'all' : 'none',
        }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSubmit())}
              placeholder={disabled ? 'Waiting for interviewer…' : 'Type your response… (Enter to send)'}
              disabled={disabled}
              rows={2}
              style={{
                flex: 1, background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8,
                padding: '10px 14px', color: '#cbd5e1',
                fontFamily: "'DM Mono', monospace", fontSize: '0.77rem',
                outline: 'none', resize: 'none', lineHeight: 1.55,
              }}
            />
            <button
              onClick={handleSubmit}
              disabled={disabled || !input.trim()}
              style={{
                width: 40, height: 40, flexShrink: 0,
                background: (!disabled && input.trim()) ? '#22d3ee' : 'rgba(34,211,238,0.08)',
                border: '1px solid rgba(34,211,238,0.15)',
                borderRadius: 8, color: (!disabled && input.trim()) ? '#040c18' : 'rgba(34,211,238,0.3)',
                fontFamily: "'DM Mono', monospace", fontSize: '1rem',
                cursor: (!disabled && input.trim()) ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.15s',
              }}
            >
              ↑
            </button>
          </div>
        </div>

        {/* User tag — combines mic status + recording — bottom-right */}
        <div style={{
          position: 'absolute', bottom: textOpen ? 94 : 14, right: 16,
          background: isRecording ? 'rgba(239,68,68,0.1)' : 'rgba(4,8,16,0.55)',
          backdropFilter: 'blur(10px)',
          borderRadius: 20, padding: '5px 12px 5px 9px', fontSize: '0.67rem',
          color: isRecording ? '#fca5a5' : 'rgba(226,232,240,0.6)',
          display: 'flex', alignItems: 'center', gap: 7,
          border: `1px solid ${isRecording ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.05)'}`,
          zIndex: 7, transition: 'all 0.25s',
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: micMuted ? '#475569' : isRecording ? '#ef4444' : '#4ade80',
            animation: isRecording ? 'sim-emp 0.8s ease-in-out infinite' : micMuted ? 'none' : 'sim-emp 2.5s ease-in-out infinite',
          }} />
          {isRecording ? 'Recording' : 'You'}
        </div>
      </div>

      {showDevices && (
        <SimDevicePicker
          selectedMicId={selectedMicId}
          selectedSpeakerId={selectedSpeakerId}
          onMicChange={setSelectedMicId}
          onSpeakerChange={setSelectedSpeakerId}
          onClose={() => setShowDevices(false)}
        />
      )}

      <SimControls
        remaining={remaining}
        timeBudgetSeconds={timeBudgetSeconds}
        scenarioType={scenarioType}
        micMuted={micMuted}
        textOpen={textOpen}
        faceActive={faceActive}
        showDevices={showDevices}
        canSubmit={!disabled && input.trim().length > 0}
        sessionEnded={sessionEnded}
        onMicToggle={() => setMicMuted((m) => !m)}
        onSubmit={handleSubmit}
        onEnd={endSession}
        onTextToggle={() => setTextOpen((o) => !o)}
        onFaceToggle={() => setFaceActive((f) => !f)}
        onDevicesToggle={() => setShowDevices((d) => !d)}
      />
    </div>
  )
}
