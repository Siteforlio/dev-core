import { app, BrowserWindow, Menu, ipcMain, shell, safeStorage } from 'electron'
import path from 'path'
import fs from 'fs'
import os from 'os'
import crypto from 'crypto'
import { execFile, spawn, ChildProcess } from 'child_process'
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

let _backendProcess: ChildProcess | null = null

async function startBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const backendDir = path.join(PROJECT_ROOT, 'backend')
    _backendProcess = spawn(
      PYTHON_EXE,
      ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'],
      { cwd: backendDir, stdio: ['ignore', 'pipe', 'pipe'] }
    )

    let stderrBuf = ''
    let startupDone = false

    _backendProcess.stdout?.on('data', (d: Buffer) => process.stdout.write(`[backend] ${d}`))
    _backendProcess.stderr?.on('data', (d: Buffer) => {
      const text = d.toString()
      stderrBuf += text
      process.stderr.write(`[backend] ${text}`)
    })

    _backendProcess.on('error', (err: Error) => {
      if (!startupDone) {
        clearInterval(poll)
        reject(err)
      }
    })

    _backendProcess.on('exit', (code: number | null) => {
      if (!startupDone) {
        // Process exited before health check passed — reject immediately with stderr context
        clearInterval(poll)
        reject(new Error(`Backend exited with code ${code}.\n${stderrBuf.slice(-500)}`))
      } else if (code !== 0 && code !== null) {
        // Mid-session crash — notify all renderer windows
        console.error(`[devcore] backend exited with code ${code}`)
        BrowserWindow.getAllWindows().forEach(w => {
          if (!w.isDestroyed()) w.webContents.send('devcore:backend:crashed', { code })
        })
      }
    })

    // Poll /health until backend is ready (max 30s)
    const start = Date.now()
    const poll = setInterval(async () => {
      if (Date.now() - start > 30_000) {
        clearInterval(poll)
        reject(new Error(`Backend did not start within 30s.\n${stderrBuf.slice(-500)}`))
        return
      }
      try {
        const { net } = await import('electron')
        const req = net.request({ method: 'GET', url: 'http://127.0.0.1:8000/health' })
        req.on('response', (res) => {
          if (res.statusCode === 200) {
            clearInterval(poll)
            startupDone = true
            resolve()
          }
        })
        req.on('error', () => {}) // still starting — ignore
        req.end()
      } catch {}
    }, 500)
  })
}

function stopBackend(): void {
  if (_backendProcess && !_backendProcess.killed) {
    _backendProcess.kill('SIGTERM')
    _backendProcess = null
  }
}

const BACKEND_WS = 'ws://localhost:8000/api/v1/cluely/ws'

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    frame: false,
    backgroundColor: '#020810',   // prevents white flash before React mounts
    show: false,                   // revealed via ready-to-show below
    icon: path.join(PROJECT_ROOT, 'frontend', 'public', 'app-icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  win.once('ready-to-show', () => win.show())

  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173')
  } else {
    win.loadFile(path.join(__dirname, '../frontend/dist/index.html'))
  }
}

let _lastToken: string = ''
let _lastRefreshToken: string = ''
let _refreshingToken: Promise<{ accessToken: string; refreshToken: string } | null> | null = null

// ── Secure credential storage paths (set after app ready) ─────────────────
let _tokenFilePath = ''
let _pinConfigPath = ''
let _credsFilePath = ''
let _pinFailures   = 0
const PIN_MAX_FAILURES = 5

function _initCredPaths() {
  const userData  = app.getPath('userData')
  _tokenFilePath  = path.join(userData, 'devcore-session.bin')
  _pinConfigPath  = path.join(userData, 'devcore-pin.json')
  _credsFilePath  = path.join(userData, 'devcore-creds.bin')
}

/** Persist refresh token to disk using OS-level encryption (Windows DPAPI). */
function _saveRefreshToken(token: string): void {
  if (!_tokenFilePath || !safeStorage.isEncryptionAvailable()) return
  try {
    fs.writeFileSync(_tokenFilePath, safeStorage.encryptString(token))
  } catch {}
}

/** Load the persisted refresh token from disk. Returns '' on any failure. */
function _loadStoredRefreshToken(): string {
  if (!_tokenFilePath || !safeStorage.isEncryptionAvailable()) return ''
  try {
    if (!fs.existsSync(_tokenFilePath)) return ''
    return safeStorage.decryptString(fs.readFileSync(_tokenFilePath))
  } catch { return '' }
}

function _clearStoredToken(): void {
  try { if (_tokenFilePath) fs.unlinkSync(_tokenFilePath) } catch {}
}

// ── PIN helpers ───────────────────────────────────────────────────────────

