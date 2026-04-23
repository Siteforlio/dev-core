import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import TrackingPanel from '../../../components/job-hunter/TrackingPanel'
import type { TrackingStatus } from '../../../types/jobHunter'

const mockTracking: TrackingStatus = {
  applicationId: 'app-1',
  status: 'applied',
  appliedAt: '2026-01-15T12:00:00Z',
  statusUpdatedAt: '2026-01-15T12:00:00Z',
  company: 'Stripe',
  title: 'Senior Software Engineer',
  emailEvents: [
    {
      id: 'ev-1',
      subject: 'Re: your application',
      sender: 'hr@stripe.com',
      classification: 'response',
      receivedAt: '2026-01-20T09:00:00Z',
    },
  ],
}

const mockGetTracking = vi.fn()

vi.mock('../../../hooks/useJobHunter', () => ({
  useJobHunter: () => ({
    getTrackingStatus: mockGetTracking,
  }),
}))

describe('TrackingPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetTracking.mockResolvedValue(mockTracking)
  })

  it('shows loading spinner initially', () => {
    render(<TrackingPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('renders company, title and status after load', async () => {
    render(<TrackingPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('Stripe')).toBeInTheDocument()
      expect(screen.getByText('Senior Software Engineer')).toBeInTheDocument()
      expect(screen.getByText('applied')).toBeInTheDocument()
    })
  })

  it('renders email events', async () => {
    render(<TrackingPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('Re: your application')).toBeInTheDocument()
      expect(screen.getByText('hr@stripe.com')).toBeInTheDocument()
      expect(screen.getByText('response')).toBeInTheDocument()
    })
  })

  it('shows "No emails detected" when email events are empty', async () => {
    mockGetTracking.mockResolvedValue({ ...mockTracking, emailEvents: [] })
    render(<TrackingPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/no emails detected/i)).toBeInTheDocument()
    })
  })

  it('re-fetches on Check email click', async () => {
    render(<TrackingPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => screen.getByRole('button', { name: /check email/i }))
    fireEvent.click(screen.getByRole('button', { name: /check email/i }))
    await waitFor(() => {
      expect(mockGetTracking).toHaveBeenCalledTimes(2)
    })
  })

  it('calls onClose when ✕ is clicked', async () => {
    const onClose = vi.fn()
    render(<TrackingPanel campaignId="c-1" applicationId="app-1" onClose={onClose} />)
    await waitFor(() => screen.getByText('Stripe'))
    fireEvent.click(screen.getByRole('button', { name: /✕/ }))
    expect(onClose).toHaveBeenCalled()
  })

  it('shows error state when fetch fails', async () => {
    mockGetTracking.mockRejectedValue(new Error('Network error'))
    render(<TrackingPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument()
    })
  })

  it('shows email event count in status row', async () => {
    render(<TrackingPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('1 found')).toBeInTheDocument()
    })
  })
})
