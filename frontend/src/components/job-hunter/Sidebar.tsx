type Module = 'interview' | 'job-hunter' | 'settings'

interface NavItem {
  module: Module
  label: string
  icon: string
}

interface Props {
  activeModule: Module
  onSelect: (module: Module) => void
}

const NAV_ITEMS: NavItem[] = [
  { module: 'interview', label: 'Interview Prep', icon: '🎯' },
  { module: 'job-hunter', label: 'Job Hunter', icon: '🔍' },
]

export default function Sidebar({ activeModule, onSelect }: Props) {
  return (
    <nav className="w-14 flex-shrink-0 bg-gray-950 border-r border-gray-800 flex flex-col items-center py-4 gap-2">
      {NAV_ITEMS.map(({ module, label, icon }) => (
        <button
          key={module}
          title={label}
          onClick={() => onSelect(module)}
          className={`w-10 h-10 flex items-center justify-center rounded-lg text-lg transition-colors ${
            activeModule === module
              ? 'bg-gray-800 text-white'
              : 'text-gray-500 hover:text-gray-300 hover:bg-gray-900'
          }`}
        >
          {icon}
        </button>
      ))}

      {/* Spacer pushes settings to bottom */}
      <div className="flex-1" />

      <button
        title="Settings"
        onClick={() => onSelect('settings')}
        className={`w-10 h-10 flex items-center justify-center rounded-lg text-lg transition-colors ${
          activeModule === 'settings'
            ? 'bg-gray-800 text-white'
            : 'text-gray-500 hover:text-gray-300 hover:bg-gray-900'
        }`}
      >
        ⚙️
      </button>
    </nav>
  )
}
