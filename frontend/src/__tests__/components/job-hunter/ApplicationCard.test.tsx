import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ApplicationCard from '../../../components/job-hunter/ApplicationCard'
import type { Application } from '../../../types/jobHunter'

const mockApp: Application = {
  id: 'app-1',
  company: 'Stripe',
  title: 'Backend Engineer',
  location: 'Remote',
  appliedAt: '2026-04-12T10:00:00Z',
  status: 'applied',
  matchScore: 'MATCH',
  source: 'jobspy',
}

describe('ApplicationCard', () => {
  it('renders company and title', () => {
    render(<ApplicationCard application={mockApp} onStartInterviewPrep={() => {}} />)
    expect(screen.getByText('Stripe')).toBeInTheDocument()
    expect(screen.getByText('Backend Engineer')).toBeInTheDocument()
  })

  it('renders match score badge', () => {
    render(<ApplicationCard application={mockApp} onStartInterviewPrep={() => {}} />)
    expect(screen.getByText('MATCH')).toBeInTheDocument()
  })

  it('shows Interview Prep button when status is interview', () => {
    const interviewApp = { ...mockApp, status: 'interview' as const }
    render(<ApplicationCard application={interviewApp} onStartInterviewPrep={() => {}} />)
    expect(screen.getByRole('button', { name: /interview prep/i })).toBeInTheDocument()
  })

  it('does not show Interview Prep button for applied status', () => {
    render(<ApplicationCard application={mockApp} onStartInterviewPrep={() => {}} />)
    expect(screen.queryByRole('button', { name: /interview prep/i })).toBeNull()
  })

  it('calls onStartInterviewPrep with application id on click', () => {
    const interviewApp = { ...mockApp, status: 'interview' as const }
    const onStart = vi.fn()
    render(<ApplicationCard application={interviewApp} onStartInterviewPrep={onStart} />)
    fireEvent.click(screen.getByRole('button', { name: /interview prep/i }))
    expect(onStart).toHaveBeenCalledWith('app-1')
  })
})
