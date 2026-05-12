import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const mockUpsertProfile = vi.fn()
const mockParseResume = vi.fn()

vi.mock('../../../hooks/useJobHunter', () => ({
  useJobHunter: () => ({
    upsertProfile: mockUpsertProfile,
    parseResume: mockParseResume,
  }),
}))

// import after mock is set up
const { default: ProfileOnboarding } = await import('../../../components/job-hunter/ProfileOnboarding')

describe('ProfileOnboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUpsertProfile.mockResolvedValue({ isComplete: false, completionScore: 40, missingFields: ['skills', 'projects'] })
    mockParseResume.mockResolvedValue({ full_name: 'Jane Doe', email: 'jane@example.com', skills: ['React', 'TypeScript'] })
  })

  it('renders the onboarding heading', () => {
    render(<ProfileOnboarding onComplete={() => {}} />)
    expect(screen.getByText(/Let's set up your profile/i)).toBeInTheDocument()
  })

  it('shows resume paste textarea', () => {
    render(<ProfileOnboarding onComplete={() => {}} />)
    expect(screen.getByPlaceholderText(/paste your resume/i)).toBeInTheDocument()
  })

  it('parse button is disabled when textarea is empty', () => {
    render(<ProfileOnboarding onComplete={() => {}} />)
    expect(screen.getByRole('button', { name: /parse text/i })).toBeDisabled()
  })

  it('parse button enabled after typing in textarea', () => {
    render(<ProfileOnboarding onComplete={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText(/paste your resume/i), { target: { value: 'My resume' } })
    expect(screen.getByRole('button', { name: /parse text/i })).not.toBeDisabled()
  })

  it('calls parseResume when Parse Resume is clicked', async () => {
    render(<ProfileOnboarding onComplete={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText(/paste your resume/i), { target: { value: 'My resume text' } })
    fireEvent.click(screen.getByRole('button', { name: /parse text/i }))
    await waitFor(() => expect(mockParseResume).toHaveBeenCalledWith('My resume text'))
  })

  it('shows missing fields after save if profile incomplete', async () => {
    render(<ProfileOnboarding onComplete={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /save profile/i }))
    await waitFor(() => expect(screen.getByText(/skills/)).toBeInTheDocument())
  })

  it('calls onComplete when profile is complete', async () => {
    mockUpsertProfile.mockResolvedValue({ isComplete: true, completionScore: 100, missingFields: [] })
    const onComplete = vi.fn()
    render(<ProfileOnboarding onComplete={onComplete} />)
    fireEvent.click(screen.getByRole('button', { name: /save profile/i }))
    await waitFor(() => expect(onComplete).toHaveBeenCalled())
  })
})