/** Deterministic hash for a PIN. Fixed salt is fine — lockout enforces rate-limiting. */
function _hashPin(pin: string): string {
  return crypto.pbkdf2Sync(pin, 'devcore-pin-salt-v1', 100_000, 32, 'sha256').toString('hex')
}

function _loadPinHash(): string | null {
  try {
    if (!_pinConfigPath || !fs.existsSync(_pinConfigPath)) return null
    const data = JSON.parse(fs.readFileSync(_pinConfigPath, 'utf8'))
    return typeof data.hash === 'string' ? data.hash : null
  } catch { return null }
}

function _savePinHash(hash: string): void {
  if (!_pinConfigPath) return
  fs.writeFileSync(_pinConfigPath, JSON.stringify({ hash }))
}

function _clearPin(): void {
  try { if (_pinConfigPath) fs.unlinkSync(_pinConfigPath) } catch {}
}

// ── Login credential storage (email + password, OS-encrypted) ─────────────

/** Encrypt and persist login credentials to disk using Windows DPAPI. */
function _saveCreds(email: string, password: string): void {
  if (!_credsFilePath || !safeStorage.isEncryptionAvailable()) return
  try {
    const payload = JSON.stringify({ email, password })
    fs.writeFileSync(_credsFilePath, safeStorage.encryptString(payload))
  } catch {}
}

/** Load saved credentials. Returns null if none saved or decryption fails. */
function _loadCreds(): { email: string; password: string } | null {
  if (!_credsFilePath || !safeStorage.isEncryptionAvailable()) return null
  try {
    if (!fs.existsSync(_credsFilePath)) return null
    const raw = safeStorage.decryptString(fs.readFileSync(_credsFilePath))
    const parsed = JSON.parse(raw)
    if (typeof parsed.email === 'string' && typeof parsed.password === 'string') {
      return { email: parsed.email, password: parsed.password }
    }
    return null
  } catch { return null }
}

function _clearCreds(): void {
  try { if (_credsFilePath) fs.unlinkSync(_credsFilePath) } catch {}
}

const BACKEND_HTTP = 'http://localhost:8000'

/** Decode JWT exp claim without a library. Returns expiry ms or 0 on error. */
function _jwtExpiry(token: string): number {
  try {
    const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64').toString())
    return (payload.exp ?? 0) * 1000
  } catch { return 0 }
}

/** Refresh tokens directly from main process — no renderer involvement. */
async function _doRefresh(): Promise<{ accessToken: string; refreshToken: string } | null> {
  if (!_lastRefreshToken) return null
  try {
    const { net } = await import('electron')
    const req = net.request({
      method: 'POST',
      url: `${BACKEND_HTTP}/api/v1/auth/refresh`,
    })
    return await new Promise<{ accessToken: string; refreshToken: string } | null>((resolve) => {
      req.setHeader('Authorization', `Bearer ${_lastRefreshToken}`)
      req.setHeader('Content-Type', 'application/json')
      let body = ''
      req.on('response', (res) => {
        res.on('data', (chunk) => { body += chunk.toString() })
        res.on('end', () => {
          try {
            if (res.statusCode !== 200) { resolve(null); return }
            const data = JSON.parse(body)?.data
            const accessToken: string = data?.access_token ?? ''
            // Capture rotated refresh token (replay attack protection — server issues new JTI each time)
            const refreshToken: string = data?.refresh_token ?? ''
            if (accessToken) _lastToken = accessToken
            if (refreshToken) { _lastRefreshToken = refreshToken; _saveRefreshToken(refreshToken) }
            resolve(accessToken ? { accessToken, refreshToken } : null)
          } catch { resolve(null) }
        })
      })
      req.on('error', () => resolve(null))
      req.end()
    })
  } catch { return null }
}

ipcMain.handle('auth:get:token', () => _lastToken || null)

// Store refresh token from renderer so main process can refresh independently.
// Also persists to disk via safeStorage so it survives app restarts.
ipcMain.handle('auth:set:refresh', (_e, refreshToken: string) => {
  if (refreshToken) {
    _lastRefreshToken = refreshToken
    _saveRefreshToken(refreshToken)
  }
})

// Called during splash to decide what screen to show.
ipcMain.handle('auth:startup:status', () => {
  const hasToken  = !!_lastRefreshToken
  const pinHash   = _loadPinHash()
  return { hasToken, pinRequired: hasToken && pinHash !== null }
})

