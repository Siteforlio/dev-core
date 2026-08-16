import { BrowserWindow, globalShortcut, app, screen, ipcMain } from 'electron'
import path from 'path'
import Store = require('electron-store')

const store = new Store<{ overlayX: number; overlayY: number }>()

// Win32 screen-capture exclusion — loaded lazily so non-Windows platforms don't crash.
type SetWindowDisplayAffinityFn = (hwnd: number, affinity: number) => boolean
let _setWindowDisplayAffinity: SetWindowDisplayAffinityFn | null = null

if (process.platform === 'win32') {
  try {
    // koffi is a native module — only available and needed on Windows.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const koffi = require('koffi')
    const user32 = koffi.load('user32.dll')
    _setWindowDisplayAffinity = user32.func(
      'bool SetWindowDisplayAffinity(intptr_t hWnd, uint32 dwAffinity)',
    )
  } catch (e) {
    console.warn('[devcore-overlay] Failed to load user32.dll (non-fatal):', e)
  }
}

const MOVE_STEP = 20  // px per arrow key press
const CONTENT_MARGIN = 50  // min px from screen edge

// Content position within the full-screen transparent window.
// Stored as the CSS left/top of the content box (top-left corner).
let _contentX = 0
let _contentY = 0

function _moveContent(win: BrowserWindow, x: number, y: number) {
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize
  _contentX = Math.max(0, Math.min(Math.round(x), sw - CONTENT_MARGIN))
  _contentY = Math.max(0, Math.min(Math.round(y), sh - CONTENT_MARGIN))
  win.webContents.send('devcore:overlay:move', { x: _contentX, y: _contentY })
  store.set('overlayX', _contentX)
  store.set('overlayY', _contentY)
}

let overlayWin: BrowserWindow | null = null

/**
 * Apply the best available screen-capture exclusion for the current platform.
 *
 * Windows  → SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) via Win32 API.
 *            The window becomes completely invisible to all screen-capture
 *            software (OBS, Zoom, Teams) on Windows 10 build 2004+ / Windows 11.
 *
 * macOS    → setContentProtection(true), Electron's built-in wrapper around
 *            NSWindow.sharingType = NSWindowSharingNone.  Hides the window
 *            from screen recording, screenshots, and the Dock preview.
 *
 * Linux    → No stable cross-desktop API exists.  The window remains visible
 *            in screen captures; users should rely on the virtual camera trick
 *            or a dedicated virtual display.
 */
function _applyStealthMode(win: BrowserWindow): void {
  if (process.platform === 'win32') {
    if (!_setWindowDisplayAffinity) {
      console.warn('[devcore-overlay] koffi/user32 not loaded — overlay will be visible in captures')
      return
    }
    try {
      const hwndBuf = win.getNativeWindowHandle()
      const hwnd = process.arch === 'x64'
        ? Number(hwndBuf.readBigInt64LE(0))
        : hwndBuf.readInt32LE(0)
      const WDA_EXCLUDEFROMCAPTURE = 0x00000011
      const ok = _setWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
      if (ok) {
        console.log('[devcore-overlay] WDA_EXCLUDEFROMCAPTURE applied (Windows stealth) hwnd=', hwnd)
      } else {
        console.error('[devcore-overlay] SetWindowDisplayAffinity returned false — stealth failed, hwnd=', hwnd)
      }
    } catch (e) {
      console.warn('[devcore-overlay] SetWindowDisplayAffinity failed (non-fatal):', e)
    }
  } else if (process.platform === 'darwin') {
    win.setContentProtection(true)
    console.log('[devcore-overlay] setContentProtection(true) applied (macOS stealth)')
  } else {
    console.info(
      '[devcore-overlay] No screen-capture exclusion API available on Linux — overlay visible in captures',
    )
  }
}
// Content bounds sent from the renderer — used by the polling loop
// to decide whether the cursor is over the actual UI (not just the transparent window).
let _contentBounds = { x: 0, y: 0, width: 0, height: 0 }
const HOVER_PADDING = 8   // px extra hit-area so near-edge clicks aren't missed
let _pollTimer: ReturnType<typeof setInterval> | null = null
let _isInteractMode = false

