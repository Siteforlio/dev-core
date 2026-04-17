import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      userId: null,
      name: null,
      languagePref: 'en',
      isAuthenticated: false,
      setAuth: (accessToken, refreshToken, userId, name, languagePref) =>
        set({ accessToken, refreshToken, userId, name, languagePref, isAuthenticated: true }),
      setAccessToken: (accessToken) => set({ accessToken }),
      clearAuth: () =>
        set({ accessToken: null, refreshToken: null, userId: null, name: null, isAuthenticated: false }),
    }),
    { name: 'auth' }
  )
)
