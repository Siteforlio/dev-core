import { useState, useCallback } from 'react'
import { apiFetch } from '../lib/apiFetch'

export interface IntegrationStatus {
  googleConfigured: boolean
  microsoftConfigured: boolean
  linkedinConfigured: boolean
}

export interface OAuthSetup {
  google_ready: boolean
  microsoft_ready: boolean
}

export function useIntegrations() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null)
  const [setup, setSetup] = useState<OAuthSetup | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const getStatus = useCallback(async (): Promise<IntegrationStatus> => {
    const res = await apiFetch('/api/v1/integrations/status')
    const json = await res.json()
    const s: IntegrationStatus = {
      googleConfigured: json.data.google_configured,
      microsoftConfigured: json.data.microsoft_configured,
      linkedinConfigured: json.data.linkedin_configured,
    }
    setStatus(s)
    return s
  }, [])

  const getSetup = useCallback(async (): Promise<OAuthSetup> => {
    const res = await apiFetch('/api/v1/integrations/oauth/setup')
    const json = await res.json()
    setSetup(json.data)
    return json.data
  }, [])

  const connectGoogle = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/api/v1/integrations/oauth/google/url')
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || 'Failed to get Google auth URL')
      await (window as any).electronAPI?.openExternal(json.data.url)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const connectMicrosoft = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/api/v1/integrations/oauth/microsoft/url')
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || 'Failed to get Microsoft auth URL')
      await (window as any).electronAPI?.openExternal(json.data.url)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const disconnectGoogle = useCallback(async () => {
    await apiFetch('/api/v1/integrations/oauth/google', { method: 'DELETE' })
    await getStatus()
  }, [getStatus])

  const disconnectMicrosoft = useCallback(async () => {
    await apiFetch('/api/v1/integrations/oauth/microsoft', { method: 'DELETE' })
    await getStatus()
  }, [getStatus])

  const setLinkedIn = useCallback(async (body: Record<string, string>) => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/api/v1/integrations/linkedin', {
        method: 'PUT',
        body: JSON.stringify(body),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || 'Failed to save LinkedIn credentials')
      await getStatus()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [getStatus])

  const testLinkedIn = useCallback(async (body: Record<string, string>) => {
    const res = await apiFetch('/api/v1/integrations/linkedin/test', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    const json = await res.json()
    if (!res.ok) throw new Error(json.detail || 'LinkedIn test failed')
    return json.data
  }, [])

  return {
    status,
    setup,
    loading,
    error,
    getStatus,
    getSetup,
    connectGoogle,
    connectMicrosoft,
    disconnectGoogle,
    disconnectMicrosoft,
    setLinkedIn,
    testLinkedIn,
  }
}
