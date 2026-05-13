type Module = 'interview' | 'job-hunter' | 'settings'

interface NavItem {
  module: Module
  label: string
  icon: React.ReactNode
}

interface Props {
  activeModule: Module
  onSelect: (module: Module) => void
  onLogout: () => void
}

const IconInterview = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="4" />
    <line x1="12" y1="2" x2="12" y2="5" />
    <line x1="12" y1="19" x2="12" y2="22" />
    <line x1="2" y1="12" x2="5" y2="12" />
    <line x1="19" y1="12" x2="22" y2="12" />
  </svg>
)

const IconJobHunter = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" />
    <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
    <line x1="12" y1="12" x2="12" y2="16" />
    <line x1="10" y1="14" x2="14" y2="14" />
  </svg>
)

const IconSettings = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
)

const IconLogout = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
)

const DevCoreLogo = () => (
  <img src="/devcore.png" width="34" height="34" alt="DevCore" style={{ objectFit: 'contain' }} />
)

const NAV_ITEMS: NavItem[] = [
  { module: 'interview', label: 'Interview Prep', icon: <IconInterview /> },
  { module: 'job-hunter', label: 'Job Hunter', icon: <IconJobHunter /> },
]

export default function Sidebar({ activeModule, onSelect, onLogout }: Props) {
  return (
    <nav
      className="w-16 flex-shrink-0 flex flex-col items-center py-0 gap-0"
      style={{
        background: 'linear-gradient(180deg, #050d18 0%, #060e1a 100%)',
        borderRight: '1px solid rgba(34,211,238,0.08)',
      }}
    >
      {/* Nav items */}
      <div className="flex flex-col items-center gap-1 py-4 w-full">
        {NAV_ITEMS.map(({ module, label, icon }) => (
          <button
            key={module}
            title={label}
            onClick={() => onSelect(module)}
            className="relative w-full flex items-center justify-center transition-all duration-150"
            style={{
              height: '48px',
              color: activeModule === module ? '#22d3ee' : 'rgba(148,163,184,0.5)',
            }}
          >
            {activeModule === module && (
              <span
                className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 rounded-r"
                style={{
                  height: '24px',
                  background: '#22d3ee',
                  boxShadow: '0 0 8px rgba(34,211,238,0.8)',
                }}
              />
            )}
            <span
              className="flex items-center justify-center rounded transition-all duration-150"
              style={{
                width: '40px',
                height: '40px',
                background: activeModule === module ? 'rgba(34,211,238,0.08)' : 'transparent',
              }}
            >
              {icon}
            </span>
          </button>
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Settings */}
      <div className="flex flex-col items-center gap-1 pb-2 w-full">
        <button
          title="Settings"
          onClick={() => onSelect('settings')}
          className="relative w-full flex items-center justify-center transition-all duration-150"
          style={{
            height: '48px',
            color: activeModule === 'settings' ? '#22d3ee' : 'rgba(148,163,184,0.5)',
          }}
        >
          {activeModule === 'settings' && (
            <span
              className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 rounded-r"
              style={{
                height: '24px',
                background: '#22d3ee',
                boxShadow: '0 0 8px rgba(34,211,238,0.8)',
              }}
            />
          )}
          <span
            className="flex items-center justify-center rounded transition-all duration-150"
            style={{
              width: '40px',
              height: '40px',
              background: activeModule === 'settings' ? 'rgba(34,211,238,0.08)' : 'transparent',
            }}
          >
            <IconSettings />
          </span>
        </button>

        {/* Divider */}
        <div
          className="w-8 my-1"
          style={{ height: '1px', background: 'rgba(34,211,238,0.08)' }}
        />

        {/* Logout */}
        <button
          title="Sign out"
          onClick={onLogout}
          className="w-full flex items-center justify-center transition-all duration-150 mb-2"
          style={{
            height: '48px',
            color: 'rgba(148,163,184,0.4)',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = '#f87171')}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(148,163,184,0.4)')}
        >
          <span className="flex items-center justify-center rounded" style={{ width: '40px', height: '40px' }}>
            <IconLogout />
          </span>
        </button>
      </div>
    </nav>
  )
}
