import { app, BrowserWindow, Menu, ipcMain, shell } from 'electron'
import path from 'path'
import fs from 'fs'
import os from 'os'
import * as naudiodon from 'naudiodon'
import { createOverlayWindow, getOverlayWindow, setOverlayContentBounds } from './overlay'
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
      sandbox: false,
    },
  })
  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173')
  } else {
    win.loadFile(path.join(__dirname, '../frontend/dist/index.html'))
  }
}

ipcMain.handle('devcore:session:start', async (_e, payload) => {
  try {
    const token: string = payload.token ?? ''
    startAudioCapture(BACKEND_WS, token, payload.audioSource ?? 'both', payload.sessionId, payload.context ?? {}, payload.micDeviceId ?? null, payload.sysDeviceId ?? null)
  } catch (err) {
    console.error('[devcore] session:start failed:', err)
    throw err  // surface to renderer so handleStart can catch and log it
  }
})

ipcMain.handle('devcore:session:pause', async () => {
  stopAudioCapture()
})

ipcMain.handle('devcore:session:end', async () => {
  stopAudioCapture()
})

// Content bounds from renderer — polling loop uses this to decide when cursor is over the UI
ipcMain.on('devcore:content:bounds', (_e, bounds: { x: number; y: number; width: number; height: number }) => {
  setOverlayContentBounds(bounds)
})

// These are now no-ops since the polling loop manages interact mode automatically.
// Kept so hotkey-forced interact (Ctrl+Shift+I) still works.
ipcMain.handle('devcore:interact:enable', async () => {
  getOverlayWindow()?.setIgnoreMouseEvents(false)
  getOverlayWindow()?.setFocusable(true)
  getOverlayWindow()?.focus()
})

ipcMain.handle('devcore:interact:disable', async () => {
  getOverlayWindow()?.setIgnoreMouseEvents(true, { forward: true })
  getOverlayWindow()?.setFocusable(false)
})

ipcMain.handle('devcore:session:status', async () => {
  const ws = getActiveWs()
  const connected = ws !== null && ws.readyState === 1
  return { connected }
})

ipcMain.handle('devcore:devices:list', async () => {
  try {
    const all = naudiodon.getDevices() as any[]
    const wasapi = all.filter((d: any) => d.hostAPIName === 'Windows WASAPI')
    const isLoopback = (d: any) =>
      d.isLoopbackDevice === true ||
      (d.maxInputChannels > 0 && /loopback|stereo mix|what u hear|wave out/i.test(d.name))
    return {
      mics: wasapi
        .filter((d: any) => d.maxInputChannels > 0 && !isLoopback(d))
        .map((d: any) => ({ id: d.id, name: d.name })),
      systems: wasapi
        .filter((d: any) => isLoopback(d))
        .map((d: any) => ({ id: d.id, name: d.name })),
    }
  } catch {
    return { mics: [], systems: [] }
  }
})

ipcMain.handle('devcore:mic:test', async (_e, payload: { deviceId?: number | null; durationMs?: number }) => {
  const DURATION_MS   = payload.durationMs ?? 5000
  const CAPTURE_RATE  = 48000
  const TARGET_RATE   = 16000  // downsample for playback (keeps WAV small)
  const CHANNELS      = 1

  return new Promise<{ ok: boolean; filePath?: string; error?: string }>((resolve) => {
    try {
      const all = naudiodon.getDevices() as any[]
      const wasapi = all.filter((d: any) => d.hostAPIName === 'Windows WASAPI')
      const isLoopback = (d: any) =>
        d.isLoopbackDevice === true ||
        (d.maxInputChannels > 0 && /loopback|stereo mix|what u hear|wave out/i.test(d.name))
      const mic = payload.deviceId != null
        ? all.find((d: any) => d.id === payload.deviceId)
        : wasapi.find((d: any) => d.maxInputChannels > 0 && !isLoopback(d))

      if (!mic) { resolve({ ok: false, error: 'No mic device found' }); return }
      console.log(`[mic-test] Recording ${DURATION_MS}ms from [${mic.id}] "${mic.name}"`)

      const input = naudiodon.AudioIO({
        inOptions: {
          deviceId: mic.id,
          channelCount: CHANNELS,
          sampleRate: CAPTURE_RATE,
          framesPerBuffer: 4096,
          sampleFormat: naudiodon.SampleFormat16Bit,
        }
      })

      const chunks: Buffer[] = []
      input.on('data', (chunk: Buffer) => chunks.push(chunk))
      input.on('error', (err: Error) => {
        console.error('[mic-test] capture error:', err)
        resolve({ ok: false, error: err.message })
      })
      input.start()

      setTimeout(() => {
        input.quit()
        const pcm = Buffer.concat(chunks)

        // Downsample 48kHz → 16kHz (nearest-neighbour)
        const ratio     = CAPTURE_RATE / TARGET_RATE
        const inSamples = pcm.length / 2
        const outCount  = Math.floor(inSamples / ratio)
        const resampled = Buffer.alloc(outCount * 2)
        for (let i = 0; i < outCount; i++) {
          const src = Math.min(Math.round(i * ratio), inSamples - 1)
          resampled.writeInt16LE(pcm.readInt16LE(src * 2), i * 2)
        }

        // Write WAV
        const wavPath = path.join(os.tmpdir(), `devcore-mic-test-${Date.now()}.wav`)
        const dataSize   = resampled.length
        const byteRate   = TARGET_RATE * CHANNELS * 2
        const header     = Buffer.alloc(44)
        header.write('RIFF', 0)
        header.writeUInt32LE(36 + dataSize, 4)
        header.write('WAVE', 8)
        header.write('fmt ', 12)
        header.writeUInt32LE(16, 16)             // PCM chunk size
        header.writeUInt16LE(1, 20)              // PCM format
        header.writeUInt16LE(CHANNELS, 22)
        header.writeUInt32LE(TARGET_RATE, 24)
        header.writeUInt32LE(byteRate, 28)
        header.writeUInt16LE(CHANNELS * 2, 32)  // block align
        header.writeUInt16LE(16, 34)             // bits per sample
        header.write('data', 36)
        header.writeUInt32LE(dataSize, 40)

        fs.writeFileSync(wavPath, Buffer.concat([header, resampled]))
        console.log(`[mic-test] Saved to ${wavPath} (${(dataSize / 1024).toFixed(1)} KB)`)

        // Open with default media player
        shell.openPath(wavPath)
        resolve({ ok: true, filePath: wavPath })
      }, DURATION_MS)
    } catch (err: any) {
      resolve({ ok: false, error: err.message })
    }
  })
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
