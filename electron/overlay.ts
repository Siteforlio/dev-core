import { BrowserWindow, globalShortcut, app, screen } from 'electron'
import path from 'path'
import Store = require('electron-store')

const store = new Store<{ overlayPosition: string }>()

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

const POSITIONS: Record<string, { x: () => number; y: () => number }> = {
  'top-center':    { x: () => Math.round(screen.getPrimaryDisplay().workAreaSize.width * 0.075), y: () => 0 },
  'top-left':      { x: () => 0, y: () => 0 },
  'top-right':     { x: () => Math.round(screen.getPrimaryDisplay().workAreaSize.width * 0.15), y: () => 0 },
  'bottom-center': { x: () => Math.round(screen.getPrimaryDisplay().workAreaSize.width * 0.075), y: () => Math.round(screen.getPrimaryDisplay().workAreaSize.height * 0.15) },
  'bottom-right':  { x: () => Math.round(screen.getPrimaryDisplay().workAreaSize.width * 0.15), y: () => Math.round(screen.getPrimaryDisplay().workAreaSize.height * 0.15) },
}
const POSITION_ORDER = ['top-center', 'top-left', 'top-right', 'bottom-center', 'bottom-right']

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
    if (!_setWindowDisplayAffinity) return
    try {
      const hwndBuf = win.getNativeWindowHandle()
      const hwnd = process.arch === 'x64'
        ? Number(hwndBuf.readBigInt64LE(0))
        : hwndBuf.readInt32LE(0)
      const WDA_EXCLUDEFROMCAPTURE = 0x00000011
      _setWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
      console.log('[devcore-overlay] WDA_EXCLUDEFROMCAPTURE applied (Windows stealth)')
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
let currentPositionIndex = 0

// Content bounds sent from the renderer — used by the polling loop
// to decide whether the cursor is over the actual UI (not just the transparent window).
let _contentBounds = { x: 0, y: 0, width: 0, height: 0 }
const HOVER_PADDING = 8   // px extra hit-area so near-edge clicks aren't missed
let _pollTimer: ReturnType<typeof setInterval> | null = null
let _isInteractMode = false

export function createOverlayWindow(): BrowserWindow {
  if (overlayWin && !overlayWin.isDestroyed()) return overlayWin

  const savedPos = store.get('overlayPosition', 'top-center') as string
  currentPositionIndex = POSITION_ORDER.indexOf(savedPos) !== -1 ? POSITION_ORDER.indexOf(savedPos) : 0
  const pos = POSITIONS[POSITION_ORDER[currentPositionIndex]]

  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize
  overlayWin = new BrowserWindow({
    width: Math.round(sw * 0.85),
    height: Math.round(sh * 0.85),
    x: pos.x(),
    y: pos.y(),
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
  // invisible to OBS, Zoom, Teams, etc.
  _applyStealthMode(overlayWin)

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
  // Show/hide
  const registeredSpace = globalShortcut.register('CommandOrControl+Shift+Space', () => {
    if (win.isVisible()) win.hide()
    else win.show()
  })
  if (!registeredSpace) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+Space')

  // Interact mode toggle
  let interactMode = false
  const registeredI = globalShortcut.register('CommandOrControl+Shift+I', () => {
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
  if (!registeredI) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+I')

  // Move overlay
  const registeredRight = globalShortcut.register('CommandOrControl+Shift+Right', () => cyclePosition(win, 1))
  if (!registeredRight) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+Right')

  const registeredLeft = globalShortcut.register('CommandOrControl+Shift+Left', () => cyclePosition(win, -1))
  if (!registeredLeft) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+Left')

  // Force re-trigger
  const registeredR = globalShortcut.register('CommandOrControl+Shift+R', () => {
    win.webContents.send('devcore:status', { state: 'thinking', latencyMs: 0 })
  })
  if (!registeredR) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+R')

  // Start session (Ctrl+Shift+Enter)
  const registeredStart = globalShortcut.register('CommandOrControl+Shift+Return', () => {
    win.webContents.send('devcore:hotkey', { action: 'start' })
  })
  if (!registeredStart) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+Return')

  // Focus ask input (Ctrl+Shift+/)
  const registeredAsk = globalShortcut.register('CommandOrControl+Shift+/', () => {
    win.setIgnoreMouseEvents(false)
    win.setFocusable(true)
    win.focus()
    win.webContents.send('devcore:hotkey', { action: 'ask' })
  })
  if (!registeredAsk) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+/')

  // Trigger AI suggestion from recent transcript (Ctrl+Shift+G)
  const registeredSuggest = globalShortcut.register('CommandOrControl+Shift+G', () => {
    win.webContents.send('devcore:hotkey', { action: 'suggest' })
  })
  if (!registeredSuggest) console.warn('[devcore-overlay] Failed to register hotkey: CommandOrControl+Shift+G')

  app.on('will-quit', () => globalShortcut.unregisterAll())
}

function cyclePosition(win: BrowserWindow, dir: 1 | -1) {
  currentPositionIndex = (currentPositionIndex + dir + POSITION_ORDER.length) % POSITION_ORDER.length
  const posKey = POSITION_ORDER[currentPositionIndex]
  const pos = POSITIONS[posKey]
  win.setPosition(pos.x(), pos.y())
  store.set('overlayPosition', posKey)
}

export function getOverlayWindow() { return overlayWin }
