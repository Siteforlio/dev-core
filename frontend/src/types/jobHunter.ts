export interface WorkExperience {
  company: string
  title: string
  startDate: string
  endDate: string | null
  responsibilities: string[]
}

export interface Education {
  degree: string
  institution: string
  fieldOfStudy: string
  graduationYear: number
}

export interface Project {
  name: string
  description: string
  techStack: string[]
  link: string | null
}

export interface Campaign {
  id: string
  name: string
  status: 'active' | 'paused' | 'archived'
  broadCategory: string
  subCategories: string[]
}

export interface CampaignSummary {
  totalApplications: number
  todayApplications: number
  weekApplications: number
  responses: number
  interviews: number
  offers: number
  rejectionRate: number
}

export interface Application {
  id: string
  company: string
  title: string
  location: string
  appliedAt: string
  status: 'pending' | 'applied' | 'responded' | 'interview' | 'offer' | 'rejected' | 'failed' | 'withdrawn'
  matchScore: 'MATCH' | 'PARTIAL' | 'SKIP' | null
  source: string
}

export interface ScheduledInterview {
  applicationId: string
  company: string
  role: string
  scheduledAt: string
}

export interface InterviewContext {
  managers: { name: string; title: string; traits: string[] }[]
  roundPatterns: { rounds: string[] }
  personaString: string
  company: string
  role: string
  applicationId: string
}

export type BoardStatusState = 'idle' | 'queued' | 'running' | 'done' | 'failed'

export interface BoardStatus {
  status: BoardStatusState
  count: number
  error: string | null
  updated_at: string
}

export interface ScrapeRunStatus {
  status: 'running' | 'done'
  matches: number
  round: number
  started_at: string
  updated_at: string
}

export interface ScrapePreferences {
  companyTypes: ('faang' | 'enterprise' | 'startup' | 'sme')[]
  workType: 'remote' | 'hybrid' | 'onsite' | 'any'
  regions: ('global' | 'africa' | 'kenya')[]
  dailyTarget: number
}
