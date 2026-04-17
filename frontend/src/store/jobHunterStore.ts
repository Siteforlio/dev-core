import { create } from 'zustand'

export type ActiveView = 'campaigns' | 'profile' | 'create-campaign' | 'build-profile' | 'dashboard'

interface JobHunterState {
  selectedCampaignId: string | null
  activeView: ActiveView
  selectCampaign: (id: string) => void
  setActiveView: (view: ActiveView) => void
  reset: () => void
}

export const useJobHunterStore = create<JobHunterState>((set) => ({
  selectedCampaignId: null,
  activeView: 'campaigns',
  selectCampaign: (id) => set({ selectedCampaignId: id, activeView: 'dashboard' }),
  setActiveView: (view) => set({ activeView: view }),
  reset: () => set({ selectedCampaignId: null, activeView: 'campaigns' }),
}))
