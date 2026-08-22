import { BrowserWindow, app, screen } from 'electron'
import path from 'path'
import Store = require('electron-store')

const store = new Store<{ overlayX: number; overlayY: number }>()

// ── Native function pointers ──
// Windows: user32.dll via koffi
// macOS:   ApplicationServices framework via koffi
// Both loaded lazily so the other platform doesn't crash.

type SetWindowDisplayAffinityFn = (hwnd: number, affinity: number) => boolean
type GetAsyncKeyStateFn = (vKey: number) => number
type CGEventSourceKeyStateFn = (stateID: number, keyCode: number) => boolean

let _setWindowDisplayAffinity: SetWindowDisplayAffinityFn | null = null
let _getAsyncKeyState: GetAsyncKeyStateFn | null = null
let _cgEventSourceKeyState: CGEventSourceKeyStateFn | null = null

if (process.platform === 'win32') {
  try {
    const koffi = require('koffi')
    const user32 = koffi.load('user32.dll')
    _setWindowDisplayAffinity = user32.func(
      'bool SetWindowDisplayAffinity(intptr_t hWnd, uint32 dwAffinity)',
    )
    _getAsyncKeyState = user32.func('short GetAsyncKeyState(int vKey)')
  } catch (e) {
    console.warn('[devcore-overlay] Failed to load user32.dll (non-fatal):', e)
  }
} else if (process.platform === 'darwin') {
  try {
    const koffi = require('koffi')
    const appSvc = koffi.load('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
    _cgEventSourceKeyState = appSvc.func('bool CGEventSourceKeyState(int32_t stateID, uint16_t keyCode)')
  } catch (e) {
    console.warn('[devcore-overlay] Failed to load ApplicationServices (non-fatal):', e)
  }
}

// ── Virtual key codes ──

// Windows VKs (used with GetAsyncKeyState)
const WIN_VK = {
  CTRL: 0x11, SHIFT: 0x10, SPACE: 0x20, RETURN: 0x0D,
  LEFT: 0x25, UP: 0x26, RIGHT: 0x27, DOWN: 0x28,
  G: 0x47, I: 0x49, R: 0x52, S: 0x53, X: 0x58, SLASH: 0xBF,
} as const

// macOS Carbon key codes (used with CGEventSourceKeyState)
// Uses Ctrl (not Cmd) — Ctrl combos are rare in macOS apps = less conflict + more stealth
const MAC_VK = {
  CTRL: 0x3B, SHIFT: 0x38, SPACE: 0x31, RETURN: 0x24,
  LEFT: 0x7B, UP: 0x7E, RIGHT: 0x7C, DOWN: 0x7D,
  G: 0x05, I: 0x22, R: 0x0F, S: 0x01, X: 0x07, SLASH: 0x2C,
} as const

// ── Unified key state helpers ──

function _winDown(vk: number): boolean {
  return _getAsyncKeyState ? (_getAsyncKeyState(vk) & 0x8000) !== 0 : false
}

function _macDown(vk: number): boolean {
  // kCGEventSourceStateCombinedSessionState = 0
  return _cgEventSourceKeyState ? _cgEventSourceKeyState(0, vk) : false
}

function _modDown(): boolean {
  if (process.platform === 'win32') return _winDown(WIN_VK.CTRL)
  if (process.platform === 'darwin') return _macDown(MAC_VK.CTRL)
  return false
}

function _shiftDown(): boolean {
  if (process.platform === 'win32') return _winDown(WIN_VK.SHIFT)
  if (process.platform === 'darwin') return _macDown(MAC_VK.SHIFT)
  return false
}

function _keyDown(winVk: number, macVk: number): boolean {
  if (process.platform === 'win32') return _winDown(winVk)
  if (process.platform === 'darwin') return _macDown(macVk)
  return false
}

// ── Edge detection — fires once on key-down, not while held ──

const _prevCombo: Record<string, boolean> = {}

function _edge(id: string, pressed: boolean): boolean {
  const was = _prevCombo[id] ?? false
  _prevCombo[id] = pressed
  return pressed && !was
}

// ── Constants ──

const MOVE_STEP = 20        // px per arrow key press
const CONTENT_MARGIN = 50   // min px from screen edge
const HOVER_PADDING = 8     // px extra hit-area for cursor detection
const POLL_INTERVAL = 30    // ms — ~33fps, imperceptible lag, < 1% CPU

// ── Content position (CSS left/top within the full-screen transparent window) ──

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

// ── Interact mode (unified) ──
// Two independent sources: cursor hover detection + manual hotkey toggle.
// The window receives mouse events when EITHER is active.

let _forceInteract = false   // toggled by Ctrl+I or IPC from renderer
let _hoverInteract = false   // set by cursor proximity detection
let _isInteractMode = false  // combined state applied to window

function _updateInteract(win: BrowserWindow) {
  const should = _forceInteract || _hoverInteract
  if (should === _isInteractMode) return
  _isInteractMode = should
  if (should) {
    win.setIgnoreMouseEvents(false)
    win.setFocusable(true)
    if (_forceInteract) win.focus()
  } else {
    win.setIgnoreMouseEvents(true, { forward: true })
    win.setFocusable(false)
  }
}

// Exported for main.ts IPC handlers (renderer input focus/blur)
export function enableInteract() {
  if (!overlayWin || overlayWin.isDestroyed()) return
  _forceInteract = true
  _updateInteract(overlayWin)
}

export function disableInteract() {
  if (!overlayWin || overlayWin.isDestroyed()) return
  _forceInteract = false
  _updateInteract(overlayWin)
}

// ── Content bounds (from renderer ResizeObserver → cursor hit-test) ──

let _contentBounds = { x: 0, y: 0, width: 0, height: 0 }

export function setOverlayContentBounds(bounds: { x: number; y: number; width: number; height: number }) {
  _contentBounds = bounds
}

// ── Stealth mode (screen-capture exclusion) ──

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
        console.log('[devcore-overlay] WDA_EXCLUDEFROMCAPTURE applied — hwnd=', hwnd)
      } else {
        console.error('[devcore-overlay] SetWindowDisplayAffinity returned false — hwnd=', hwnd)
      }
    } catch (e) {
      console.warn('[devcore-overlay] SetWindowDisplayAffinity failed (non-fatal):', e)
    }
  } else if (process.platform === 'darwin') {
    win.setContentProtection(true)
    console.log('[devcore-overlay] setContentProtection(true) applied (macOS stealth)')
  } else {
    console.info('[devcore-overlay] No screen-capture exclusion API on Linux')
  }
}

