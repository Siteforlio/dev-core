import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCampaignActivity } from '../../hooks/useCampaignActivity'

class MockWebSocket {
  url: string
  onmessage: ((e: MessageEvent) => void) | null = null
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: ((e: Event) => void) | null = null
  static instances: MockWebSocket[] = []

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  close() {}

  simulateMessage(data: string) {
    this.onmessage?.({ data } as MessageEvent)
  }
}

describe('useCampaignActivity', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('connects to correct WS URL with token', () => {
    renderHook(() => useCampaignActivity('camp-1', 'tok-abc'))
    expect(MockWebSocket.instances[0].url).toBe('/api/v1/ws/campaign/camp-1/activity?token=tok-abc')
  })

  it('does not connect when campaignId is null', () => {
    renderHook(() => useCampaignActivity(null, 'tok-abc'))
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('appends messages to the feed', () => {
    const { result } = renderHook(() => useCampaignActivity('camp-1', 'tok-abc'))
    act(() => {
      MockWebSocket.instances[0].simulateMessage('Applied to Stripe — Backend Engineer')
    })
    expect(result.current.feed).toHaveLength(1)
    expect(result.current.feed[0].text).toBe('Applied to Stripe — Backend Engineer')
  })

  it('caps feed at 100 messages', () => {
    const { result } = renderHook(() => useCampaignActivity('camp-1', 'tok-abc'))
    act(() => {
      for (let i = 0; i < 110; i++) {
        MockWebSocket.instances[0].simulateMessage(`msg-${i}`)
      }
    })
    expect(result.current.feed).toHaveLength(100)
  })
})
