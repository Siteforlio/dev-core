import { create } from 'zustand'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  userId: string | null
  name: string | null
  languagePref: string
  isAuthenticated: boolean
  setAuth: (token: string, refreshToken: string, userId: string, name: string, lang: string) => void
  setAccessToken: (token: string) => void
  clearAuth: () => void
}

// Tokens are kept in memory only — NOT persisted to localStorage.
// The main process (Electron safeStorage) is the source of truth for the refresh token.
// On app restart, the renderer re-authenticates via IPC (auth:get:token / auth:refresh:token).
export const useAuthStore = create<AuthState>()((set) => ({
  accessToken: null,
  refreshToken: null,
  userId: null,
  name: null,
  languagePref: 'en',
  isAuthenticated: false,
  setAuth: (accessToken, refreshToken, userId, name, languagePref) => {
    // Keep main process in sync so it can refresh tokens without renderer involvement
    ;(window as any).electronAPI?.setRefreshToken?.(refreshToken)
    set({ accessToken, refreshToken, userId, name, languagePref, isAuthenticated: true })
  },
  setAccessToken: (accessToken) => set({ accessToken }),
  clearAuth: () => {
    // Wipe the encrypted token from disk so the next startup requires login
    ;(window as any).electronAPI?.clearStored?.()
    set({ accessToken: null, refreshToken: null, userId: null, name: null, isAuthenticated: false })
  },
}))
