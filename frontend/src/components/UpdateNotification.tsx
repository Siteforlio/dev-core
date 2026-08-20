import { useEffect, useState } from 'react'

interface UpdateState {
  phase: 'available' | 'downloading' | 'ready'
  version: string
  percent: number
}

export default function UpdateNotification() {
  const [update, setUpdate] = useState<UpdateState | null>(null)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const api = (window as any).electronAPI?.updates
    if (!api) return

    const unsubs: (() => void)[] = []

    unsubs.push(api.onAvailable((info: { version: string }) => {
      setUpdate({ phase: 'available', version: info.version, percent: 0 })
      setDismissed(false)
    }))

    unsubs.push(api.onProgress((p: { percent: number }) => {
      setUpdate(prev => prev ? { ...prev, phase: 'downloading', percent: p.percent } : null)
    }))

    unsubs.push(api.onDownloaded((info: { version: string }) => {
      setUpdate({ phase: 'ready', version: info.version, percent: 100 })
      setDismissed(false)
    }))

    unsubs.push(api.onError(() => {
      setUpdate(null)
    }))

    return () => {
      unsubs.forEach(fn => fn())
      api.removeAllListeners?.()
    }
  }, [])

  if (!update || dismissed) return null

  return (
    <div className="fixed bottom-4 right-4 z-[9999] max-w-sm animate-in slide-in-from-bottom-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-4 flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center flex-shrink-0">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 2v8M8 2L5 5M8 2l3 3M3 11v1.5A1.5 1.5 0 004.5 14h7a1.5 1.5 0 001.5-1.5V11"
                  stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-white">
                {update.phase === 'ready' ? 'Update Ready' : `v${update.version} Available`}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                {update.phase === 'available' && 'Downloading update...'}
                {update.phase === 'downloading' && `Downloading... ${update.percent}%`}
                {update.phase === 'ready' && 'Restart to apply the update'}
              </p>
            </div>
          </div>
          {update.phase !== 'downloading' && (
            <button
              onClick={() => setDismissed(true)}
              className="text-gray-500 hover:text-gray-300 transition-colors p-0.5 -mt-0.5"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          )}
        </div>

        {/* Progress bar */}
        {(update.phase === 'available' || update.phase === 'downloading') && (
          <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${Math.max(update.percent, 2)}%` }}
            />
          </div>
        )}

        {/* Restart button */}
        {update.phase === 'ready' && (
          <button
            onClick={() => (window as any).electronAPI?.updates?.install()}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 rounded-lg transition-colors"
          >
            Restart & Update
          </button>
        )}
      </div>
    </div>
  )
}
