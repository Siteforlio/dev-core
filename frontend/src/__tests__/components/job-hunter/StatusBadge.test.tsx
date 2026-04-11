import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBadge from '../../../components/job-hunter/StatusBadge'

describe('StatusBadge', () => {
  it('renders MATCH with green class', () => {
    render(<StatusBadge variant="matchScore" value="MATCH" />)
    const badge = screen.getByText('MATCH')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('green')
  })

  it('renders PARTIAL with yellow class', () => {
    render(<StatusBadge variant="matchScore" value="PARTIAL" />)
    expect(screen.getByText('PARTIAL').className).toContain('yellow')
  })

  it('renders SKIP with gray class', () => {
    render(<StatusBadge variant="matchScore" value="SKIP" />)
    expect(screen.getByText('SKIP').className).toContain('gray')
  })

  it('renders null value as nothing', () => {
    const { container } = render(<StatusBadge variant="matchScore" value={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders interview status with purple class', () => {
    render(<StatusBadge variant="status" value="interview" />)
    expect(screen.getByText('interview').className).toContain('purple')
  })

  it('renders applied status with blue class', () => {
    render(<StatusBadge variant="status" value="applied" />)
    expect(screen.getByText('applied').className).toContain('blue')
  })

  it('renders rejected status with red class', () => {
    render(<StatusBadge variant="status" value="rejected" />)
    expect(screen.getByText('rejected').className).toContain('red')
  })
})
