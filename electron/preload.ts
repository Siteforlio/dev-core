import { contextBridge } from 'electron'
import { authIPC } from './ipc/auth'
import { interviewIPC } from './ipc/interview'

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  auth: authIPC,
  interview: interviewIPC,
})
