import React, { useState, useEffect } from 'react'

// Extension ID storage key — persisted to localStorage so Electron renderer remembers
const EXT_ID_KEY = 'jh_ext_id'

export const getStoredExtId = (): string | null => localStorage.getItem(EXT_ID_KEY)

export const ExtensionBanner: React.FC = () => {
  const [visible, setVisible] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [extIdInput, setExtIdInput] = useState('')

  useEffect(() => {
    // Already confirmed — don't show banner
    if (localStorage.getItem(EXT_ID_KEY)) return
    // DOM attribute set by content script (only works in Chrome, not Electron)
    const domId = document.documentElement.getAttribute('data-jh-ext-id')
    if (domId) {
      localStorage.setItem(EXT_ID_KEY, domId)
      return
    }
    setVisible(true)
  }, [])

  if (!visible) return null

  const dismiss = () => setVisible(false)

  const confirmInstalled = () => {
    const id = extIdInput.trim() || 'installed'
    localStorage.setItem(EXT_ID_KEY, id)
    setVisible(false)
    setShowModal(false)
  }

  return (
    <>
      <div style={{
        background: '#1e293b',
        borderBottom: '1px solid #334155',
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        fontSize: '13px',
        color: '#94a3b8',
        flexShrink: 0,
      }}>
        <span>⚡</span>
        <span style={{ flex: 1 }}>
          Install the <strong style={{ color: '#e2e8f0' }}>Job Hunter extension</strong> to auto-fill job application forms
        </span>
        <button
          onClick={() => setShowModal(true)}
          style={{
            background: '#334155',
            border: 'none',
            borderRadius: '4px',
            padding: '4px 10px',
            color: '#e2e8f0',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          Install Instructions
        </button>
        <button
          onClick={dismiss}
          style={{
            background: 'none',
            border: 'none',
            color: '#64748b',
            cursor: 'pointer',
            fontSize: '16px',
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      {showModal && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '24px',
            maxWidth: '420px',
            width: '90%',
            color: '#e2e8f0',
          }}>
            <h3 style={{ marginBottom: '16px', color: '#f8fafc', margin: '0 0 16px 0' }}>
              Install Job Hunter Extension
            </h3>
            <ol style={{ paddingLeft: '20px', lineHeight: '2', color: '#94a3b8', fontSize: '14px', margin: 0 }}>
              <li>Open <code style={{ color: '#67e8f9' }}>chrome://extensions</code> in Chrome</li>
              <li>Enable <strong style={{ color: '#e2e8f0' }}>Developer mode</strong> (toggle, top-right)</li>
              <li>Click <strong style={{ color: '#e2e8f0' }}>Load unpacked</strong> → select the <code style={{ color: '#67e8f9' }}>chrome-extension/</code> folder in this project</li>
              <li>Copy the extension <strong style={{ color: '#e2e8f0' }}>ID</strong> shown on the extensions page</li>
            </ol>
            <div style={{ marginTop: '16px' }}>
              <label style={{ fontSize: '12px', color: '#64748b', display: 'block', marginBottom: '6px' }}>
                Paste your extension ID (from chrome://extensions):
              </label>
              <input
                value={extIdInput}
                onChange={e => setExtIdInput(e.target.value)}
                placeholder="e.g. gpmobladhmkeafcppadjljggmfkgcbfp"
                style={{
                  width: '100%',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '6px',
                  padding: '7px 10px',
                  color: '#e2e8f0',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                }}
              />
            </div>
            <button
              onClick={confirmInstalled}
              style={{
                marginTop: '12px',
                background: '#0f2a1a',
                border: '1px solid #1a3d24',
                borderRadius: '6px',
                padding: '8px 16px',
                color: '#34d399',
                cursor: 'pointer',
                width: '100%',
                fontWeight: 600,
              }}
            >
              ✓ I've installed it
            </button>
            <button
              onClick={() => setShowModal(false)}
              style={{
                marginTop: '8px',
                background: 'none',
                border: 'none',
                borderRadius: '6px',
                padding: '6px 16px',
                color: '#64748b',
                cursor: 'pointer',
                width: '100%',
                fontSize: '12px',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </>
  )
}
