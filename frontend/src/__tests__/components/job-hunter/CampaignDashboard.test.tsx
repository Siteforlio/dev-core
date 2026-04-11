import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const mockGetDashboard = vi.fn()
const mockGetInterviewContext = vi.fn()

vi.mock('../../../hooks/useJobHunter', () => ({
  useJobHunter: () => ({
    getDashboard: mockGetDashboard,
    getInterviewContext: mockGetInterviewContext,
  }),
}))

vi.mock('../../../hooks/useCampaignActivity', () => ({
  useCampaignActivity: () => ({ feed: [] }),
}))

vi.mock('../../../store/authStore', () => ({
  useAuthStore: vi.fn((selector: (s: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'tok' })
  ),
}))

const { default: CampaignDashboard } = await import('../../../components/job-hunter/CampaignDashboard')

const dashboardData = {
  summary: {
    totalApplications: 50,
    todayApplications: 5,
    weekApplications: 20,
    responses: 3,
    interviews: 1,
    offers: 0,
    rejectionRate: 10,
  },
  pipeline: [
    {
      id: 'app-1',
      company: 'Stripe',
      title: 'Backend Engineer',
      location: 'Remote',
      appliedAt: '2026-04-12T10:00:00Z',
      status: 'interview' as const,
      matchScore: 'MATCH' as const,
      source: 'jobspy',
    },
  ],
  interviews: [
    { applicationId: 'app-1', company: 'Stripe', role: 'Backend Engineer', scheduledAt: '2026-04-15T14:00:00Z' },
  ],
}

describe('CampaignDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDashboard.mockResolvedValue(dashboardData)
    mockGetInterviewContext.mockResolvedValue({
      company: 'Stripe',
      role: 'Backend Engineer',
      applicationId: 'app-1',
      personaString: 'hello',
      managers: [],
      roundPatterns: {},
    })
  })

  it('shows loading spinner initially', () => {
    mockGetDashboard.mockReturnValue(new Promise(() => {}))
    render(<CampaignDashboard campaignId="c1" onStartInterviewPrep={() => {}} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders application company after load', async () => {
    render(<CampaignDashboard campaignId="c1" onStartInterviewPrep={() => {}} />)
    await waitFor(() => expect(screen.getByText('Stripe')).toBeInTheDocument())
  })

  it('renders total applications from summary', async () => {
    render(<CampaignDashboard campaignId="c1" onStartInterviewPrep={() => {}} />)
    await waitFor(() => expect(screen.getByText('50')).toBeInTheDocument())
  })

  it('shows scheduled interviews section', async () => {
    render(<CampaignDashboard campaignId="c1" onStartInterviewPrep={() => {}} />)
    await waitFor(() => expect(screen.getByText(/Scheduled Interviews/i)).toBeInTheDocument())
  })

  it('shows error message when fetch fails', async () => {
    mockGetDashboard.mockRejectedValue(new Error('Network error'))
    render(<CampaignDashboard campaignId="c1" onStartInterviewPrep={() => {}} />)
    await waitFor(() => expect(screen.getByText(/Failed to load/i)).toBeInTheDocument())
  })
})
