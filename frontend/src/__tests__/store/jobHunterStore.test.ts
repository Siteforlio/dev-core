import { describe, it, expect, beforeEach } from 'vitest'
import { useJobHunterStore } from '../../store/jobHunterStore'

describe('jobHunterStore', () => {
  beforeEach(() => {
    useJobHunterStore.setState({
      selectedCampaignId: null,
      profileComplete: false,
      activeView: 'campaigns',
    })
  })

  it('starts with no selected campaign', () => {
    expect(useJobHunterStore.getState().selectedCampaignId).toBeNull()
  })

  it('selectCampaign sets the campaign id and navigates to dashboard', () => {
    useJobHunterStore.getState().selectCampaign('camp-1')
    expect(useJobHunterStore.getState().selectedCampaignId).toBe('camp-1')
    expect(useJobHunterStore.getState().activeView).toBe('dashboard')
  })

  it('setProfileComplete updates profileComplete', () => {
    useJobHunterStore.getState().setProfileComplete(true)
    expect(useJobHunterStore.getState().profileComplete).toBe(true)
  })

  it('setActiveView transitions between views', () => {
    useJobHunterStore.getState().setActiveView('dashboard')
    expect(useJobHunterStore.getState().activeView).toBe('dashboard')
  })

  it('reset clears selectedCampaignId and activeView', () => {
    useJobHunterStore.getState().selectCampaign('camp-1')
    useJobHunterStore.getState().reset()
    expect(useJobHunterStore.getState().selectedCampaignId).toBeNull()
    expect(useJobHunterStore.getState().activeView).toBe('campaigns')
  })
})
