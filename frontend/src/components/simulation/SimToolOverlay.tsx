// frontend/src/components/simulation/SimToolOverlay.tsx
import type { SimToolEvent } from '../../hooks/useSimulationSession'

interface Props {
  tool: SimToolEvent
}

export default function SimToolOverlay({ tool }: Props) {
  const done = tool.status === 'done'

  return (
    <div style={{
      position: 'absolute', top: '50%', left: '50%',
      transform: 'translate(-50%, -50%)',
      background: 'rgba(4,8,16,0.92)', backdropFilter: 'blur(16px)',
      border: '1px solid rgba(251,191,36,0.2)',
      borderRadius: 10, padding: '14px 18px',
      minWidth: 260, maxWidth: '50%', zIndex: 20,
      fontFamily: "'DM Mono', monospace",
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{
          fontSize: '0.6rem', fontWeight: 600, letterSpacing: '0.1em',
          color: '#fbbf24', textTransform: 'uppercase' as const,
          background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.15)',
          borderRadius: 4, padding: '2px 7px',
        }}>
          {tool.tool}
        </div>
        {!done && (
          <div style={{
            width: 10, height: 10,
            border: '1.5px solid rgba(251,191,36,0.3)', borderTopColor: '#fbbf24',
            borderRadius: '50%', animation: 'sim-spin 0.8s linear infinite',
          }} />
        )}
        <span style={{ fontSize: '0.6rem', color: '#475569' }}>
          {done ? 'done' : 'running...'}
        </span>
      </div>

      {tool.command && (
        <div style={{ fontSize: '0.68rem', color: 'rgba(251,191,36,0.8)', marginBottom: 6 }}>
          $ {tool.command}
        </div>
      )}

      {tool.output && (
        <pre style={{
          fontSize: '0.62rem', color: 'rgba(255,255,255,0.4)', lineHeight: 1.5,
          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 6, marginTop: 2,
          fontFamily: "'DM Mono', monospace",
        }}>
          {tool.output}
        </pre>
      )}
    </div>
  )
}
