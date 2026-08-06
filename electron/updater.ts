/**
 * Auto-update logic using electron-updater.
 *
 * Checks github.com/Siteforlio/dev-core/releases for newer versions.
 * Downloads only changed bytes (block-map diff), then notifies the renderer
 * via IPC so it can show a "restart to update" prompt.
 *
 * Only active when app.isPackaged — no-op in dev mode.
 */
import { app, BrowserWindow, ipcMain } from 'electron'
import { autoUpdater, UpdateInfo } from 'electron-updater'
import log from 'electron-log'

// electron-updater uses electron-log for its own logging
autoUpdater.logger = log
;(autoUpdater.logger as any).transports.file.level = 'info'

// Do not auto-install on quit — let the user choose when to restart
autoUpdater.autoInstallOnAppQuit = false
autoUpdater.autoDownload = true  // download automatically, but don't install

function _sendToAll(channel: string, payload?: unknown) {
  BrowserWindow.getAllWindows().forEach(w => {
    if (!w.isDestroyed()) w.webContents.send(channel, payload)
  })
}

export function initUpdater(): void {
  if (!app.isPackaged) return  // no-op in dev

  autoUpdater.on('update-available', (info: UpdateInfo) => {
    log.info('[updater] update available:', info.version)
    _sendToAll('update:available', { version: info.version, releaseNotes: info.releaseNotes })
  })

  autoUpdater.on('update-not-available', () => {
    log.info('[updater] app is up to date')
  })

  autoUpdater.on('download-progress', (progress) => {
    _sendToAll('update:progress', {
      percent:        Math.round(progress.percent),
      transferred:    progress.transferred,
      total:          progress.total,
      bytesPerSecond: progress.bytesPerSecond,
    })
  })

  autoUpdater.on('update-downloaded', (info: UpdateInfo) => {
    log.info('[updater] update downloaded:', info.version)
    _sendToAll('update:downloaded', { version: info.version })
  })

  autoUpdater.on('error', (err: Error) => {
    log.error('[updater] error:', err)
    _sendToAll('update:error', { message: err.message })
  })

  // IPC: renderer requests install (triggers restart + update apply)
  ipcMain.handle('update:install', () => {
    autoUpdater.quitAndInstall(false, true)  // isSilent=false, isForceRunAfter=true
  })

  // Check for updates 5 seconds after startup (give the app time to settle)
  setTimeout(() => {
    autoUpdater.checkForUpdates().catch(err => {
      log.warn('[updater] check failed:', err.message)
    })
  }, 5_000)
}