// Verify a PIN attempt. Locks out after PIN_MAX_FAILURES wrong tries.
ipcMain.handle('auth:pin:check', (_e, pin: string) => {
  const pinHash = _loadPinHash()
  if (!pinHash) return { ok: false, reason: 'no_pin' }
  if (_pinFailures >= PIN_MAX_FAILURES) {
    return { ok: false, reason: 'locked', attemptsLeft: 0 }
  }
  if (_hashPin(String(pin)) === pinHash) {
    _pinFailures = 0
    return { ok: true }
  }
  _pinFailures++
  const attemptsLeft = PIN_MAX_FAILURES - _pinFailures
  if (attemptsLeft <= 0) {
    // Wipe stored token — force full login
    _clearStoredToken()
    _lastRefreshToken = ''
    _lastToken = ''
  }
  return { ok: false, reason: 'wrong', attemptsLeft }
})

// Set or update the PIN (digits only, 4–8 chars).
ipcMain.handle('auth:pin:set', (_e, pin: string) => {
  if (typeof pin !== 'string' || !/^\d{4,8}$/.test(pin)) {
    return { ok: false, reason: 'invalid' }
  }
  _savePinHash(_hashPin(pin))
  return { ok: true }
})

// Remove PIN (PIN screen skipped on next startup).
ipcMain.handle('auth:pin:remove', () => {
  _clearPin()
  return { ok: true }
})

// Quick check used by settings UI to know if PIN is configured.
ipcMain.handle('auth:pin:exists', () => ({ exists: _loadPinHash() !== null }))

// Called on logout — wipes the stored refresh token from disk.
ipcMain.handle('auth:clear:stored', () => {
  _clearStoredToken()
  _lastRefreshToken = ''
  _lastToken = ''
})

// Save login credentials encrypted with Windows DPAPI.
ipcMain.handle('auth:creds:save', (_e, email: string, password: string) => {
  if (typeof email !== 'string' || typeof password !== 'string') return { ok: false }
  _saveCreds(email.slice(0, 512), password.slice(0, 512))
  return { ok: true }
})

// Load saved credentials (returns null if none).
ipcMain.handle('auth:creds:load', () => _loadCreds())

// Clear saved credentials.
ipcMain.handle('auth:creds:clear', () => {
  _clearCreds()
  return { ok: true }
})

// Single refresh path for all windows — deduplicates concurrent attempts.
// Main process calls backend directly — no renderer/executeJavaScript needed.
// Returns { accessToken, refreshToken } on success, or null on failure.
ipcMain.handle('auth:refresh:token', async () => {
  // Return cached token if still valid (30s buffer)
  if (_lastToken && Date.now() < _jwtExpiry(_lastToken) - 30_000) {
    return { accessToken: _lastToken, refreshToken: _lastRefreshToken }
  }
  if (_refreshingToken) return _refreshingToken
  _refreshingToken = _doRefresh().finally(() => { _refreshingToken = null })
  return _refreshingToken
})

/** Clamp a string to maxLen characters, return '' if not a string. */
function _str(v: unknown, maxLen = 4096): string {
  if (typeof v !== 'string') return ''
  return v.slice(0, maxLen)
}

/** Clamp a number to [min, max], return fallback if not a number. */
function _num(v: unknown, fallback: number, min: number, max: number): number {
  const n = typeof v === 'number' ? v : fallback
  return Math.max(min, Math.min(max, n))
}

