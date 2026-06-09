/** Shared modal — asks whether to save login credentials after auth */
export function SaveCredsModal({
  email,
  onYes,
  onNo,
}: {
  email: string
  onYes: () => void
  onNo: () => void
}) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(2,8,16,0.88)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      animation: 'sc-fade-in 0.18s ease both',
    }}>
      <div style={{
        width: '380px',
        background: 'linear-gradient(160deg, #030f1e 0%, #020c18 100%)',
        border: '1px solid rgba(34,211,238,0.15)',
        borderRadius: '16px',
        padding: '32px 28px 28px',
        boxShadow: '0 0 0 1px rgba(34,211,238,0.04), 0 32px 64px rgba(0,0,0,0.6), 0 0 80px rgba(34,211,238,0.05)',
        animation: 'sc-slide-up 0.22s cubic-bezier(0.34,1.56,0.64,1) both',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '20px' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '10px', flexShrink: 0,
            background: 'radial-gradient(circle at 30% 30%, rgba(34,211,238,0.15), rgba(34,211,238,0.04))',
            border: '1px solid rgba(34,211,238,0.18)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 20px rgba(34,211,238,0.07)',
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2"/>
              <path d="M7 11V7a5 5 0 0110 0v4"/>
              <circle cx="12" cy="16" r="1" fill="#22d3ee"/>
            </svg>
          </div>
          <div>
            <p style={{ fontFamily: '"Orbitron", monospace', fontSize: '12px', fontWeight: 700, letterSpacing: '0.12em', color: 'rgba(226,232,240,0.95)', marginBottom: '3px' }}>
              Save Credentials?
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#34d399', boxShadow: '0 0 6px #34d399' }} />
              <span style={{ fontFamily: 'monospace', fontSize: '9px', letterSpacing: '0.14em', color: 'rgba(52,211,153,0.7)', textTransform: 'uppercase' }}>
                Windows DPAPI encrypted
              </span>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: '1px', background: 'linear-gradient(90deg, rgba(34,211,238,0.12), transparent)', marginBottom: '20px' }} />

        {/* Body */}
        <p style={{ fontFamily: 'monospace', fontSize: '12px', color: 'rgba(148,163,184,0.7)', lineHeight: 1.7, marginBottom: '8px' }}>
          Store credentials for{' '}
          <span style={{ color: '#22d3ee', fontWeight: 600 }}>{email}</span>
          {' '}so next time you can log in with one click.
        </p>
        <p style={{ fontFamily: 'monospace', fontSize: '10px', color: 'rgba(100,116,139,0.45)', lineHeight: 1.6, marginBottom: '24px' }}>
          Your password is encrypted on disk — unreadable without your Windows account.
        </p>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={onYes}
            style={{
              flex: 1, padding: '12px',
              background: 'rgba(34,211,238,0.08)',
              border: '1px solid rgba(34,211,238,0.3)',
              borderRadius: '10px',
              color: '#22d3ee',
              fontFamily: '"Orbitron", monospace',
              fontSize: '10px', fontWeight: 700,
              letterSpacing: '0.16em', textTransform: 'uppercase',
              cursor: 'pointer',
              transition: 'all 0.15s',
              boxShadow: '0 0 16px rgba(34,211,238,0.04)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(34,211,238,0.15)'
              e.currentTarget.style.boxShadow = '0 0 20px rgba(34,211,238,0.12)'
              e.currentTarget.style.borderColor = 'rgba(34,211,238,0.5)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(34,211,238,0.08)'
              e.currentTarget.style.boxShadow = '0 0 16px rgba(34,211,238,0.04)'
              e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)'
            }}
          >
            Save
          </button>
          <button
            onClick={onNo}
            style={{
              flex: 1, padding: '12px',
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: '10px',
              color: 'rgba(100,116,139,0.55)',
              fontFamily: 'monospace',
              fontSize: '11px',
              letterSpacing: '0.12em',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.14)'
              e.currentTarget.style.color = 'rgba(148,163,184,0.75)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'
              e.currentTarget.style.color = 'rgba(100,116,139,0.55)'
            }}
          >
            Not now
          </button>
        </div>
      </div>

      <style>{`
        @keyframes sc-fade-in { from { opacity: 0 } to { opacity: 1 } }
        @keyframes sc-slide-up { from { opacity: 0; transform: translateY(16px) scale(0.97) } to { opacity: 1; transform: translateY(0) scale(1) } }
      `}</style>
    </div>
  )
}