// ── Overlay window ──

let overlayWin: BrowserWindow | null = null
let _pollTimer: ReturnType<typeof setInterval> | null = null

export function createOverlayWindow(): BrowserWindow {
  if (overlayWin && !overlayWin.isDestroyed()) return overlayWin

  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize
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

  // Apply stealth twice: early + after paint (Windows resets on compositor init)
  _applyStealthMode(overlayWin)
  overlayWin.webContents.once('did-finish-load', () => {
    if (overlayWin && !overlayWin.isDestroyed()) {
      _applyStealthMode(overlayWin)
      overlayWin.webContents.send('devcore:overlay:move', { x: _contentX, y: _contentY })
    }
  })

  // Windows resets WDA_EXCLUDEFROMCAPTURE on hide→show transitions
  overlayWin.on('show', () => {
    if (overlayWin && !overlayWin.isDestroyed()) _applyStealthMode(overlayWin)
  })

  if (process.env.NODE_ENV === 'development') {
    overlayWin.loadURL('http://localhost:5173/overlay.html')
    overlayWin.webContents.openDevTools({ mode: 'detach' })
  } else {
    overlayWin.loadFile(path.join(__dirname, '../frontend/dist/overlay.html'))
  }

  // Start the unified poll loop (cursor hover + stealth key detection)
  _startPollLoop(overlayWin)

  overlayWin.on('closed', () => {
    _stopPollLoop()
    overlayWin = null
  })

  return overlayWin
}

// ── Unified poll loop (cursor hover + key detection) ──
// Runs at 30ms intervals (~33fps). Replaces both:
//   1. The old cursor-only poll (_startCursorPoll)
//   2. Electron's globalShortcut hotkey registration
//
// Using GetAsyncKeyState/CGEventSourceKeyState instead of globalShortcut means:
//   - No RegisterHotKey calls → invisible to proctoring software
//   - No SetWindowsHookEx → invisible to hook enumerators
//   - No system hotkey table entries → invisible to keyboard monitors
//   - Key events pass through to the focused app → no conflicts with Ctrl+S etc.