export function createOverlayWindow(): BrowserWindow {
  if (overlayWin && !overlayWin.isDestroyed()) return overlayWin

  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize
  // Default: top-center — pill is ~350 px wide, so x = (sw - 350) / 2
  const defaultX = Math.max(0, Math.round((sw - 350) / 2))
  const defaultY = 8
  _contentX = store.get('overlayX', defaultX)
  _contentY = store.get('overlayY', defaultY)

  overlayWin = new BrowserWindow({
    width: sw,
    height: sh,
    x: 0,
    y: 0,
    transparent: true,
    frame: false,
    skipTaskbar: true,
    focusable: false,
    hasShadow: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
      backgroundThrottling: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  overlayWin.setAlwaysOnTop(true, 'screen-saver')
  overlayWin.setIgnoreMouseEvents(true, { forward: true })
  _startCursorPoll(overlayWin)

  // Apply platform-specific screen-capture exclusion so the overlay is
  // invisible to OBS, Zoom, Teams, mss, etc.
  // Applied twice: once early (before load) and once after did-finish-load
  // to ensure the compositor has registered the affinity after the window
  // is fully painted.
  _applyStealthMode(overlayWin)
  overlayWin.webContents.once('did-finish-load', () => {
    if (overlayWin && !overlayWin.isDestroyed()) {
      _applyStealthMode(overlayWin)
      // Send saved content position so renderer can position itself immediately
      overlayWin.webContents.send('devcore:overlay:move', { x: _contentX, y: _contentY })
    }
  })

  // Windows resets WDA_EXCLUDEFROMCAPTURE whenever the window transitions from
  // hidden → visible. Re-apply on every 'show' event to keep stealth intact.
  overlayWin.on('show', () => {
    if (overlayWin && !overlayWin.isDestroyed()) _applyStealthMode(overlayWin)
  })

  if (process.env.NODE_ENV === 'development') {
    overlayWin.loadURL('http://localhost:5173/overlay.html')
  } else {
    overlayWin.loadFile(path.join(__dirname, '../frontend/dist/overlay.html'))
  }

  overlayWin.webContents.openDevTools({ mode: 'detach' })
  registerHotkeys(overlayWin)
  return overlayWin
}

function _startCursorPoll(win: BrowserWindow) {
  if (_pollTimer) clearInterval(_pollTimer)
  _pollTimer = setInterval(() => {
    if (!win || win.isDestroyed() || !win.isVisible()) return
    const cursor   = screen.getCursorScreenPoint()
    const [wx, wy] = win.getPosition()
    // Convert screen coords → window-local coords
    const lx = cursor.x - wx
    const ly = cursor.y - wy
    const b  = _contentBounds
    const isOver = b.width > 0 && (
      lx >= b.x - HOVER_PADDING && lx <= b.x + b.width  + HOVER_PADDING &&
      ly >= b.y - HOVER_PADDING && ly <= b.y + b.height + HOVER_PADDING
    )
    if (isOver && !_isInteractMode) {
      _isInteractMode = true
      win.setIgnoreMouseEvents(false)
      win.setFocusable(true)
      win.focus()
    } else if (!isOver && _isInteractMode) {
      _isInteractMode = false
      win.setIgnoreMouseEvents(true, { forward: true })
      win.setFocusable(false)
    }
  }, 30)  // 30 ms ≈ 33 fps — imperceptible lag, < 1% CPU
}

// Called from main.ts IPC when the renderer sends updated content bounds.
export function setOverlayContentBounds(bounds: { x: number; y: number; width: number; height: number }) {
  _contentBounds = bounds
}

function registerHotkeys(win: BrowserWindow) {
  // Show/hide — re-apply stealth on every show because Windows resets
  // SetWindowDisplayAffinity when a window is hidden and re-shown.
  const registeredSpace = globalShortcut.register('CommandOrControl+Space', () => {
    if (win.isVisible()) {
      win.hide()
    } else {
      win.show()
      _applyStealthMode(win)
    }
  })
  if (!registeredSpace) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Space')

  // Interact mode toggle
  let interactMode = false
  const registeredI = globalShortcut.register('CommandOrControl+I', () => {
    interactMode = !interactMode
    if (interactMode) {
      win.setIgnoreMouseEvents(false)
      win.setFocusable(true)
      win.focus()
    } else {
      win.setIgnoreMouseEvents(true, { forward: true })
      win.setFocusable(false)
    }
  })
  if (!registeredI) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+I')

  // Move overlay content — each press nudges by MOVE_STEP px, clamped to screen bounds
  const registeredRight = globalShortcut.register('CommandOrControl+Right', () => _moveContent(win, _contentX + MOVE_STEP, _contentY))
  if (!registeredRight) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Right')

  const registeredLeft = globalShortcut.register('CommandOrControl+Left', () => _moveContent(win, _contentX - MOVE_STEP, _contentY))
  if (!registeredLeft) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Left')

  const registeredDown = globalShortcut.register('CommandOrControl+Down', () => _moveContent(win, _contentX, _contentY + MOVE_STEP))
  if (!registeredDown) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Down')

  const registeredUp = globalShortcut.register('CommandOrControl+Up', () => _moveContent(win, _contentX, _contentY - MOVE_STEP))
  if (!registeredUp) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Up')

  // Force re-trigger
  const registeredR = globalShortcut.register('CommandOrControl+R', () => {
    win.webContents.send('devcore:status', { state: 'thinking', latencyMs: 0 })
  })
  if (!registeredR) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+R')

  // Screenshot capture (Ctrl+Shift+S)
  const registeredSnap = globalShortcut.register('CommandOrControl+S', async () => {
    const { captureAndSendScreenshot } = await import('./audio')
    await captureAndSendScreenshot()
    // Visual flash on the pill — send hotkey event so renderer can animate
    win.webContents.send('devcore:hotkey', { action: 'screenshot' })
  })
  if (!registeredSnap) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+S')

  // Clear screenshot buffer (Ctrl+Shift+X)
  const registeredClear = globalShortcut.register('CommandOrControl+X', () => {
    const sock = require('./audio').getActiveWs?.()
    if (sock && sock.readyState === 1) {
      sock.send(JSON.stringify({ type: 'screenshot_clear' }))
    }
    win.webContents.send('devcore:screenshot:count', { count: 0 })
  })
  if (!registeredClear) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+X')

  // Start session (Ctrl+Shift+Enter)
  const registeredStart = globalShortcut.register('CommandOrControl+Return', () => {
    win.webContents.send('devcore:hotkey', { action: 'start' })
  })
  if (!registeredStart) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Return')

  // Focus ask input (Ctrl+Shift+/)
  const registeredAsk = globalShortcut.register('CommandOrControl+/', () => {
    win.setIgnoreMouseEvents(false)
    win.setFocusable(true)
    win.focus()
    win.webContents.send('devcore:hotkey', { action: 'ask' })
  })
  if (!registeredAsk) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+/')

  // Trigger AI suggestion from recent transcript (Ctrl+Shift+G)
  const registeredSuggest = globalShortcut.register('CommandOrControl+G', () => {
    win.webContents.send('devcore:hotkey', { action: 'suggest' })
  })
  if (!registeredSuggest) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+G')

  const registeredScrollDown = globalShortcut.register('CommandOrControl+Shift+Down', () => {
    win.webContents.send('devcore:hotkey', { action: 'scroll-down' })
  })
  if (!registeredScrollDown) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+Down')

  const registeredScrollUp = globalShortcut.register('CommandOrControl+Shift+Up', () => {
    win.webContents.send('devcore:hotkey', { action: 'scroll-up' })
  })
  if (!registeredScrollUp) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+Up')

  app.on('will-quit', () => globalShortcut.unregisterAll())
}


export function getOverlayWindow() { return overlayWin }
