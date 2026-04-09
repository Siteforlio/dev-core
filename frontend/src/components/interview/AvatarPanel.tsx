import { useEffect, useRef, useState } from 'react'

interface Props {
  sessionId: string | null
  persona: string
  isSpeaking: boolean
}

export default function AvatarPanel({ sessionId, persona, isSpeaking }: Props) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!sessionId) return
    const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/avatar/${sessionId}`)
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    return () => ws.close()
  }, [sessionId])

  return (
    <div className="flex flex-col items-center justify-center bg-gray-900 rounded-xl overflow-hidden w-full h-full min-h-64 relative">
      {/* Simli will attach a <video> here via their SDK in a future integration */}
      {/* For now: animated avatar placeholder */}
      <div className="relative flex items-center justify-center">
        {/* Face */}
        <div
          className={`w-36 h-36 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-2xl transition-transform duration-300 ${
            isSpeaking ? 'scale-105' : 'scale-100'
          }`}
        >
          <span className="text-6xl select-none">🧑‍💼</span>
        </div>
        {/* Speaking pulse rings */}
        {isSpeaking && (
          <>
            <div className="absolute w-44 h-44 rounded-full border-2 border-blue-400 opacity-60 animate-ping" />
            <div className="absolute w-52 h-52 rounded-full border border-indigo-400 opacity-30 animate-ping" style={{ animationDelay: '150ms' }} />
          </>
        )}
      </div>

      {/* Persona label */}
      <p className="mt-4 text-xs text-gray-400 italic text-center px-4 leading-relaxed max-w-xs">
        {persona || 'Hiring Manager'}
      </p>

      {/* Connection dot */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-gray-600'}`} />
        <span className="text-xs text-gray-500">{connected ? 'Live' : 'Ready'}</span>
      </div>
    </div>
  )
}
