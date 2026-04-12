import { useEffect, useRef, useState } from 'react'

export interface ActivityMessage {
  id: string
  text: string
  timestamp: Date
}

export function useCampaignActivity(campaignId: string | null, token: string | null) {
  const [feed, setFeed] = useState<ActivityMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!campaignId || !token) return

    const ws = new WebSocket(`/api/v1/ws/campaign/${campaignId}/activity?token=${token}`)
    wsRef.current = ws

    ws.onmessage = (e: MessageEvent) => {
      const msg: ActivityMessage = {
        id: `${Date.now()}-${Math.random()}`,
        text: typeof e.data === 'string' ? e.data : JSON.stringify(e.data),
        timestamp: new Date(),
      }
      setFeed((prev) => [msg, ...prev].slice(0, 100))
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [campaignId, token])

  return { feed }
}
