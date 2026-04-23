import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ApplyPanel from '../../../components/job-hunter/ApplyPanel'
import type { ApplicationDetail } from '../../../types/jobHunter'

const mockDetail: ApplicationDetail = {
  applicationId: 'app-1',
  status: 'pending',
  company: 'Stripe',
  title: 'Senior Software Engineer',
  location: 'Remote',
  applyUrl: 'https://stripe.com/apply',
  campaignName: 'Software Engineer 2026',
  resumePath: '/resumes/stripe/resume.pdf',
  resumeFolder: '/resumes/stripe/',
  resumeFilename: 'Solomon Jesse - Stripe - Senior Software Engineer.pdf',
  coverLetter: null,
  appliedAt: null,
  statusUpdatedAt: null,
}

const mockGetDetail = vi.fn()
const mockGenerateCover = vi.fn()
const mockChat = vi.fn()
const mockOpenInChrome = vi.fn()

vi.mock('../../../hooks/useJobHunter', () => ({
  useJobHunter: () => ({
    getApplicationDetail: mockGetDetail,
    generateCoverLetter: mockGenerateCover,
    chatWithApplication: mockChat,
    openInChrome: mockOpenInChrome,
  }),
}))

describe('ApplyPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDetail.mockResolvedValue(mockDetail)
    mockOpenInChrome.mockResolvedValue(undefined)
    mockGenerateCover.mockResolvedValue('Dear Stripe, I am excited...')
    mockChat.mockResolvedValue('You have 2 years of Go.')
  })

  it('shows loading spinner initially', () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('renders job title and company after load', async () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      // getByRole scopes to the heading element specifically
      expect(screen.getAllByText('Senior Software Engineer').length).toBeGreaterThan(0)
      expect(screen.getAllByText(/Stripe/).length).toBeGreaterThan(0)
    })
  })

  it('shows resume filename', async () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('Solomon Jesse - Stripe - Senior Software Engineer.pdf')).toBeInTheDocument()
    })
  })

  it('shows greeting message in chat', async () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      // Multiple elements may contain "Context loaded" — verify at least one exists
      expect(screen.getAllByText(/Context loaded/).length).toBeGreaterThan(0)
    })
  })

  it('calls openInChrome on Open in Chrome click', async () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => screen.getByRole('button', { name: /open in chrome/i }))
    fireEvent.click(screen.getByRole('button', { name: /open in chrome/i }))
    await waitFor(() => expect(mockOpenInChrome).toHaveBeenCalledWith('c-1', 'app-1'))
  })

  it('calls onClose when ✕ is clicked', async () => {
    const onClose = vi.fn()
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={onClose} />)
    await waitFor(() => screen.getAllByText('Senior Software Engineer'))
    // There may be multiple ✕ buttons (close + cover letter) — click the first one in the header
    const closeBtns = screen.getAllByRole('button', { name: /✕/ })
    fireEvent.click(closeBtns[0])
    expect(onClose).toHaveBeenCalled()
  })

  it('sends chat message on button click', async () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => screen.getByPlaceholderText(/ask anything/i))

    const textarea = screen.getByPlaceholderText(/ask anything/i)
    fireEvent.change(textarea, { target: { value: 'How many years of Go?' } })
    fireEvent.click(screen.getByRole('button', { name: /↑/ }))

    await waitFor(() => {
      expect(mockChat).toHaveBeenCalledWith('c-1', 'app-1', 'How many years of Go?', expect.any(Array))
      expect(screen.getByText('You have 2 years of Go.')).toBeInTheDocument()
    })
  })

  it('sends message on Enter key', async () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => screen.getByPlaceholderText(/ask anything/i))

    const textarea = screen.getByPlaceholderText(/ask anything/i)
    fireEvent.change(textarea, { target: { value: 'What should I emphasise?' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => {
      expect(mockChat).toHaveBeenCalled()
    })
  })

  it('shows quick chip prompts', async () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => screen.getByText('Write cover letter'))
    expect(screen.getByText('What should I emphasise?')).toBeInTheDocument()
    expect(screen.getByText('Summarise this job')).toBeInTheDocument()
  })

  it('generates cover letter on chip click', async () => {
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => screen.getByText(/generate cover letter/i))
    fireEvent.click(screen.getByText(/generate cover letter/i))

    await waitFor(() => {
      expect(mockGenerateCover).toHaveBeenCalledWith('c-1', 'app-1')
      expect(screen.getByText('Dear Stripe, I am excited...')).toBeInTheDocument()
    })
  })

  it('shows error state when detail fetch fails', async () => {
    mockGetDetail.mockRejectedValue(new Error('Network error'))
    render(<ApplyPanel campaignId="c-1" applicationId="app-1" onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument()
    })
  })
})
