import { useAuthStore } from '../store/authStore'
import { apiFetch } from '../lib/apiFetch'

const BASE = '/api/v1'

export function useIntegrations() {
  const token = useAuthStore((s) => s.accessToken)
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }

  async function getStatus(): Promise<{ emailConfigured: boolean; caldavConfigured: boolean; linkedinConfigured: boolean }> {
    const res = await apiFetch(`${BASE}/integrations/status`, { headers })
    const { data } = await res.json()
    return {
      emailConfigured: data.email_configured,
      caldavConfigured: data.caldav_configured,
      linkedinConfigured: data.linkedin_configured,
    }
  }

  async function testEmail(creds: { host: string; port: number; username: string; password: string; smtp_host?: string; smtp_port?: number }): Promise<void> {
    const res = await apiFetch(`${BASE}/integrations/email/test`, { method: 'POST', headers, body: JSON.stringify(creds) })
    if (!res.ok) { const b = await res.json().catch(() => null); throw new Error(b?.detail ?? `HTTP ${res.status}`) }
  }

  async function setEmail(creds: { host: string; port: number; username: string; password: string; smtp_host?: string; smtp_port?: number }): Promise<void> {
    const res = await apiFetch(`${BASE}/integrations/email`, { method: 'PUT', headers, body: JSON.stringify(creds) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function testCalDAV(creds: { url: string; username: string; password: string }): Promise<string> {
    const res = await apiFetch(`${BASE}/integrations/caldav/test`, { method: 'POST', headers, body: JSON.stringify(creds) })
    if (!res.ok) { const b = await res.json().catch(() => null); throw new Error(b?.detail ?? `HTTP ${res.status}`) }
    const { data } = await res.json()
    return data.message as string
  }

  async function setCalDAV(creds: { url: string; username: string; password: string }): Promise<void> {
    const res = await apiFetch(`${BASE}/integrations/caldav`, { method: 'PUT', headers, body: JSON.stringify(creds) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  async function testLinkedIn(creds: { email?: string; password?: string; session_cookie?: string }): Promise<void> {
    const res = await apiFetch(`${BASE}/integrations/linkedin/test`, { method: 'POST', headers, body: JSON.stringify(creds) })
    if (!res.ok) { const b = await res.json().catch(() => null); throw new Error(b?.detail ?? `HTTP ${res.status}`) }
  }

  async function setLinkedIn(creds: { email?: string; password?: string; session_cookie?: string }): Promise<void> {
    const res = await apiFetch(`${BASE}/integrations/linkedin`, { method: 'PUT', headers, body: JSON.stringify(creds) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  }

  return { getStatus, testEmail, setEmail, testCalDAV, setCalDAV, testLinkedIn, setLinkedIn }
}
