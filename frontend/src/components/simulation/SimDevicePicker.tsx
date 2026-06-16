// frontend/src/components/simulation/SimDevicePicker.tsx
import { useEffect, useRef, useState } from 'react'

interface Props {
  selectedMicId: string | undefined
  selectedSpeakerId: string | undefined
  onMicChange: (id: string) => void
  onSpeakerChange: (id: string) => void
  onClose: () => void
}

interface DeviceDropdownProps {
  devices: MediaDeviceInfo[]
  selectedId: string | undefined
  placeholder: string
  onChange: (id: string) => void
}

function DeviceDropdown({ devices, selectedId, placeholder, onChange }: DeviceDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const selected = devices.find((d) => d.deviceId === selectedId) ?? devices[0]
  const label = selected?.label || placeholder

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {/* Trigger */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: 'rgba(255,255,255,0.04)',
          border: `1px solid ${open ? 'rgba(34,211,238,0.2)' : 'rgba(255,255,255,0.07)'}`,
          borderRadius: 7, padding: '8px 12px', cursor: 'pointer',
          fontFamily: "'DM Mono', monospace", fontSize: '0.72rem',
          color: '#cbd5e1', textAlign: 'left', transition: 'border-color 0.15s',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, marginRight: 8 }}>
          {label}
        </span>
        <span style={{
          color: '#475569', fontSize: '0.55rem', flexShrink: 0,
          transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s',
        }}>▾</span>
      </button>

      {/* Dropdown list */}
      {open && (
        <div style={{
          position: 'absolute', bottom: 'calc(100% + 6px)', left: 0, right: 0, zIndex: 50,
          background: '#0b1320', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 8, overflow: 'hidden',
          boxShadow: '0 -8px 24px rgba(0,0,0,0.6)',
        }}>
          {devices.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: '0.7rem', color: '#475569' }}>
              No devices found
            </div>
          ) : (
            devices.map((d) => {
              const isActive = (selectedId ?? devices[0]?.deviceId) === d.deviceId
              return (
                <button
                  key={d.deviceId}
                  onClick={() => { onChange(d.deviceId); setOpen(false) }}
                  style={{
                    width: '100%', display: 'block', padding: '9px 12px',
                    background: isActive ? 'rgba(34,211,238,0.07)' : 'transparent',
                    border: 'none', borderBottom: '1px solid rgba(255,255,255,0.04)',
                    color: isActive ? '#22d3ee' : '#94a3b8',
                    fontFamily: "'DM Mono', monospace", fontSize: '0.7rem',
                    textAlign: 'left', cursor: 'pointer',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)' }}
                  onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
                >
                  {isActive && <span style={{ marginRight: 6, fontSize: '0.55rem' }}>●</span>}
                  {d.label || `Device ${d.deviceId.slice(0, 6)}`}
                </button>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}

export default function SimDevicePicker({
  selectedMicId, selectedSpeakerId, onMicChange, onSpeakerChange, onClose,
}: Props) {
  const [mics, setMics] = useState<MediaDeviceInfo[]>([])
  const [speakers, setSpeakers] = useState<MediaDeviceInfo[]>([])
  const [speakerSupported, setSpeakerSupported] = useState(false)

  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => { stream.getTracks().forEach((t) => t.stop()); return navigator.mediaDevices.enumerateDevices() })
      .catch(() => navigator.mediaDevices.enumerateDevices())
      .then((devices) => {
        setMics(devices.filter((d) => d.kind === 'audioinput'))
        setSpeakers(devices.filter((d) => d.kind === 'audiooutput'))
        setSpeakerSupported(typeof AudioContext !== 'undefined' && 'setSinkId' in AudioContext.prototype)
      })
      .catch(() => {})
  }, [])

  const sectionLabel = (text: string) => (
    <div style={{
      fontSize: '0.56rem', color: '#334155', textTransform: 'uppercase' as const,
      letterSpacing: '0.1em', marginBottom: 6,
    }}>
      {text}
    </div>
  )

  return (
    <div style={{
      position: 'absolute', bottom: 60, right: 16,
      background: '#080f1e', backdropFilter: 'blur(20px)',
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10,
      padding: '14px 14px 16px', width: 272, zIndex: 40,
      fontFamily: "'DM Mono', monospace",
      boxShadow: '0 12px 40px rgba(0,0,0,0.7)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <span style={{ fontSize: '0.58rem', color: '#475569', letterSpacing: '0.1em' }}>
          AUDIO DEVICES
        </span>
        <button
          onClick={onClose}
          style={{
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 4, color: '#475569', cursor: 'pointer',
            fontSize: '0.65rem', lineHeight: 1, padding: '3px 6px',
          }}
        >
          ✕
        </button>
      </div>

      {/* Mic */}
      <div style={{ marginBottom: 14 }}>
        {sectionLabel('🎙  Microphone')}
        <DeviceDropdown
          devices={mics}
          selectedId={selectedMicId}
          placeholder="Default microphone"
          onChange={onMicChange}
        />
      </div>

      {/* Speaker */}
      <div>
        {sectionLabel('🔊  Speaker output')}
        {speakerSupported ? (
          <DeviceDropdown
            devices={speakers}
            selectedId={selectedSpeakerId}
            placeholder="Default speaker"
            onChange={onSpeakerChange}
          />
        ) : (
          <div style={{
            fontSize: '0.65rem', color: '#334155', padding: '8px 12px',
            border: '1px solid rgba(255,255,255,0.05)', borderRadius: 7,
          }}>
            Not supported in this browser
          </div>
        )}
      </div>
    </div>
  )
}
