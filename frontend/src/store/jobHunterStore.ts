import { create } from 'zustand'

export type ActiveView = 'campaigns' | 'profile' | 'create-campaign' | 'dashboard'

interface JobHunterState {
  selectedCampaignId: string | null
  profileComplete: boolean
  activeView: ActiveView
  selectCampaign: (id: string) => void
  setProfileComplete: (complete: boolean) => void
  setActiveView: (view: ActiveView) => void
  reset: () => void
}

export const useJobHunterStore = create<JobHunterState>((set) => ({
  selectedCampaignId: null,
  profileComplete: false,
  activeView: 'campaigns',
  selectCampaign: (id) => set({ selectedCampaignId: id, activeView: 'dashboard' }),
  setProfileComplete: (complete) => set({ profileComplete: complete }),
  setActiveView: (view) => set({ activeView: view }),
  reset: () => set({ selectedCampaignId: null, activeView: 'campaigns' }),
}))
