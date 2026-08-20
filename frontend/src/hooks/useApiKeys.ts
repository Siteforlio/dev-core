import { apiFetch } from '../lib/apiFetch'

const BASE = '/api/v1'

export interface ApiKeyInfo {
  key_name: string
  configured: boolean
  required: boolean
  updated_at: string | null
}

export function useApiKeys() {
  async function getStatus(): Promise<ApiKeyInfo[]> {
    const res = await apiFetch(`${BASE}/settings/api-keys/status`)
    const { data } = await res.json()
    return data.keys as ApiKeyInfo[]
  }

  async function setKey(keyName: string, value: string): Promise<void> {
    const res = await apiFetch(`${BASE}/settings/api-keys/${keyName}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    })
    if (!res.ok) {
      const b = await res.json().catch(() => null)
      throw new Error(b?.detail ?? `HTTP ${res.status}`)
    }
  }

  async function deleteKey(keyName: string): Promise<void> {
    const res = await apiFetch(`${BASE}/settings/api-keys/${keyName}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const b = await res.json().catch(() => null)
      throw new Error(b?.detail ?? `HTTP ${res.status}`)
    }
  }

  return { getStatus, setKey, deleteKey }
}
