import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ApplicationCard from '../../../components/job-hunter/ApplicationCard'
import type { Application } from '../../../types/jobHunter'

const baseApp: Application = {
  id: 'app-1',
  applicationId: null,
  company: 'Stripe',
  title: 'Backend Engineer',
  location: 'Remote',
  appliedAt: '2026-04-12T10:00:00Z',
  postedAt: null,
  discoveredAt: '2026-04-12T10:00:00Z',
  status: 'pending',
  matchScore: 'MATCH',
  source: 'jobspy',
}

const noop = () => {}

describe('ApplicationCard', () => {
  it('renders company and title', () => {
    render(<ApplicationCard application={baseApp} onStartInterviewPrep={noop} onApply={noop} onViewTracking={noop} />)
    expect(screen.getByText('Stripe')).toBeInTheDocument()
    expect(screen.getByText('Backend Engineer')).toBeInTheDocument()
  })

  it('renders match score badge', () => {
    render(<ApplicationCard application={baseApp} onStartInterviewPrep={noop} onApply={noop} onViewTracking={noop} />)
    expect(screen.getByText('MATCH')).toBeInTheDocument()
  })

  it('shows Apply button for pending applications', () => {
    render(<ApplicationCard application={baseApp} onStartInterviewPrep={noop} onApply={noop} onViewTracking={noop} />)
    expect(screen.getByRole('button', { name: /apply/i })).toBeInTheDocument()
  })

  it('calls onApply with application id on Apply click', () => {
    const onApply = vi.fn()
    render(<ApplicationCard application={baseApp} onStartInterviewPrep={noop} onApply={onApply} onViewTracking={noop} />)
    fireEvent.click(screen.getByRole('button', { name: /apply/i }))
    expect(onApply).toHaveBeenCalledWith('app-1')
  })

  it('shows Track button for applied applications', () => {
    const appliedApp = { ...baseApp, status: 'applied' as const }
    render(<ApplicationCard application={appliedApp} onStartInterviewPrep={noop} onApply={noop} onViewTracking={noop} />)
    expect(screen.getByRole('button', { name: /track/i })).toBeInTheDocument()
  })

  it('calls onViewTracking on Track click', () => {
    const appliedApp = { ...baseApp, status: 'applied' as const }
    const onViewTracking = vi.fn()
    render(<ApplicationCard application={appliedApp} onStartInterviewPrep={noop} onApply={noop} onViewTracking={onViewTracking} />)
    fireEvent.click(screen.getByRole('button', { name: /track/i }))
    expect(onViewTracking).toHaveBeenCalledWith('app-1')
  })

  it('shows Interview Prep button when status is interview', () => {
    const interviewApp = { ...baseApp, status: 'interview' as const }
    render(<ApplicationCard application={interviewApp} onStartInterviewPrep={noop} onApply={noop} onViewTracking={noop} />)
    expect(screen.getByRole('button', { name: /interview prep/i })).toBeInTheDocument()
  })

  it('calls onStartInterviewPrep with application id on click', () => {
    const interviewApp = { ...baseApp, status: 'interview' as const }
    const onStart = vi.fn()
    render(<ApplicationCard application={interviewApp} onStartInterviewPrep={onStart} onApply={noop} onViewTracking={noop} />)
    fireEvent.click(screen.getByRole('button', { name: /interview prep/i }))
    expect(onStart).toHaveBeenCalledWith('app-1')
  })
})
