import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const mockCreateCampaign = vi.fn()

vi.mock('../../../hooks/useJobHunter', () => ({
  useJobHunter: () => ({
    createCampaign: mockCreateCampaign,
  }),
}))

const { default: CampaignForm } = await import('../../../components/job-hunter/CampaignForm')

describe('CampaignForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCreateCampaign.mockResolvedValue({
      id: 'new-c',
      name: 'My Campaign',
      status: 'active',
      broadCategory: 'Engineering',
      subCategories: ['Backend'],
    })
  })

  it('renders name, category, and country inputs', () => {
    render(<CampaignForm onCreated={() => {}} />)
    expect(screen.getByPlaceholderText(/campaign name/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/job category/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/country/i)).toBeInTheDocument()
  })

  it('launch button is disabled when fields are empty', () => {
    render(<CampaignForm onCreated={() => {}} />)
    expect(screen.getByRole('button', { name: /launch/i })).toBeDisabled()
  })

  it('launch button enables when all fields are filled', () => {
    render(<CampaignForm onCreated={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText(/campaign name/i), { target: { value: 'Hunt' } })
    fireEvent.change(screen.getByPlaceholderText(/job category/i), { target: { value: 'Engineering' } })
    fireEvent.change(screen.getByPlaceholderText(/country/i), { target: { value: 'US' } })
    expect(screen.getByRole('button', { name: /launch/i })).not.toBeDisabled()
  })

  it('calls createCampaign and onCreated after submit', async () => {
    const onCreated = vi.fn()
    render(<CampaignForm onCreated={onCreated} />)
    fireEvent.change(screen.getByPlaceholderText(/campaign name/i), { target: { value: 'My Campaign' } })
    fireEvent.change(screen.getByPlaceholderText(/job category/i), { target: { value: 'Software Engineering' } })
    fireEvent.change(screen.getByPlaceholderText(/country/i), { target: { value: 'US' } })
    fireEvent.click(screen.getByRole('button', { name: /launch/i }))
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 'new-c' })))
  })
})
