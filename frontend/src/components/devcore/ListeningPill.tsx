import { useOverlayStore } from '../../store/overlayStore'

export function ListeningPill() {
  const { state } = useOverlayStore()

  const isActive = state !== 'idle'
  const isThinking = state === 'thinking'
  const isReconnecting = state === 'reconnecting'

  return (
    <div className="flex items-center gap-3 px-6 py-2.5 rounded-full bg-[rgba(9,9,18,0.97)] border border-white/[0.07] shadow-lg">
      <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${isReconnecting ? 'bg-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.8)]' : isActive ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]' : 'bg-violet-400 shadow-[0_0_10px_rgba(167,139,250,0.8)]'} animate-pulse`} />
      <span className="font-orbitron text-[14px] font-bold tracking-[0.18em] text-violet-400">DEVCORE</span>
      <div className="w-px h-5 bg-white/[0.07]" />

      {isReconnecting ? (
        <span className="font-mono text-[12px] text-yellow-400 tracking-wider">reconnecting…</span>
      ) : isThinking ? (
        <span className="font-mono text-[12px] text-amber-400 tracking-wider">thinking...</span>
      ) : isActive ? (
        <div className="flex items-end gap-[3px] h-5">
          {[7, 14, 9, 16, 7, 12].map((h, i) => (
            <span
              key={i}
              className="w-[3px] bg-emerald-400 rounded-sm shadow-[0_0_4px_rgba(52,211,153,0.8)]"
              style={{ height: h, animation: `wave 1.1s ease-in-out ${i * 0.05}s infinite` }}
            />
          ))}
        </div>
      ) : (
        <span className="font-mono text-[12px] text-white/30 tracking-wider">idle</span>
      )}

      <span className="font-mono text-[12px] text-white/40 tracking-wider ml-1">
        {isReconnecting ? 'reconnecting...' : isActive ? 'listening...' : 'Ctrl+Shift+Enter to start'}
      </span>
    </div>
  )
}
