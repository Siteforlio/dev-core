/**
 * Drop-in fetch wrapper that auto-refreshes the access token on 401.
 * If refresh also fails, clears auth and forces re-login.
 */
import { useAuthStore } from '../store/authStore'
import { API_BASE, API_ROOT } from './apiBase'

let refreshing: Promise<string | null> | null = null

export async function attemptRefresh(): Promise<string | null> {
  const { refreshToken, setAccessToken, clearAuth } = useAuthStore.getState()
  const electronAPI = (window as any).electronAPI

  try {
    // In Electron, the main process holds the refresh token (loaded from safeStorage on startup).
    // Delegate to it directly — don't guard on the Zustand refreshToken which may be empty
    // on first startup before the store is hydrated.
    if (electronAPI?.refreshToken) {
      const result = await electronAPI.refreshToken()
      if (!result?.accessToken) { clearAuth(); return null }
      setAccessToken(result.accessToken)
      if (result.refreshToken) useAuthStore.setState({ refreshToken: result.refreshToken })
      return result.accessToken
    }

    // Non-Electron fallback (plain browser dev mode)
    if (!refreshToken) { clearAuth(); return null }
    const res = await fetch(`${API_BASE()}/auth/refresh`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${refreshToken}` },
    })
    if (!res.ok) { clearAuth(); return null }
    const { data } = await res.json()
    setAccessToken(data.access_token)
    if (data.refresh_token) useAuthStore.setState({ refreshToken: data.refresh_token })
    return data.access_token
  } catch {
    clearAuth()
    return null
  }
}

/** Returns a valid access token, refreshing if the stored one is expired. */
export async function getFreshToken(): Promise<string | null> {
  const { accessToken, refreshToken } = useAuthStore.getState()
  if (!accessToken) return null

  // Check expiry without calling the backend — decode the JWT payload locally.
  try {
    const payload = JSON.parse(atob(accessToken.split('.')[1]))
    const expiresAt = payload.exp * 1000  // ms
    if (Date.now() < expiresAt - 30_000) return accessToken  // still valid (30s buffer)
  } catch {
    // malformed token — fall through to refresh
  }

  if (!refreshToken) { useAuthStore.getState().clearAuth(); return null }
  if (!refreshing) refreshing = attemptRefresh().finally(() => { refreshing = null })
  return refreshing
}

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  // Resolve relative URLs (e.g. "/api/v1/...") to the backend origin.
  // In dev, Vite proxy handles this; in production (file://), we need the full URL.
  const url = input.startsWith('/') ? `${API_ROOT()}${input}` : input
  const { accessToken } = useAuthStore.getState()

  const makeHeaders = (token: string | null) => ({
    // Don't set Content-Type for FormData — the browser must set it to inject the multipart boundary
    ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(init.headers as Record<string, string> ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  })

  let res = await fetch(url, { ...init, headers: makeHeaders(accessToken) })

  if (res.status === 401) {
    // Deduplicate concurrent refresh calls
    if (!refreshing) refreshing = attemptRefresh().finally(() => { refreshing = null })
    const newToken = await refreshing
    if (!newToken) return res  // clearAuth already called — App will redirect to login
    res = await fetch(url, { ...init, headers: makeHeaders(newToken) })
  }

  return res
}
