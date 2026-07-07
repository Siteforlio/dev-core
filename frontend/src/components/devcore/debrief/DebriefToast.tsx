interface Props {
  visible: boolean
  message: string
}

export default function DebriefToast({ visible, message }: Props) {
  if (!visible) return null

  return (
    <div style={{
      position: 'fixed',
      zIndex: 60,
      bottom: '28px',
      left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '12px 18px',
      borderRadius: '12px',
      background: '#050d18',
      border: '1px solid rgba(34,211,238,0.25)',
      color: '#e2e8f0',
      fontWeight: 600,
      fontSize: '13px',
      boxShadow: '0 20px 40px rgba(3,10,20,0.8), 0 0 20px rgba(34,211,238,0.08)',
      animation: 'dcPop .28s cubic-bezier(.2,.7,.2,1) both',
      whiteSpace: 'nowrap',
      fontFamily: "'Manrope', sans-serif",
    }}>
      <span style={{
        width: '20px', height: '20px',
        borderRadius: '50%',
        background: 'rgba(34,211,238,0.15)',
        border: '1px solid rgba(34,211,238,0.35)',
        display: 'grid',
        placeItems: 'center',
        flexShrink: 0,
        color: '#22d3ee',
      }}>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
          <path d="M5 12l5 5 9-11" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </span>
      {message}
    </div>
  )
}
