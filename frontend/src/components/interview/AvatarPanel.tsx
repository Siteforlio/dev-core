import { CharacterDef } from './InterviewerCharacters'

interface Props {
  character: CharacterDef
  isSpeaking: boolean
}

const WAVEFORM_HEIGHTS = [3, 9, 13, 7, 11, 5, 9]

export default function AvatarPanel({ character, isSpeaking }: Props) {
  return (
    <div style={{
      width: '100%',
      aspectRatio: '3 / 4',
      background: character.bg,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 10,
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Subtle desk/environment gradient at bottom */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '35%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.3), transparent)',
        pointerEvents: 'none',
      }} />

      {/* Face circle */}
      <div style={{ position: 'relative', width: 64, height: 64 }}>
        <div style={{
          width: 64, height: 64,
          borderRadius: '50%',
          overflow: 'hidden',
          border: '1.5px solid rgba(255,255,255,0.12)',
        }}>
          <character.Face />
        </div>

        {/* Speaking pulse rings */}
        {isSpeaking && (
          <>
            <div style={{
              position: 'absolute', inset: -5, borderRadius: '50%',
              border: '1.5px solid rgba(255,255,255,0.2)',
              animation: 'avatarRing 1.6s ease-in-out infinite',
            }} />
            <div style={{
              position: 'absolute', inset: -10, borderRadius: '50%',
              border: '1px solid rgba(255,255,255,0.08)',
              animation: 'avatarRing 1.6s ease-in-out 0.4s infinite',
            }} />
          </>
        )}
      </div>

      {/* Waveform — only when speaking */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 2.5, height: 16,
        opacity: isSpeaking ? 1 : 0.2,
        transition: 'opacity 0.4s',
      }}>
        {WAVEFORM_HEIGHTS.map((h, i) => (
          <div key={i} style={{
            width: 2.5,
            height: isSpeaking ? h : 3,
            borderRadius: 3,
            background: 'rgba(255,255,255,0.45)',
            transition: 'height 0.3s ease',
            animation: isSpeaking ? `avatarWave 1.3s ease-in-out ${i * 0.1}s infinite` : 'none',
          }} />
        ))}
      </div>

      {/* Name tag */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        background: 'rgba(0,0,0,0.5)',
        backdropFilter: 'blur(4px)',
        padding: '5px 8px',
        fontSize: 10, fontWeight: 600,
        color: 'rgba(255,255,255,0.65)',
        textAlign: 'center',
        letterSpacing: '0.05em',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        lineHeight: 1.3,
      }}>
        <div>{character.name}</div>
        <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.3)', fontWeight: 400, marginTop: 1 }}>
          {character.title}
        </div>
      </div>

      {/* CSS keyframes injected once */}
      <style>{`
        @keyframes avatarRing {
          0%, 100% { transform: scale(1); opacity: 0.8; }
          50%       { transform: scale(1.1); opacity: 0.2; }
        }
        @keyframes avatarWave {
          0%, 100% { transform: scaleY(0.4); opacity: 0.5; }
          50%       { transform: scaleY(1);   opacity: 0.9; }
        }
      `}</style>
    </div>
  )
}
