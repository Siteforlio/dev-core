import { create } from 'zustand'

interface AuthState {
  accessToken: string | null
  userId: string | null
  name: string | null
  languagePref: string
  isAuthenticated: boolean
  setAuth: (token: string, userId: string, name: string, lang: string) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  userId: null,
  name: null,
  languagePref: 'en',
  isAuthenticated: false,
  setAuth: (accessToken, userId, name, languagePref) =>
    set({ accessToken, userId, name, languagePref, isAuthenticated: true }),
  clearAuth: () =>
    set({ accessToken: null, userId: null, name: null, isAuthenticated: false }),
}))