ipcMain.handle('devcore:session:start', async (_e, payload) => {
  if (!payload || typeof payload !== 'object') throw new Error('Invalid payload')
  try {
    const token: string = _str(payload.token, 2048)
    console.log(`[devcore] session:start received | token=${token ? token.slice(0,20)+'…' : 'EMPTY'} | audioSource=${payload.audioSource}`)
    if (token) _lastToken = token

    const audioSource = ['mic', 'system', 'both'].includes(payload.audioSource)
      ? payload.audioSource : 'both'
    const sessionId = _str(payload.sessionId, 128)
    const micDeviceId = payload.micDeviceId != null ? _num(payload.micDeviceId, 0, 0, 9999) : null
    const sysDeviceId = payload.sysDeviceId != null ? _num(payload.sysDeviceId, 0, 0, 9999) : null

    // Sanitise context — whitelist known keys, cap string lengths
    const rawCtx = payload.context ?? {}
    const context = {
      jobTitle:      _str(rawCtx.jobTitle, 256),
      company:       _str(rawCtx.company, 256),
      resumeText:    _str(rawCtx.resumeText, 8000),
      jdText:        _str(rawCtx.jdText, 4000),
      assessmentMode: _str(rawCtx.assessmentMode, 32) || null,
      projectRoot:   _str(rawCtx.projectRoot, 512) || null,
      files: Array.isArray(rawCtx.files)
        ? (rawCtx.files as unknown[]).slice(0, 3).map((f) => _str(f, 512)).filter(Boolean)
        : [],
    }

    // Quick connectivity check before handing off to audio.ts
    const { net } = await import('electron')
    await new Promise<void>((resolve) => {
      const req = net.request({ method: 'GET', url: `http://localhost:8000/api/v1/auth/me` })
      req.on('response', (res) => { console.log(`[devcore] backend reachable — HTTP ${res.statusCode}`); resolve() })
      req.on('error', (e) => { console.error('[devcore] backend NOT reachable:', e.message); resolve() })
      req.end()
    })
    startAudioCapture(BACKEND_WS, token, audioSource, sessionId, context, micDeviceId, sysDeviceId)
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
  // Send pause signal to backend — keep WS + audio streams alive so resume works.
  // The backend sets state to "paused" and stops processing new audio.
  const ws = getActiveWs()
  if (ws && ws.readyState === 1) {
    try { ws.send(JSON.stringify({ type: 'session_pause' })) } catch {}
  }
})

ipcMain.handle('devcore:session:resume', async () => {
  const ws = getActiveWs()
  if (ws && ws.readyState === 1) {
    try { ws.send(JSON.stringify({ type: 'session_resume' })) } catch {}
  }
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
  if (!payload || typeof payload !== 'object') return
  const ws = getActiveWs()
  if (!ws || ws.readyState !== 1) return
  try {
    ws.send(JSON.stringify({
      type: 'assessment_trigger',
      action: _str(payload.action, 64),
      text:   payload.text != null ? _str(payload.text, 2000) : undefined,
    }))
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

ipcMain.handle('devcore:manual:ask', async (_e, payload: { text: string; mode: string; language?: string; history?: { role: string; text: string }[] }) => {
  if (!payload || typeof payload !== 'object') return
  const activeWs = getActiveWs()
  if (activeWs && activeWs.readyState === 1 /* WebSocket.OPEN */) {
    const safeHistory = Array.isArray(payload.history)
      ? payload.history.slice(0, 50).map((h) => ({
          role: _str(h?.role, 16),
          text: _str(h?.text, 2000),
        }))
      : []
    activeWs.send(JSON.stringify({
      type: 'manual_ask',
      text: _str(payload.text, 2000),
      mode: _str(payload.mode, 32),
      language: _str(payload.language ?? 'python', 32),
      history: safeHistory,
    }))
    console.log('[devcore] manual_ask sent to backend')
  } else {
    console.warn('[devcore] manual:ask — no active WS, message dropped')
  }
})

ipcMain.handle('devcore:screenshot:clear', async () => {
  const { getActiveWs } = await import('./audio')
  const sock = getActiveWs()
  if (sock && sock.readyState === 1) {
    sock.send(JSON.stringify({ type: 'screenshot_clear' }))
  }
  const overlayWin = getOverlayWindow()
  if (overlayWin && !overlayWin.isDestroyed()) {
    overlayWin.webContents.send('devcore:screenshot:count', { count: 0 })
  }
})

ipcMain.handle('devcore:outcome:ask', async (_e, payload: { outcome: string }) => {
  if (!payload || typeof payload !== 'object') return
  const activeWs = getActiveWs()
  if (activeWs && activeWs.readyState === 1) {
    activeWs.send(JSON.stringify({ type: 'outcome_pill_ask', outcome: _str(payload.outcome, 512) }))
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

// ── Shell helpers — open files / folders in the OS ───────────────────────────
ipcMain.handle('shell:openPath', (_e, filePath: string) => shell.openPath(filePath))
ipcMain.handle('shell:showItemInFolder', (_e, filePath: string) => {
  shell.showItemInFolder(filePath)
})

ipcMain.handle('window:minimize', () => BrowserWindow.getFocusedWindow()?.minimize())
ipcMain.handle('window:maximize', () => {
  const win = BrowserWindow.getFocusedWindow()
  if (!win) return
  win.isMaximized() ? win.unmaximize() : win.maximize()
})
ipcMain.handle('window:close', () => BrowserWindow.getFocusedWindow()?.close())

// Renderer signals splash done → create the overlay window for the first time
let _overlayCreated = false
ipcMain.handle('app:splash-done', () => {
  if (_overlayCreated) return
  _overlayCreated = true
  createOverlayWindow()
})

app.whenReady().then(async () => {
  _initCredPaths()
  // Restore persisted refresh token so startup status check is correct
  const stored = _loadStoredRefreshToken()
  if (stored) _lastRefreshToken = stored

  Menu.setApplicationMenu(null)

  // Start backend before opening the window
  try {
    await startBackend()
    console.log('[devcore] backend ready')
  } catch (err) {
    console.error('[devcore] backend failed to start:', err)
    const { dialog } = await import('electron')
    await dialog.showErrorBox(
      'Startup Error',
      `Developer Core backend failed to start.\n\n${err}\n\nPlease check your installation.`
    )
    app.quit()
    return
  }

  createWindow()          // main app window (overlay deferred until splash-done IPC)
  _startDeviceWatcher()   // hot-plug detection
})
app.on('will-quit', () => stopBackend())
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
