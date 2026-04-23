import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import DidYouApplyPopup from '../../../components/job-hunter/DidYouApplyPopup'

// Mock useJobHunter
const mockPatchStatus = vi.fn()
vi.mock('../../../hooks/useJobHunter', () => ({
  useJobHunter: () => ({
    patchApplicationStatus: mockPatchStatus,
  }),
}))

const defaultProps = {
  campaignId: 'camp-1',
  applicationId: 'app-1',
  company: 'Stripe',
  title: 'Senior Engineer',
  onDone: vi.fn(),
  onDismiss: vi.fn(),
}

describe('DidYouApplyPopup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPatchStatus.mockResolvedValue(undefined)
  })

  it('renders company and title', () => {
    render(<DidYouApplyPopup {...defaultProps} />)
    expect(screen.getByText('Stripe · Senior Engineer')).toBeInTheDocument()
  })

  it('shows yes, failed, and later buttons', () => {
    render(<DidYouApplyPopup {...defaultProps} />)
    expect(screen.getByRole('button', { name: /yes, applied/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /failed/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /later/i })).toBeInTheDocument()
  })

  it('calls patchApplicationStatus with applied and triggers onDone', async () => {
    const onDone = vi.fn()
    render(<DidYouApplyPopup {...defaultProps} onDone={onDone} />)
    fireEvent.click(screen.getByRole('button', { name: /yes, applied/i }))
    await waitFor(() => {
      expect(mockPatchStatus).toHaveBeenCalledWith('camp-1', 'app-1', 'applied', undefined)
      expect(onDone).toHaveBeenCalledWith('applied')
    })
  })

  it('calls patchApplicationStatus with failed', async () => {
    const onDone = vi.fn()
    render(<DidYouApplyPopup {...defaultProps} onDone={onDone} />)
    fireEvent.click(screen.getByRole('button', { name: /failed/i }))
    await waitFor(() => {
      expect(mockPatchStatus).toHaveBeenCalledWith('camp-1', 'app-1', 'failed', undefined)
      expect(onDone).toHaveBeenCalledWith('failed')
    })
  })

  it('calls onDismiss when Later is clicked', () => {
    const onDismiss = vi.fn()
    render(<DidYouApplyPopup {...defaultProps} onDismiss={onDismiss} />)
    fireEvent.click(screen.getByRole('button', { name: /later/i }))
    expect(onDismiss).toHaveBeenCalled()
    expect(mockPatchStatus).not.toHaveBeenCalled()
  })

  it('passes notes to patchApplicationStatus when provided', async () => {
    const onDone = vi.fn()
    render(<DidYouApplyPopup {...defaultProps} onDone={onDone} />)
    fireEvent.change(screen.getByPlaceholderText(/any notes/i), {
      target: { value: 'Submitted via Workday' },
    })
    fireEvent.click(screen.getByRole('button', { name: /yes, applied/i }))
    await waitFor(() => {
      expect(mockPatchStatus).toHaveBeenCalledWith('camp-1', 'app-1', 'applied', 'Submitted via Workday')
    })
  })

  it('still calls onDone even when patchApplicationStatus throws', async () => {
    mockPatchStatus.mockRejectedValue(new Error('Network error'))
    const onDone = vi.fn()
    render(<DidYouApplyPopup {...defaultProps} onDone={onDone} />)
    fireEvent.click(screen.getByRole('button', { name: /yes, applied/i }))
    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith('applied')
    })
  })
})