function _startPollLoop(win: BrowserWindow) {
  _stopPollLoop()

  _pollTimer = setInterval(() => {
    if (!win || win.isDestroyed()) return

    // ── Cursor hover detection ──
    if (win.isVisible()) {
      const cursor = screen.getCursorScreenPoint()
      const [wx, wy] = win.getPosition()
      const lx = cursor.x - wx
      const ly = cursor.y - wy
      const b = _contentBounds
      const isOver = b.width > 0 && (
        lx >= b.x - HOVER_PADDING && lx <= b.x + b.width + HOVER_PADDING &&
        ly >= b.y - HOVER_PADDING && ly <= b.y + b.height + HOVER_PADDING
      )
      if (isOver !== _hoverInteract) {
        _hoverInteract = isOver
        _updateInteract(win)
      }
    }

    // ── Stealth key detection ──
    // Skip if no native key polling available (Linux fallback)
    if (!_getAsyncKeyState && !_cgEventSourceKeyState) return

    const mod = _modDown()
    const shift = _shiftDown()

    // Ctrl+Space — show/hide overlay
    if (_edge('mod+space', mod && !shift && _keyDown(WIN_VK.SPACE, MAC_VK.SPACE))) {
      if (win.isVisible()) {
        win.hide()
      } else {
        win.show()
        _applyStealthMode(win)
      }
    }

    // Ctrl+I — toggle forced interact mode
    if (_edge('mod+i', mod && !shift && _keyDown(WIN_VK.I, MAC_VK.I))) {
      _forceInteract = !_forceInteract
      _updateInteract(win)
    }

    // Ctrl+Arrow — move overlay content
    if (_edge('mod+right', mod && !shift && _keyDown(WIN_VK.RIGHT, MAC_VK.RIGHT))) {
      _moveContent(win, _contentX + MOVE_STEP, _contentY)
    }
    if (_edge('mod+left', mod && !shift && _keyDown(WIN_VK.LEFT, MAC_VK.LEFT))) {
      _moveContent(win, _contentX - MOVE_STEP, _contentY)
    }
    if (_edge('mod+down', mod && !shift && _keyDown(WIN_VK.DOWN, MAC_VK.DOWN))) {
      _moveContent(win, _contentX, _contentY + MOVE_STEP)
    }
    if (_edge('mod+up', mod && !shift && _keyDown(WIN_VK.UP, MAC_VK.UP))) {
      _moveContent(win, _contentX, _contentY - MOVE_STEP)
    }

    // Ctrl+R — force re-trigger thinking state
    if (_edge('mod+r', mod && !shift && _keyDown(WIN_VK.R, MAC_VK.R))) {
      win.webContents.send('devcore:status', { state: 'thinking', latencyMs: 0 })
    }

    // Ctrl+S — screenshot capture
    if (_edge('mod+s', mod && !shift && _keyDown(WIN_VK.S, MAC_VK.S))) {
      import('./audio').then(({ captureAndSendScreenshot }) => {
        captureAndSendScreenshot()
      })
      win.webContents.send('devcore:hotkey', { action: 'screenshot' })
    }

    // Ctrl+X — clear screenshot buffer
    if (_edge('mod+x', mod && !shift && _keyDown(WIN_VK.X, MAC_VK.X))) {
      const sock = require('./audio').getActiveWs?.()
      if (sock && sock.readyState === 1) {
        sock.send(JSON.stringify({ type: 'screenshot_clear' }))
      }
      win.webContents.send('devcore:screenshot:count', { count: 0 })
    }

    // Ctrl+Enter — start session
    if (_edge('mod+enter', mod && !shift && _keyDown(WIN_VK.RETURN, MAC_VK.RETURN))) {
      win.webContents.send('devcore:hotkey', { action: 'start' })
    }

    // Ctrl+/ — focus ask input (also enables interact so typing works)
    if (_edge('mod+slash', mod && !shift && _keyDown(WIN_VK.SLASH, MAC_VK.SLASH))) {
      _forceInteract = true
      _updateInteract(win)
      win.webContents.send('devcore:hotkey', { action: 'ask' })
    }

    // Ctrl+G — trigger AI suggestion (immediate "thinking" feedback)
    if (_edge('mod+g', mod && !shift && _keyDown(WIN_VK.G, MAC_VK.G))) {
      // Show thinking state within 30ms of keypress — don't wait for backend round trip
      win.webContents.send('devcore:status', { state: 'thinking', latencyMs: 0 })
      win.webContents.send('devcore:hotkey', { action: 'suggest' })
    }

    // Ctrl+Shift+Down/Up — scroll suggestion card
    if (_edge('mod+shift+down', mod && shift && _keyDown(WIN_VK.DOWN, MAC_VK.DOWN))) {
      win.webContents.send('devcore:hotkey', { action: 'scroll-down' })
    }
    if (_edge('mod+shift+up', mod && shift && _keyDown(WIN_VK.UP, MAC_VK.UP))) {
      win.webContents.send('devcore:hotkey', { action: 'scroll-up' })
    }
  }, POLL_INTERVAL)
}

function _stopPollLoop() {
  if (_pollTimer) {
    clearInterval(_pollTimer)
    _pollTimer = null
  }
}

app.on('will-quit', _stopPollLoop)

export function getOverlayWindow() { return overlayWin }
