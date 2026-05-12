import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useJobHunter } from '../../hooks/useJobHunter'

const mockToken = 'test-token'

vi.mock('../../store/authStore', () => {
  const store = Object.assign(
    vi.fn((selector: (s: { accessToken: string }) => unknown) => selector({ accessToken: 'test-token' })),
    { getState: () => ({ accessToken: 'test-token' }) }
  )
  return { useAuthStore: store }
})

describe('useJobHunter', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('listCampaigns returns mapped array on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({
        data: [{ id: 'c1', name: 'My Campaign', status: 'active', broad_category: 'Engineering', sub_categories: ['Backend'] }],
        error: null,
      }),
    }) as unknown as typeof fetch

    const { result } = renderHook(() => useJobHunter())
    const campaigns = await result.current.listCampaigns()

    expect(campaigns).toHaveLength(1)
    expect(campaigns[0].id).toBe('c1')
    expect(campaigns[0].broadCategory).toBe('Engineering')
  })

  it('createCampaign posts to correct endpoint with snake_case body', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        data: { id: 'c2', name: 'New', status: 'active', sub_categories: ['Backend'] },
        error: null,
      }),
    }) as unknown as typeof fetch

    const { result } = renderHook(() => useJobHunter())
    const campaign = await result.current.createCampaign({ name: 'New', broadCategory: 'Engineering', userCountry: 'US' })

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/job-hunter/campaigns',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'New', broad_category: 'Engineering', user_country: 'US', anywhere: false, work_type: 'remote' }),
      })
    )
    expect(campaign.id).toBe('c2')
  })

  it('getInterviewContext calls bridge endpoint and maps camelCase', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({
        data: {
          company: 'Stripe',
          role: 'Engineer',
          application_id: 'app-1',
          persona_string: 'hello',
          managers: [],
          round_patterns: { rounds: ['HR'] },
        },
        error: null,
      }),
    }) as unknown as typeof fetch

    const { result } = renderHook(() => useJobHunter())
    const ctx = await result.current.getInterviewContext('camp-1', 'app-1')

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/job-hunter/campaigns/camp-1/applications/app-1/interview-context',
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${mockToken}` }) })
    )
    expect(ctx.company).toBe('Stripe')
    expect(ctx.personaString).toBe('hello')
  })

  it('getDashboard maps summary fields to camelCase', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({
        data: {
          summary: { total_applications: 10, today_applications: 2, week_applications: 5, responses: 1, interviews: 0, offers: 0, rejection_rate: 20 },
          pipeline: [],
          interviews: [],
        },
        error: null,
      }),
    }) as unknown as typeof fetch

    const { result } = renderHook(() => useJobHunter())
    const dash = await result.current.getDashboard('camp-1')

    expect(dash.summary.totalApplications).toBe(10)
    expect(dash.summary.rejectionRate).toBe(20)
  })
})
