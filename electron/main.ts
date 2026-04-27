import { app, BrowserWindow, Menu, ipcMain } from 'electron'
import path from 'path'
import { createOverlayWindow, getOverlayWindow } from './overlay'
import { startAudioCapture, stopAudioCapture, getActiveWs } from './audio'

const BACKEND_WS = 'ws://localhost:8000/api/v1/cluely/ws'

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173')
  } else {
    win.loadFile(path.join(__dirname, '../frontend/dist/index.html'))
  }
}

ipcMain.handle('devcore:session:start', async (_e, payload) => {
  const token: string = payload.token ?? ''
  startAudioCapture(BACKEND_WS, token, payload.audioSource ?? 'both')
})

ipcMain.handle('devcore:session:pause', async () => {
  stopAudioCapture()
})

ipcMain.handle('devcore:session:end', async () => {
  stopAudioCapture()
})

ipcMain.handle('devcore:interact:enable', async () => {
  getOverlayWindow()?.setIgnoreMouseEvents(false)
  getOverlayWindow()?.setFocusable(true)
  getOverlayWindow()?.focus()
})

ipcMain.handle('devcore:interact:disable', async () => {
  getOverlayWindow()?.setIgnoreMouseEvents(true, { forward: true })
  getOverlayWindow()?.setFocusable(false)
})

ipcMain.handle('devcore:manual:ask', async (_e, payload: { text: string; mode: string; language?: string }) => {
  const activeWs = getActiveWs()
  if (activeWs && activeWs.readyState === 1 /* WebSocket.OPEN */) {
    activeWs.send(JSON.stringify({
      type: 'manual_ask',
      text: payload.text,
      mode: payload.mode,
      language: payload.language ?? 'python',
    }))
  }
})

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  createWindow()          // existing main window
  createOverlayWindow()   // new overlay window
})
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
