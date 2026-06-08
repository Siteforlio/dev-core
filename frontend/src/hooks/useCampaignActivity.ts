import { useEffect, useRef, useState } from 'react'
import { getFreshToken } from '../lib/apiFetch'

export interface ActivityMessage {
  id: string
  text: string
  timestamp: Date
}

export function useCampaignActivity(campaignId: string | null, token: string | null) {
  const [feed, setFeed] = useState<ActivityMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const deadRef = useRef(false)

  useEffect(() => {
    if (!campaignId || !token) return
    deadRef.current = false

    async function connect() {
      if (deadRef.current) return

      // Always get a fresh (non-expired) token before connecting.
      // getFreshToken() refreshes silently if the stored token is about to expire.
      const freshToken = await getFreshToken()
      if (!freshToken || deadRef.current) return

      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(
        `${proto}//${window.location.host}/api/v1/ws/campaign/${campaignId}/activity?token=${freshToken}`
      )
      wsRef.current = ws

      ws.onmessage = (e: MessageEvent) => {
        if (ws !== wsRef.current) return  // stale connection — ignore
        let text: string
        let timestamp = new Date()
        try {
          const parsed = JSON.parse(e.data)
          text = parsed.text ?? e.data
          if (parsed.timestamp) timestamp = new Date(parsed.timestamp)
        } catch {
          text = typeof e.data === 'string' ? e.data : JSON.stringify(e.data)
        }
        const msg: ActivityMessage = {
          id: `${Date.now()}-${Math.random()}`,
          text,
          timestamp,
        }
        setFeed((prev) => [...prev, msg].slice(-100))
      }

      ws.onclose = () => {
        if (ws !== wsRef.current) return  // already superseded
        if (!deadRef.current) {
          retryRef.current = setTimeout(connect, 2000)
        }
      }
    }

    connect()

    return () => {
      deadRef.current = true
      if (retryRef.current) clearTimeout(retryRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [campaignId, token])

  return { feed }
}
