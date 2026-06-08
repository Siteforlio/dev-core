import { useAuthStore } from '../store/authStore'
import { apiFetch } from '../lib/apiFetch'
import type {
  Campaign,
  CampaignSummary,
  Application,
  ScheduledInterview,
  InterviewContext,
  ScrapePreferences,
  BoardStatus,
  ScrapeRunStatus,
  ApplicationDetail,
  ChatMessage,
  TrackingStatus,
} from '../types/jobHunter'

const BASE = '/api/v1'

export function useJobHunter() {
  const token = useAuthStore((s) => s.accessToken)

  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }

  async function listCampaigns(): Promise<Campaign[]> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns`, { headers })
    const { data } = await res.json()
    return (data ?? []).map((c: Record<string, unknown>) => ({
      id: c.id,
      name: c.name,
      status: c.status,
      broadCategory: c.broad_category,
      subCategories: c.sub_categories ?? [],
    })) as Campaign[]
  }

  async function getCampaignMeta(): Promise<{ categories: string[]; workTypes: string[] }> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/meta`, { headers })
    const { data } = await res.json()
    return { categories: data.categories, workTypes: data.work_types }
  }

  async function createCampaign(body: {
    name: string
    broadCategory?: string
    categories?: string[]
    userCountry?: string
    anywhere?: boolean
    workType?: string
    workTypes?: string[]
  }): Promise<Campaign> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        name: body.name,
        broad_category: body.broadCategory ?? null,
        categories: body.categories ?? [],
        user_country: body.userCountry ?? null,
        anywhere: body.anywhere ?? false,
        work_type: body.workType ?? 'remote',
        work_types: body.workTypes ?? [],
      }),
    })
    if (!res.ok) {
      const b = await res.json().catch(() => null)
      throw new Error(b?.detail ?? `HTTP ${res.status}`)
    }
    const { data } = await res.json()
    return {
      id: data.id,
      name: data.name,
      status: data.status,
      broadCategory: data.broad_category,
      subCategories: data.sub_categories ?? [],
      workType: data.work_type,
      anywhere: data.anywhere,
      userCountry: data.user_country,
    }
  }

  async function getCampaignProfile(campaignId: string): Promise<Record<string, unknown>> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/profile`, { headers })
    const { data } = await res.json()
    return data
  }

  async function upsertCampaignProfile(campaignId: string, data: Record<string, unknown>): Promise<void> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/profile`, {
      method: 'PUT', headers, body: JSON.stringify(data),
    })
    if (!res.ok) {
      const b = await res.json().catch(() => null)
      throw new Error(b?.detail ?? `HTTP ${res.status}`)
    }
  }

  async function analyzeProfileGaps(campaignId: string): Promise<{
    score: number; is_ready: boolean; gaps: string[]; questions: { gap: string; question: string }[]; summary: string
  }> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/profile/analyze`, {
      method: 'POST', headers,
    })
    const { data } = await res.json()
    return data
  }

  async function processRawContext(campaignId: string, rawContext: string): Promise<{
    extracted: Record<string, unknown>; gaps: { score: number; is_ready: boolean; gaps: string[]; questions: { gap: string; question: string }[] }
  }> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/profile/context`, {
      method: 'POST', headers, body: JSON.stringify({ raw_context: rawContext }),
    })
    if (!res.ok) {
      const b = await res.json().catch(() => null)
      throw new Error(b?.detail ?? `HTTP ${res.status}`)
    }
    const { data } = await res.json()
    return data
  }

  async function processContextFile(campaignId: string, file: File): Promise<{
    extracted: Record<string, unknown>; gaps: { score: number; is_ready: boolean; gaps: string[]; questions: { gap: string; question: string }[] }
  }> {
    const form = new FormData()
    form.append('file', file)
    const token = useAuthStore.getState().accessToken
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/profile/context/file`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },  // no Content-Type — browser sets multipart boundary
      body: form,
    })
    if (!res.ok) {
      const b = await res.json().catch(() => null)
      const detail = b?.detail
      const msg = Array.isArray(detail)
        ? detail.map((d: Record<string, unknown>) => d?.msg ?? String(d)).join('; ')
        : typeof detail === 'string' ? detail : `HTTP ${res.status}`
      throw new Error(msg)
    }
    const { data } = await res.json()
    return data
  }

  async function triggerScrape(campaignId: string, prefs?: Partial<ScrapePreferences>): Promise<void> {
    const body: Record<string, unknown> = {}
    if (prefs?.companyTypes?.length)   body.company_types  = prefs.companyTypes
    if (prefs?.workType)               body.work_type      = prefs.workType
    if (prefs?.regions?.length)        body.regions        = prefs.regions
    if (prefs?.dailyTarget)            body.daily_target   = prefs.dailyTarget

    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/scrape`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const b = await res.json().catch(() => null)
      throw new Error(b?.detail ?? `HTTP ${res.status}`)
    }
  }

  async function getScrapeStatus(campaignId: string): Promise<{
    run: ScrapeRunStatus | null
    boards: Record<string, BoardStatus>
  }> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/scrape/status`, { headers })
    if (!res.ok) return { run: null, boards: {} }
    const { data } = await res.json()
    return { run: data.run ?? null, boards: data.boards ?? {} }
  }

  async function ensureApplication(campaignId: string, listingId: string): Promise<string> {
    const res = await apiFetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/listings/${listingId}/ensure-application`,
      { method: 'POST', headers },
    )
    if (!res.ok) {
      const b = await res.json().catch(() => null)
      throw new Error(b?.detail ?? `HTTP ${res.status}`)
    }
    const { data } = await res.json()
    return data.application_id as string
  }

  async function stopScrape(campaignId: string): Promise<void> {
    await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/scrape/stop`, {
      method: 'POST',
      headers,
    })
  }

  async function setCampaignStatus(
    campaignId: string,
    status: 'active' | 'paused' | 'archived'
  ): Promise<void> {
    await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/status`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ status }),
    })
  }

  async function getDashboard(campaignId: string): Promise<{
    summary: CampaignSummary
    pipeline: Application[]
    interviews: ScheduledInterview[]
    activityLog: { message: string; createdAt: string }[]
  }> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/dashboard`, { headers })
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
        applicationId: a.application_id ?? null,
        company: a.company,
        title: a.title,
        location: a.location ?? '',
        appliedAt: a.applied_at ?? a.discovered_at ?? '',
        status: a.status,
        matchScore: a.match_score ?? null,
        source: a.source ?? '',
        appliedElsewhere: a.applied_elsewhere === true,
      })) as Application[],
      interviews: (data.interviews ?? []).map((i: Record<string, unknown>) => ({
        applicationId: i.application_id,
        company: i.company,
        role: i.role,
        scheduledAt: i.scheduled_at,
      })) as ScheduledInterview[],
      activityLog: (data.activity_log ?? []).map((l: Record<string, unknown>) => ({
        message: l.message as string,
        createdAt: l.created_at as string,
      })),
    }
  }

  async function getInterviewContext(
    campaignId: string,
    applicationId: string
  ): Promise<InterviewContext> {
    const res = await apiFetch(
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

  async function getCredentialsStatus(campaignId: string): Promise<{ emailConfigured: boolean; caldavConfigured: boolean; linkedinConfigured: boolean }> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/credentials/status`, { headers })
    const { data } = await res.json()
    return {
      emailConfigured: data.email_configured,
      caldavConfigured: data.caldav_configured,
      linkedinConfigured: data.linkedin_configured ?? false,
    }
  }

  async function testEmailCredentials(campaignId: string, creds: {
    host: string; port: number; username: string; password: string; smtp_host?: string; smtp_port?: number
  }): Promise<void> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/credentials/email/test`, {
      method: 'POST', headers, body: JSON.stringify(creds),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new Error(body?.detail ?? `HTTP ${res.status}`)
    }
  }

  async function setEmailCredentials(campaignId: string, creds: {
    host: string; port: number; username: string; password: string; smtp_host?: string; smtp_port?: number
  }): Promise<void> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/credentials/email`, {
      method: 'PUT', headers, body: JSON.stringify(creds),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function testCalDAVCredentials(campaignId: string, creds: {
    url: string; username: string; password: string
  }): Promise<string> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/credentials/caldav/test`, {
      method: 'POST', headers, body: JSON.stringify(creds),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new Error(body?.detail ?? `HTTP ${res.status}`)
    }
    const { data } = await res.json()
    return data.message as string
  }

  async function setCalDAVCredentials(campaignId: string, creds: {
    url: string; username: string; password: string
  }): Promise<void> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/credentials/caldav`, {
      method: 'PUT', headers, body: JSON.stringify(creds),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function testLinkedInCredentials(campaignId: string, creds: {
    email?: string; password?: string; session_cookie?: string
  }): Promise<void> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/credentials/linkedin/test`, {
      method: 'POST', headers, body: JSON.stringify(creds),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new Error(body?.detail ?? `HTTP ${res.status}`)
    }
  }

  async function setLinkedInCredentials(campaignId: string, creds: {
    email?: string; password?: string; session_cookie?: string
  }): Promise<void> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/credentials/linkedin`, {
      method: 'PUT', headers, body: JSON.stringify(creds),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function setCampaignToggles(campaignId: string, toggles: { email_enabled?: boolean; caldav_enabled?: boolean; linkedin_enabled?: boolean }): Promise<void> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/toggles`, {
      method: 'PATCH', headers, body: JSON.stringify(toggles),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function deleteCampaign(campaignId: string): Promise<void> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}`, {
      method: 'DELETE', headers,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  // ── Apply panel ─────────────────────────────────────────────────────────────

  async function getApplicationDetail(campaignId: string, applicationId: string): Promise<ApplicationDetail> {
    const res = await apiFetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/detail`,
      { headers }
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const { data } = await res.json()
    return {
      applicationId: data.application_id,
      status: data.status,
      company: data.company,
      title: data.title,
      location: data.location ?? '',
      applyUrl: data.apply_url ?? null,
      campaignName: data.campaign_name ?? '',
      resumePath: data.resume_path ?? null,
      resumeFolder: data.resume_folder ?? null,
      resumeFilename: data.resume_filename ?? null,
      coverLetter: data.cover_letter ?? null,
      appliedAt: data.applied_at ?? null,
      statusUpdatedAt: data.status_updated_at ?? null,
      description: data.description ?? null,
    }
  }

  async function triggerTailoring(campaignId: string, applicationId: string): Promise<void> {
    const res = await apiFetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/tailor`,
      { method: 'POST', headers }
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function patchApplicationStatus(
    campaignId: string,
    applicationId: string,
    status: Application['status'],
    notes?: string
  ): Promise<void> {
    const res = await apiFetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/status`,
      {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ status, notes }),
      }
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function generateCoverLetter(campaignId: string, applicationId: string): Promise<string> {
    const res = await apiFetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/cover-letter`,
      { method: 'POST', headers }
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const { data } = await res.json()
    return data.cover_letter as string
  }

  async function chatWithApplication(
    campaignId: string,
    applicationId: string,
    message: string,
    history: ChatMessage[]
  ): Promise<string> {
    const res = await apiFetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/chat`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({ message, history }),
      }
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const { data } = await res.json()
    return data.reply as string
  }

  async function openInChrome(campaignId: string, applicationId: string): Promise<void> {
    const res = await apiFetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/open-in-chrome`,
      { method: 'POST', headers }
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function scanEmails(campaignId: string): Promise<{ noCredentials: boolean }> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/email/scan`, {
      method: 'POST', headers,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const { data } = await res.json()
    return { noCredentials: data.no_credentials ?? false }
  }

  async function addManualJob(
    campaignId: string,
    job: { title: string; company: string; description: string; applyUrl?: string; location?: string }
  ): Promise<{ listingId: string }> {
    const res = await apiFetch(`${BASE}/job-hunter/campaigns/${campaignId}/jobs/manual`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        title: job.title,
        company: job.company,
        description: job.description,
        apply_url: job.applyUrl ?? null,
        location: job.location ?? null,
      }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body?.detail ?? `HTTP ${res.status}`)
    }
    const { data } = await res.json()
    return { listingId: data.listing_id }
  }

  async function getTrackingStatus(campaignId: string, applicationId: string): Promise<TrackingStatus> {
    const res = await apiFetch(
      `${BASE}/job-hunter/campaigns/${campaignId}/applications/${applicationId}/tracking`,
      { headers }
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const { data } = await res.json()
    return {
      applicationId: data.application_id,
      status: data.status,
      appliedAt: data.applied_at ?? null,
      statusUpdatedAt: data.status_updated_at ?? null,
      company: data.company,
      title: data.title,
      emailEvents: (data.email_events ?? []).map((e: Record<string, unknown>) => ({
        id: e.id,
        subject: e.subject,
        sender: e.sender,
        classification: e.classification,
        receivedAt: e.received_at,
      })),
    }
  }

  return {
    listCampaigns,
    getCampaignMeta,
    createCampaign,
    getCampaignProfile,
    upsertCampaignProfile,
    analyzeProfileGaps,
    processRawContext,
    processContextFile,
    triggerScrape,
    getScrapeStatus,
    stopScrape,
    ensureApplication,
    setCampaignStatus,
    getDashboard,
    getInterviewContext,
    getCredentialsStatus,
    testEmailCredentials,
    setEmailCredentials,
    testCalDAVCredentials,
    setCalDAVCredentials,
    testLinkedInCredentials,
    setLinkedInCredentials,
    setCampaignToggles,
    deleteCampaign,
    getApplicationDetail,
    patchApplicationStatus,
    triggerTailoring,
    generateCoverLetter,
    chatWithApplication,
    openInChrome,
    scanEmails,
    getTrackingStatus,
    addManualJob,
  }
}
