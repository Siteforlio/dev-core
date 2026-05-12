import { useEffect, useRef, useState } from 'react'

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

    function connect() {
      if (deadRef.current) return
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(
        `${proto}//${window.location.host}/api/v1/ws/campaign/${campaignId}/activity?token=${token}`
      )
      wsRef.current = ws

      ws.onmessage = (e: MessageEvent) => {
        if (ws !== wsRef.current) return  // stale connection — ignore
        const msg: ActivityMessage = {
          id: `${Date.now()}-${Math.random()}`,
          text: typeof e.data === 'string' ? e.data : JSON.stringify(e.data),
          timestamp: new Date(),
        }
        setFeed((prev) => [msg, ...prev].slice(0, 100))
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
