// frontend/src/components/simulation/AIPip.tsx
import { CHARACTERS } from '../interview/InterviewerCharacters'

interface Props {
  speaking: boolean
  thinking: boolean
  characterId?: number
}

export default function AIPip({ speaking, thinking, characterId = 0 }: Props) {
  const char = CHARACTERS[characterId] ?? CHARACTERS[0]
  const { Face, name, title, bg } = char

  return (
    <div style={{
      position: 'absolute', top: 16, right: 16,
      width: '18%', aspectRatio: '3/4',
      borderRadius: 12, overflow: 'hidden',
      border: '1px solid rgba(167,139,250,0.2)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.8), 0 0 20px rgba(167,139,250,0.06)',
      background: '#0a0c14', zIndex: 10,
    }}>
      <div
        className={speaking && !thinking ? 'sim-speaking' : ''}
        style={{
          width: '100%', height: '100%',
          background: bg,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: 8, position: 'relative',
        }}
      >
        {/* Desk shadow */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: '30%',
          background: 'linear-gradient(to top, #06070d, transparent)',
        }} />

        {/* Face */}
        <div style={{ position: 'relative', width: 56, height: 56 }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%', overflow: 'hidden',
            border: '1.5px solid rgba(167,139,250,0.2)',
            position: 'relative',
          }}>
            <Face />
          </div>
          <div className="sim-speak-ring" style={{ position: 'absolute', inset: -5, borderRadius: '50%', border: '1.5px solid rgba(167,139,250,0.25)' }} />
          <div className="sim-speak-ring2" style={{ position: 'absolute', inset: -11, borderRadius: '50%', border: '1px solid rgba(167,139,250,0.1)' }} />
        </div>

        {/* Waveform */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2.5, height: 14 }}>
          {([4, 10, 14, 7, 11, 5, 9] as const).map((h, i) => (
            <div key={i} className="sim-wbar" style={{
              width: 2.5, height: h, borderRadius: 3,
              background: 'rgba(167,139,250,0.5)',
              transform: 'scaleY(0.3)',
              animationDelay: `${[0, 0.12, 0.22, 0.08, 0.28, 0.04, 0.18][i]}s`,
            }} />
          ))}
        </div>

        {/* Nametag */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
          padding: '5px 8px', fontSize: '0.58rem', fontWeight: 500,
          color: 'rgba(167,139,250,0.7)', textAlign: 'center',
          letterSpacing: '0.06em',
          borderTop: '1px solid rgba(167,139,250,0.08)',
        }}>
          <div>{name}</div>
          <div style={{ fontSize: '0.5rem', color: 'rgba(167,139,250,0.4)', marginTop: 1 }}>{title}</div>
        </div>

        {/* Thinking overlay */}
        {thinking && (
          <div style={{
            position: 'absolute', inset: 0,
            background: 'rgba(5,9,15,0.75)', backdropFilter: 'blur(2px)',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 8, zIndex: 5,
          }}>
            <div style={{ display: 'flex', gap: 5 }}>
              {[0, 0.2, 0.4].map((delay, i) => (
                <div key={i} style={{
                  width: 5, height: 5, borderRadius: '50%', background: '#a78bfa',
                  animation: `sim-tdot 1.2s ease-in-out ${delay}s infinite`,
                }} />
              ))}
            </div>
            <div style={{ fontSize: '0.55rem', color: 'rgba(167,139,250,0.5)', letterSpacing: '0.1em', textTransform: 'uppercase' as const }}>
              Thinking
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
