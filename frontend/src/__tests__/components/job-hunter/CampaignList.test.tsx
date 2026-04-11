import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CampaignList from '../../../components/job-hunter/CampaignList'
import type { Campaign } from '../../../types/jobHunter'

const campaigns: Campaign[] = [
  { id: 'c1', name: 'Backend Hunt', status: 'active', broadCategory: 'Engineering', subCategories: ['Backend'] },
  { id: 'c2', name: 'Frontend Run', status: 'paused', broadCategory: 'Engineering', subCategories: ['Frontend'] },
]

describe('CampaignList', () => {
  it('renders all campaign names', () => {
    render(<CampaignList campaigns={campaigns} onSelect={() => {}} onCreateNew={() => {}} />)
    expect(screen.getByText('Backend Hunt')).toBeInTheDocument()
    expect(screen.getByText('Frontend Run')).toBeInTheDocument()
  })

  it('shows status badge for each campaign', () => {
    render(<CampaignList campaigns={campaigns} onSelect={() => {}} onCreateNew={() => {}} />)
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText('paused')).toBeInTheDocument()
  })

  it('calls onSelect with campaign id when View is clicked', () => {
    const onSelect = vi.fn()
    render(<CampaignList campaigns={campaigns} onSelect={onSelect} onCreateNew={() => {}} />)
    fireEvent.click(screen.getAllByRole('button', { name: /view/i })[0])
    expect(onSelect).toHaveBeenCalledWith('c1')
  })

  it('calls onCreateNew when New Campaign button is clicked', () => {
    const onCreateNew = vi.fn()
    render(<CampaignList campaigns={campaigns} onSelect={() => {}} onCreateNew={onCreateNew} />)
    fireEvent.click(screen.getByRole('button', { name: /new campaign/i }))
    expect(onCreateNew).toHaveBeenCalled()
  })

  it('shows empty state when no campaigns', () => {
    render(<CampaignList campaigns={[]} onSelect={() => {}} onCreateNew={() => {}} />)
    expect(screen.getByText(/no campaigns yet/i)).toBeInTheDocument()
  })
})
