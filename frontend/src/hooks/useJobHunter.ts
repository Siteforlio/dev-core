import { useAuthStore } from '../store/authStore'
import type {
  Campaign,
  CampaignSummary,
  Application,
  ScheduledInterview,
  InterviewContext,
  JobHunterProfile,
} from '../types/jobHunter'

const BASE = '/api/v1'

export function useJobHunter() {
  const token = useAuthStore((s) => s.accessToken)

  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }

  async function getProfile(): Promise<JobHunterProfile> {
    const res = await fetch(`${BASE}/job-hunter/profiles/me`, { headers })
    const { data } = await res.json()
    return {
      id: data.id,
      isComplete: data.is_complete,
      completionScore: data.completion_score,
      missingFields: data.missing_fields ?? [],
      fullName: data.full_name ?? null,
      email: data.email ?? null,
      phone: data.phone ?? null,
      city: data.city ?? null,
      country: data.country ?? null,
      linkedinUrl: data.linkedin_url ?? null,
      githubUrl: data.github_url ?? null,
      skills: data.skills ?? [],
      workExperience: data.work_experience ?? [],
      education: data.education ?? [],
      projects: data.projects ?? [],
    }
  }

  async function upsertProfile(
    fields: Record<string, unknown>
  ): Promise<{ isComplete: boolean; completionScore: number; missingFields: string[] }> {
    // Pydantic v2 rejects explicit null for list[...] fields — null must become []
    // Skills from Haiku may arrive as a comma-separated string instead of an array
    const sanitized: Record<string, unknown> = { ...fields }
    const listFields = ['work_experience', 'education', 'projects', 'languages_spoken'] as const
    for (const key of listFields) {
      if (!Array.isArray(sanitized[key])) sanitized[key] = []
    }
    if (!Array.isArray(sanitized.skills)) {
      sanitized.skills =
        typeof sanitized.skills === 'string'
          ? (sanitized.skills as string).split(',').map((s) => s.trim()).filter(Boolean)
          : []
    }

    const res = await fetch(`${BASE}/job-hunter/profiles/me`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(sanitized),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      const detail = body?.detail ?? body?.error?.message ?? `HTTP ${res.status}`
      throw new Error(detail)
    }
    const { data } = await res.json()
    return {
      isComplete: data.is_complete,
      completionScore: data.completion_score,
      missingFields: data.missing_fields ?? [],
    }
  }

  async function parseResume(text: string): Promise<Record<string, unknown>> {
    const res = await fetch(`${BASE}/job-hunter/profiles/me/parse-resume`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ text }),
    })
    const { data } = await res.json()
    return data
  }

  async function listCampaigns(): Promise<Campaign[]> {
    const res = await fetch(`${BASE}/job-hunter/campaigns`, { headers })
    const { data } = await res.json()
    return (data ?? []).map((c: Record<string, unknown>) => ({
      id: c.id,
      name: c.name,
      status: c.status,
      broadCategory: c.broad_category,
      subCategories: c.sub_categories ?? [],
    })) as Campaign[]
  }

  async function createCampaign(body: {
    name: string
    broadCategory: string
    userCountry: string
  }): Promise<Campaign> {
    const res = await fetch(`${BASE}/job-hunter/campaigns`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        name: body.name,
        broad_category: body.broadCategory,
        user_country: body.userCountry,
      }),
    })
    const { data } = await res.json()
    return {
      id: data.id,
      name: data.name,
      status: data.status,
      broadCategory: body.broadCategory,
      subCategories: data.sub_categories ?? [],
    }
  }

  async function setCampaignStatus(
    campaignId: string,
    status: 'active' | 'paused' | 'archived'
  ): Promise<void> {
    await fetch(`${BASE}/job-hunter/campaigns/${campaignId}/status`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ status }),
    })
  }

  async function getDashboard(campaignId: string): Promise<{
    summary: CampaignSummary
    pipeline: Application[]
    interviews: ScheduledInterview[]
  }> {
    const res = await fetch(`${BASE}/job-hunter/campaigns/${campaignId}/dashboard`, { headers })
    const { data } = await res.json()
    return {
      summary: {
        totalApplications: data.summary.total_applications ?? 0,
        todayApplications: data.summary.today_applications ?? 0,
        weekApplications: data.summary.week_applications ?? 0,
        responses: data.summary.responses ?? 0,
        interviews: data.summary.interviews ?? 0,
        offers: data.summary.offers ?? 0,
        rejectionRate: data.summary.rejection_rate ?? 0,
      },
      pipeline: (data.pipeline ?? []).map((a: Record<string, unknown>) => ({
        id: a.id,
        company: a.company,
        title: a.title,
        location: a.location ?? '',
        appliedAt: a.applied_at ?? '',
        status: a.status,
        matchScore: a.match_score ?? null,
        source: a.source ?? '',
      })) as Application[],
      interviews: (data.interviews ?? []).map((i: Record<string, unknown>) => ({
        applicationId: i.application_id,
        company: i.company,
        role: i.role,
        scheduledAt: i.scheduled_at,
      })) as ScheduledInterview[],
    }
  }

  async function getInterviewContext(
    campaignId: string,
    applicationId: string
  ): Promise<InterviewContext> {
    const res = await fetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/interview-context`,
      { headers }
    )
    const { data } = await res.json()
    return {
      managers: data.managers ?? [],
      roundPatterns: data.round_patterns ?? {},
      personaString: data.persona_string ?? '',
      company: data.company,
      role: data.role,
      applicationId: data.application_id,
    }
  }

  return {
    getProfile,
    upsertProfile,
    parseResume,
    listCampaigns,
    createCampaign,
    setCampaignStatus,
    getDashboard,
    getInterviewContext,
  }
}
