import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ActivityFeed from '../../../components/job-hunter/ActivityFeed'
import type { ActivityMessage } from '../../../hooks/useCampaignActivity'

const messages: ActivityMessage[] = [
  { id: '1', text: 'Applied to Stripe — Backend Engineer', timestamp: new Date('2026-04-12T10:00:00Z') },
  { id: '2', text: 'Rejection received from Acme Corp', timestamp: new Date('2026-04-12T09:00:00Z') },
]

describe('ActivityFeed', () => {
  it('renders all messages', () => {
    render(<ActivityFeed feed={messages} />)
    expect(screen.getByText(/Applied to Stripe/)).toBeInTheDocument()
    expect(screen.getByText(/Rejection received/)).toBeInTheDocument()
  })

  it('shows empty state when feed is empty', () => {
    render(<ActivityFeed feed={[]} />)
    expect(screen.getByText(/No activity yet/i)).toBeInTheDocument()
  })
})
