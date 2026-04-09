import { ipcRenderer } from 'electron'
import type { IPCResponse } from './types'

export const authIPC = {
  login: (email: string, password: string): Promise<IPCResponse<{ accessToken: string; userId: string; name: string; languagePref: string }>> =>
    ipcRenderer.invoke('auth:login', { email, password }),
  register: (data: { name: string; email: string; password: string; languagePref: string; consentGiven: boolean }): Promise<IPCResponse<{ accessToken: string; userId: string; name: string; languagePref: string }>> =>
    ipcRenderer.invoke('auth:register', data),
}
