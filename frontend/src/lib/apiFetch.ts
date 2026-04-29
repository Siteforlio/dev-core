/**
 * Drop-in fetch wrapper that auto-refreshes the access token on 401.
 * If refresh also fails, clears auth and forces re-login.
 */
import { useAuthStore } from '../store/authStore'

let refreshing: Promise<string | null> | null = null

async function attemptRefresh(): Promise<string | null> {
  const { refreshToken, setAccessToken, clearAuth } = useAuthStore.getState()
  if (!refreshToken) { clearAuth(); return null }

  try {
    const res = await fetch('http://localhost:8000/api/v1/auth/refresh', {
      method: 'POST',
      headers: { Authorization: `Bearer ${refreshToken}` },
    })
    if (!res.ok) { clearAuth(); return null }
    const { data } = await res.json()
    setAccessToken(data.access_token)
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
  const { accessToken } = useAuthStore.getState()

  const makeHeaders = (token: string | null) => ({
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  })

  let res = await fetch(input, { ...init, headers: makeHeaders(accessToken) })

  if (res.status === 401) {
    // Deduplicate concurrent refresh calls
    if (!refreshing) refreshing = attemptRefresh().finally(() => { refreshing = null })
    const newToken = await refreshing
    if (!newToken) return res  // clearAuth already called — App will redirect to login
    res = await fetch(input, { ...init, headers: makeHeaders(newToken) })
  }

  return res
}
