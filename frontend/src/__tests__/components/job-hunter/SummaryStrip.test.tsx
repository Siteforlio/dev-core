import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SummaryStrip from '../../../components/job-hunter/SummaryStrip'
import type { CampaignSummary } from '../../../types/jobHunter'

const summary: CampaignSummary = {
  totalApplications: 142,
  todayApplications: 12,
  weekApplications: 48,
  responses: 7,
  interviews: 3,
  offers: 1,
  rejectionRate: 22,
}

describe('SummaryStrip', () => {
  it('renders total applications count', () => {
    render(<SummaryStrip summary={summary} />)
    expect(screen.getByText('142')).toBeInTheDocument()
  })

  it('renders today sub-label', () => {
    render(<SummaryStrip summary={summary} />)
    expect(screen.getByText('12 today')).toBeInTheDocument()
  })

  it('renders interviews count', () => {
    render(<SummaryStrip summary={summary} />)
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('renders rejection rate as percentage', () => {
    render(<SummaryStrip summary={summary} />)
    expect(screen.getByText('22%')).toBeInTheDocument()
  })

  it('renders offers count', () => {
    render(<SummaryStrip summary={summary} />)
    expect(screen.getByText('1')).toBeInTheDocument()
  })
})
