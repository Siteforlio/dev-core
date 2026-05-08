import { app, BrowserWindow, Menu, ipcMain, shell } from 'electron'
import path from 'path'
import fs from 'fs'
import os from 'os'
import { execFile } from 'child_process'
import * as naudiodon from 'naudiodon'
import { createOverlayWindow, getOverlayWindow, setOverlayContentBounds } from './overlay'
import { startAudioCapture, stopAudioCapture, getActiveWs } from './audio'

// Resolve paths to the Python venv and loopback helper script.
// In dev: __dirname = dist-electron/, project root is one level up.
const PROJECT_ROOT  = path.join(__dirname, '..')
const PYTHON_EXE    = path.join(PROJECT_ROOT, 'backend', 'venv', 'Scripts', 'python.exe')
const LOOPBACK_SCRIPT = path.join(PROJECT_ROOT, 'scripts', 'loopback_capture.py')

function listLoopbackDevices(): Promise<{ id: number; name: string; rate: number; channels: number }[]> {
  return new Promise((resolve) => {
    execFile(PYTHON_EXE, [LOOPBACK_SCRIPT, 'list'], { timeout: 5000 }, (err, stdout) => {
      if (err) { console.warn('[devcore] loopback list failed:', err.message); resolve([]); return }
      try { resolve(JSON.parse(stdout.trim())) } catch { resolve([]) }
    })
  })
}

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

let _lastToken: string = ''

ipcMain.handle('auth:get:token', () => _lastToken || null)

ipcMain.handle('devcore:session:start', async (_e, payload) => {
  try {
    const token: string = payload.token ?? ''
    if (token) _lastToken = token
    startAudioCapture(BACKEND_WS, token, payload.audioSource ?? 'both', payload.sessionId, payload.context ?? {}, payload.micDeviceId ?? null, payload.sysDeviceId ?? null)
    // Forward assessment mode to the overlay window so its store stays in sync
    const overlayWin = getOverlayWindow()
    if (overlayWin && !overlayWin.isDestroyed()) {
      overlayWin.webContents.send('devcore:session:mode', {
        assessmentMode: payload.context?.assessmentMode ?? null,
      })
    }
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
  // Clear assessment mode in the overlay
  const overlayWin = getOverlayWindow()
  if (overlayWin && !overlayWin.isDestroyed()) {
    overlayWin.webContents.send('devcore:session:mode', { assessmentMode: null })
  }
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

// Forward assessment trigger from overlay UI → backend via existing WebSocket
ipcMain.handle('devcore:assessment:trigger', async (_e, payload: { action: string; text?: string }) => {
  const ws = getActiveWs()
  if (!ws || ws.readyState !== 1) return
  try {
    ws.send(JSON.stringify({ type: 'assessment_trigger', ...payload }))
  } catch (err) {
    console.error('[devcore] assessment:trigger send failed:', err)
  }
})

ipcMain.handle('devcore:session:status', async () => {
  const ws = getActiveWs()
  const connected = ws !== null && ws.readyState === 1
  return { connected }
})

ipcMain.handle('devcore:devices:list', async () => {
  try {
    const all    = naudiodon.getDevices() as any[]
    const wasapi = all.filter((d: any) => d.hostAPIName === 'Windows WASAPI')
    const isLoopback = (d: any) =>
      d.isLoopbackDevice === true ||
      (d.maxInputChannels > 0 && /loopback|stereo mix|what u hear|wave out|\[loopback\]/i.test(d.name))

    const mics = wasapi
      .filter((d: any) => d.maxInputChannels > 0 && !isLoopback(d))
      .map((d: any) => ({ id: d.id, name: d.name }))

    // Merge naudiodon loopbacks (Stereo Mix if enabled) with pyaudiowpatch loopbacks
    const naudiodonLoops = wasapi
      .filter((d: any) => isLoopback(d))
      .map((d: any) => ({ id: d.id, name: d.name }))

    const pythonLoops = await listLoopbackDevices()
    // pythonLoops use a separate ID space — prefix with 'py:' to avoid collision
    const systems = [
      ...naudiodonLoops,
      ...pythonLoops
        .filter(p => !naudiodonLoops.some(n => n.name.includes(p.name.replace(' [Loopback]', ''))))
        .map(p => ({ id: p.id, name: p.name, _python: true, _rate: p.rate, _channels: p.channels })),
    ]

    return { mics, systems }
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
  console.log(`[devcore] manual:ask received | text="${payload.text.slice(0, 40)}" | ws=${activeWs ? `readyState=${activeWs.readyState}` : 'null'}`)
  if (activeWs && activeWs.readyState === 1 /* WebSocket.OPEN */) {
    activeWs.send(JSON.stringify({
      type: 'manual_ask',
      text: payload.text,
      mode: payload.mode,
      language: payload.language ?? 'python',
    }))
    console.log('[devcore] manual_ask sent to backend')
  } else {
    console.warn('[devcore] manual:ask — no active WS, message dropped')
  }
})

ipcMain.handle('devcore:outcome:ask', async (_e, payload: { outcome: string }) => {
  const activeWs = getActiveWs()
  if (activeWs && activeWs.readyState === 1) {
    activeWs.send(JSON.stringify({ type: 'outcome_pill_ask', outcome: payload.outcome }))
  } else {
    console.warn('[devcore] outcome:ask — no active WS, message dropped')
  }
})

// ── Device hot-plug detection ──────────────────────────────────────────────
// naudiodon has no push event for device changes, so poll every 2 seconds.
// When the mic list changes, push the new list to the overlay renderer.
function _getDeviceList() {
  try {
    const all = naudiodon.getDevices() as any[]
    const wasapi = all.filter((d: any) => d.hostAPIName === 'Windows WASAPI')
    const isLoopback = (d: any) =>
      d.isLoopbackDevice === true ||
      (d.maxInputChannels > 0 && /loopback|stereo mix|what u hear|wave out|\[loopback\]/i.test(d.name))
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
}

let _lastDeviceSnapshot = ''

function _startDeviceWatcher() {
  setInterval(() => {
    const devices = _getDeviceList()
    const snapshot = JSON.stringify(devices.mics.map((m: any) => m.id))
    if (snapshot === _lastDeviceSnapshot) return
    _lastDeviceSnapshot = snapshot
    const win = getOverlayWindow()
    if (win && !win.isDestroyed()) {
      win.webContents.send('devcore:devices:changed', devices)
    }
  }, 2000)
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  createWindow()          // existing main window
  createOverlayWindow()   // new overlay window
  _startDeviceWatcher()   // hot-plug detection
})
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
