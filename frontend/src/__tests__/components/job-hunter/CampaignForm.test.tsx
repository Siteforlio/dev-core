import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const mockCreateCampaign = vi.fn()
const mockGetCampaignMeta = vi.fn()

vi.mock('../../../hooks/useJobHunter', () => ({
  useJobHunter: () => ({
    createCampaign: mockCreateCampaign,
    getCampaignMeta: mockGetCampaignMeta,
  }),
}))

const { default: CampaignForm } = await import('../../../components/job-hunter/CampaignForm')

describe('CampaignForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetCampaignMeta.mockResolvedValue({ categories: ['Engineering', 'Design'] })
    mockCreateCampaign.mockResolvedValue({
      id: 'new-c',
      name: 'My Campaign',
      status: 'active',
      broadCategory: 'Engineering',
      subCategories: ['Backend'],
    })
  })

  it('renders campaign name and country inputs', () => {
    render(<CampaignForm onCreated={() => {}} />)
    expect(screen.getByPlaceholderText(/senior engineer/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/search country/i)).toBeInTheDocument()
  })

  it('submit button is disabled when fields are empty', () => {
    render(<CampaignForm onCreated={() => {}} />)
    expect(screen.getByRole('button', { name: /create campaign/i })).toBeDisabled()
  })

  it('submit button enables when name and anywhere checkbox are set', async () => {
    render(<CampaignForm onCreated={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText(/senior engineer/i), { target: { value: 'Hunt' } })
    // tick any async category load
    await waitFor(() => {
      fireEvent.click(screen.getByRole('button', { name: 'Engineering' }))
    })
    fireEvent.click(screen.getByRole('checkbox'))
    expect(screen.getByRole('button', { name: /create campaign/i })).not.toBeDisabled()
  })

  it('calls createCampaign and onCreated after submit', async () => {
    const onCreated = vi.fn()
    render(<CampaignForm onCreated={onCreated} />)
    fireEvent.change(screen.getByPlaceholderText(/senior engineer/i), { target: { value: 'My Campaign' } })
    await waitFor(() => {
      fireEvent.click(screen.getByRole('button', { name: 'Engineering' }))
    })
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: /create campaign/i }))
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 'new-c' })))
  })
})
