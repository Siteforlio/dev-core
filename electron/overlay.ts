import { BrowserWindow, globalShortcut, app, screen } from 'electron'
import path from 'path'
import ffi = require('ffi-napi')
import Store = require('electron-store')

const store = new Store<{ overlayPosition: string }>()

const user32 = new ffi.Library('user32', {
  SetWindowDisplayAffinity: ['bool', ['pointer', 'uint32']]
})

const POSITIONS: Record<string, { x: () => number; y: () => number }> = {
  'top-center':    { x: () => Math.round((screen.getPrimaryDisplay().workAreaSize.width - 500) / 2), y: () => 8 },
  'top-left':      { x: () => 8,  y: () => 8 },
  'top-right':     { x: () => screen.getPrimaryDisplay().workAreaSize.width - 508, y: () => 8 },
  'bottom-center': { x: () => Math.round((screen.getPrimaryDisplay().workAreaSize.width - 500) / 2), y: () => screen.getPrimaryDisplay().workAreaSize.height - 120 },
  'bottom-right':  { x: () => screen.getPrimaryDisplay().workAreaSize.width - 508, y: () => screen.getPrimaryDisplay().workAreaSize.height - 120 },
}
const POSITION_ORDER = ['top-center', 'top-left', 'top-right', 'bottom-center', 'bottom-right']

let overlayWin: BrowserWindow | null = null
let currentPositionIndex = 0

export function createOverlayWindow(): BrowserWindow {
  if (overlayWin && !overlayWin.isDestroyed()) return overlayWin

  const savedPos = store.get('overlayPosition', 'top-center') as string
  currentPositionIndex = POSITION_ORDER.indexOf(savedPos) !== -1 ? POSITION_ORDER.indexOf(savedPos) : 0
  const pos = POSITIONS[POSITION_ORDER[currentPositionIndex]]

  overlayWin = new BrowserWindow({
    width: 500,
    height: 200,
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
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  overlayWin.setAlwaysOnTop(true, 'screen-saver')
  overlayWin.setIgnoreMouseEvents(true, { forward: true })

  // Apply WDA_EXCLUDEFROMCAPTURE — invisible to all screen capture on Windows 11
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hwnd = overlayWin.getNativeWindowHandle() as any
  const WDA_EXCLUDEFROMCAPTURE = 0x00000011
  user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)

  if (process.env.NODE_ENV === 'development') {
    overlayWin.loadURL('http://localhost:5173/overlay')
  } else {
    overlayWin.loadFile(path.join(__dirname, '../frontend/dist/index.html'), { hash: '/overlay' })
  }

  registerHotkeys(overlayWin)
  return overlayWin
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
