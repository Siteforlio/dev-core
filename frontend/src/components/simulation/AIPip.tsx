// frontend/src/components/simulation/AIPip.tsx

interface Props {
  speaking: boolean
  thinking: boolean
}

export default function AIPip({ speaking, thinking }: Props) {
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
          background: 'linear-gradient(180deg, #111420 0%, #08090f 100%)',
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
            background: 'radial-gradient(circle at 42% 38%, #9fa8c0, #6b7490 45%, #3d4262)',
            position: 'relative',
          }}>
            <svg viewBox="0 0 48 48" fill="none" style={{ width: 46, height: 46, position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)' }}>
              <ellipse cx="24" cy="26" rx="15" ry="17" fill="#9fa8c0" opacity="0.3"/>
              <ellipse cx="18" cy="22" rx="2.8" ry="3" fill="#2d3148"/>
              <ellipse cx="30" cy="22" rx="2.8" ry="3" fill="#2d3148"/>
              <circle cx="18" cy="22" r="2" fill="#4a5070"/>
              <circle cx="30" cy="22" r="2" fill="#4a5070"/>
              <circle cx="18.5" cy="22.5" r="1" fill="#1a1c28"/>
              <circle cx="30.5" cy="22.5" r="1" fill="#1a1c28"/>
              <circle cx="19.2" cy="21.4" r="0.5" fill="rgba(255,255,255,0.5)"/>
              <circle cx="31.2" cy="21.4" r="0.5" fill="rgba(255,255,255,0.5)"/>
              <path d="M19 33 Q24 37 29 33" stroke="rgba(80,90,120,0.7)" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
              <path d="M23.5 25 L22 29 L26 29" stroke="rgba(100,110,140,0.5)" strokeWidth="1.2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
              <ellipse cx="9" cy="26" rx="2" ry="3.5" fill="#8a93ad" opacity="0.4"/>
              <ellipse cx="39" cy="26" rx="2" ry="3.5" fill="#8a93ad" opacity="0.4"/>
              <ellipse cx="24" cy="11" rx="15" ry="8" fill="#2d3148" opacity="0.7"/>
            </svg>
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
          letterSpacing: '0.06em', textTransform: 'uppercase' as const,
          borderTop: '1px solid rgba(167,139,250,0.08)',
        }}>
          Interviewer
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
