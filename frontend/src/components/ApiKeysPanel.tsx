import { useState, useEffect, useRef } from 'react'
import { useApiKeys, type ApiKeyInfo } from '../hooks/useApiKeys'

/* ── Provider logos (inline SVG) ── */

const LogoDeepSeek = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="#4D6BFE" opacity="0.15"/>
    <path d="M12 5a7 7 0 100 14 7 7 0 000-14zm0 2.5a1.25 1.25 0 110 2.5 1.25 1.25 0 010-2.5zM10 12h4v5h-1.5v-3.5h-1V17H10v-5z" fill="#4D6BFE"/>
  </svg>
)
const LogoDeepgram = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#13EF93" opacity="0.15"/>
    <path d="M7 8v8M10 6v12M13 9v6M16 7v10M19 10v4" stroke="#13EF93" strokeWidth="1.8" strokeLinecap="round"/>
  </svg>
)
const LogoAnthropic = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M12 3L3 21h4.5l1.8-3.6h5.4L16.5 21H21L12 3zm0 6.6L14.4 15h-4.8L12 9.6z" fill="#D4A574"/>
  </svg>
)
const LogoGoogle = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09A6.96 6.96 0 015.5 12c0-.72.13-1.43.34-2.09V7.07H2.18A11 11 0 001 12c0 1.77.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
)
const LogoGroq = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#F55036" opacity="0.15"/>
    <path d="M12 6a6 6 0 100 12 6 6 0 000-12zm0 2a4 4 0 110 8 4 4 0 010-8z" fill="#F55036"/>
    <circle cx="12" cy="12" r="1.5" fill="#F55036"/>
  </svg>
)
const LogoOpenAI = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M22.28 9.37a5.97 5.97 0 00-.52-4.93 6.06 6.06 0 00-6.52-2.91A5.97 5.97 0 0010.72 0a6.06 6.06 0 00-5.78 4.18 5.97 5.97 0 00-4 2.9 6.06 6.06 0 00.74 7.1 5.97 5.97 0 00.52 4.93 6.06 6.06 0 006.52 2.91A5.97 5.97 0 0013.27 24a6.06 6.06 0 005.78-4.18 5.97 5.97 0 004-2.9 6.06 6.06 0 00-.74-7.1z" fill="rgba(255,255,255,0.85)" transform="scale(0.8) translate(3,3)"/>
  </svg>
)
const LogoHeyGen = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#6C5CE7" opacity="0.15"/>
    <circle cx="12" cy="10" r="3.5" stroke="#6C5CE7" strokeWidth="1.5"/>
    <path d="M7 18c0-2.76 2.24-5 5-5s5 2.24 5 5" stroke="#6C5CE7" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M16 8l2-2M16 6l2 2" stroke="#6C5CE7" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
)
const LogoSimli = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#00D2FF" opacity="0.15"/>
    <path d="M8 8h8v8H8z" stroke="#00D2FF" strokeWidth="1.5" strokeLinejoin="round"/>
    <circle cx="11" cy="11" r="1" fill="#00D2FF"/>
    <circle cx="14" cy="11" r="1" fill="#00D2FF"/>
    <path d="M10.5 14c.83.5 2.17.5 3 0" stroke="#00D2FF" strokeWidth="1" strokeLinecap="round"/>
  </svg>
)
const LogoJudge0 = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#E8D44D" opacity="0.15"/>
    <path d="M7 7l3 3-3 3M12 16h5" stroke="#E8D44D" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const LogoSerpAPI = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#68A063" opacity="0.15"/>
    <circle cx="11" cy="11" r="5" stroke="#68A063" strokeWidth="1.8"/>
    <path d="M15 15l4 4" stroke="#68A063" strokeWidth="1.8" strokeLinecap="round"/>
  </svg>
)
const LogoAdzuna = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#64BC46" opacity="0.15"/>
    <path d="M8 16V8l4 4 4-4v8" stroke="#64BC46" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const LogoReed = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#D63384" opacity="0.15"/>
    <path d="M8 7v10M8 7c0 0 0-1 2-1s2.5 1.5 2.5 2.5S11 10 9 11" stroke="#D63384" strokeWidth="1.8" strokeLinecap="round"/>
    <path d="M9 11l4 6" stroke="#D63384" strokeWidth="1.8" strokeLinecap="round"/>
  </svg>
)
const LogoScrapfly = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="4" fill="#FF6B35" opacity="0.15"/>
    <path d="M6 12c2-4 4-6 6-6s4 2 6 6c-2 4-4 6-6 6s-4-2-6-6z" stroke="#FF6B35" strokeWidth="1.5"/>
    <circle cx="12" cy="12" r="2" fill="#FF6B35"/>
  </svg>
)

/* ── Logo map ── */
const LOGOS: Record<string, React.ReactNode> = {
  deepseek_api_key: <LogoDeepSeek />,
  deepgram_api_key: <LogoDeepgram />,
  anthropic_api_key: <LogoAnthropic />,
  gemini_api_key: <LogoGoogle />,
  groq_api_key: <LogoGroq />,
  openai_api_key: <LogoOpenAI />,
  heygen_api_key: <LogoHeyGen />,
  simli_api_key: <LogoSimli />,
  judge0_api_key: <LogoJudge0 />,
  serp_api_key: <LogoSerpAPI />,
  adzuna_app_id: <LogoAdzuna />,
  adzuna_api_key: <LogoAdzuna />,
  reed_api_key: <LogoReed />,
  scrapfly_key: <LogoScrapfly />,
}

/* ── Provider metadata ── */
interface ProviderMeta {
  label: string
  description: string
  placeholder: string
  helpUrl: string
  helpLabel: string
  vision?: boolean
  recommended?: boolean
  freeTier?: boolean
}

const META: Record<string, ProviderMeta> = {
  deepseek_api_key: { label: 'DeepSeek', description: 'Fast, affordable LLM — powers interviews, job search, and overlay', placeholder: 'sk-...', helpUrl: 'https://platform.deepseek.com/api_keys', helpLabel: 'Get free key', recommended: true, freeTier: true },
  anthropic_api_key: { label: 'Anthropic (Claude)', description: 'Premium LLM with vision — powers screenshot analysis in overlay', placeholder: 'sk-ant-...', helpUrl: 'https://console.anthropic.com', helpLabel: 'Get API key', vision: true, recommended: true },
  gemini_api_key: { label: 'Google Gemini', description: 'Fast multimodal LLM with vision support', placeholder: 'AI...', helpUrl: 'https://aistudio.google.com/apikey', helpLabel: 'Get API key', vision: true, freeTier: true },
  openai_api_key: { label: 'OpenAI', description: 'GPT models with vision — also enables Whisper transcription fallback', placeholder: 'sk-...', helpUrl: 'https://platform.openai.com/api-keys', helpLabel: 'Get API key', vision: true },
  groq_api_key: { label: 'Groq', description: 'Ultra-fast inference — great for real-time overlay suggestions', placeholder: 'gsk_...', helpUrl: 'https://console.groq.com/keys', helpLabel: 'Get free key', freeTier: true },
  deepgram_api_key: { label: 'Deepgram', description: 'Real-time speech transcription for interviews and overlay', placeholder: 'dg-...', helpUrl: 'https://console.deepgram.com', helpLabel: 'Free tier: 200hrs/mo', freeTier: true },
  heygen_api_key: { label: 'HeyGen', description: 'Photorealistic avatar for interviews', placeholder: 'hg-...', helpUrl: 'https://www.heygen.com', helpLabel: 'Enterprise pricing' },
  simli_api_key: { label: 'Simli', description: 'Alternative avatar provider', placeholder: 'sim-...', helpUrl: 'https://simli.com', helpLabel: 'Get API key' },
  judge0_api_key: { label: 'Judge0', description: 'Code execution sandbox', placeholder: 'j0-...', helpUrl: 'https://judge0.com', helpLabel: 'Get API key' },
  serp_api_key: { label: 'SerpAPI', description: 'Web search in overlay', placeholder: 'serp-...', helpUrl: 'https://serpapi.com', helpLabel: 'Get API key' },
  adzuna_app_id: { label: 'Adzuna App ID', description: 'Job board — application ID', placeholder: 'app_id', helpUrl: 'https://developer.adzuna.com', helpLabel: 'Get credentials' },
  adzuna_api_key: { label: 'Adzuna API Key', description: 'Job board — API key', placeholder: 'api_key', helpUrl: 'https://developer.adzuna.com', helpLabel: 'Get credentials' },
  reed_api_key: { label: 'Reed', description: 'UK job board API', placeholder: 'reed-...', helpUrl: 'https://www.reed.co.uk/developers/jobseeker', helpLabel: 'Get API key' },
  scrapfly_key: { label: 'Scrapfly', description: 'Wellfound job scraping', placeholder: 'scp-...', helpUrl: 'https://scrapfly.io', helpLabel: 'Get API key' },
}

/* ── Core credential keys ── */
const LLM_DROPDOWN_KEYS = ['deepseek_api_key', 'anthropic_api_key', 'gemini_api_key', 'openai_api_key', 'groq_api_key']
const NON_DROPDOWN_CORE_KEYS = ['deepgram_api_key']
const CORE_KEYS = [...LLM_DROPDOWN_KEYS, ...NON_DROPDOWN_CORE_KEYS]

/* ── Category definitions ── */
interface Category {
  id: string
  title: string
  subtitle: string
  accentColor: string
  tag: string
  keys: string[]
  icon: React.ReactNode
}

const CATEGORIES: Category[] = [
  {
    id: 'ai',
    title: 'Core Credentials',
    subtitle: 'At least one LLM required — vision-capable providers unlock screen overlay',
    accentColor: '#22d3ee',
    tag: 'REQUIRED',
    keys: CORE_KEYS,
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
      </svg>
    ),
  },
  {
    id: 'avatar',
    title: 'Avatar',
    subtitle: 'Photorealistic interview avatars',
    accentColor: '#6c5ce7',
    tag: 'OPTIONAL',
    keys: ['heygen_api_key', 'simli_api_key'],
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#6c5ce7" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="8" r="4"/>
        <path d="M6 20c0-3.31 2.24-6 6-6s6 2.69 6 6"/>
      </svg>
    ),
  },
  {
    id: 'tools',
    title: 'Overlay Tools',
    subtitle: 'Code execution and web search for live overlay',
    accentColor: '#fbbf24',
    tag: 'OPTIONAL',
    keys: ['judge0_api_key', 'serp_api_key'],
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/>
      </svg>
    ),
  },
  {
    id: 'boards',
    title: 'Job Boards',
    subtitle: 'External job board API access',
    accentColor: '#34d399',
    tag: 'OPTIONAL',
    keys: ['adzuna_app_id', 'adzuna_api_key', 'reed_api_key', 'scrapfly_key'],
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="7" width="20" height="14" rx="2"/>
        <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/>
        <line x1="12" y1="12" x2="12" y2="16"/>
        <line x1="10" y1="14" x2="14" y2="14"/>
      </svg>
    ),
  },
]

/* ── Shared field component (used by non-core categories) ── */
function KeyField({
  label, value, onChange, placeholder, logo, helpUrl, helpLabel, configured, onRemove, removing,
  description, vision, recommended, freeTier,
}: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string
  logo: React.ReactNode; helpUrl: string; helpLabel: string
  configured: boolean; onRemove: () => void; removing: boolean
  description?: string; vision?: boolean; recommended?: boolean; freeTier?: boolean
}) {
  const [focused, setFocused] = useState(false)
  const [revealed, setRevealed] = useState(false)

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: '14px',
      padding: '16px 18px',
      background: configured ? 'rgba(52,211,153,0.03)' : 'rgba(255,255,255,0.015)',
      border: `1px solid ${configured ? 'rgba(52,211,153,0.1)' : 'rgba(255,255,255,0.05)'}`,
      borderRadius: '12px',
      transition: 'all 0.15s',
    }}>
      <div style={{
        width: '36px', height: '36px', borderRadius: '8px',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, marginTop: '2px',
      }}>
        {logo}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '12px', fontFamily: 'monospace', fontWeight: 700, color: 'rgba(226,232,240,0.9)' }}>
            {label}
          </span>
          {configured && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#34d399', boxShadow: '0 0 6px #34d399' }} />
              <span style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, color: '#34d399', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Live
              </span>
            </div>
          )}
          {recommended && (
            <span style={{
              fontSize: '8px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase',
              color: '#fbbf24', background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.2)',
              padding: '1px 6px', borderRadius: '3px',
            }}>Recommended</span>
          )}
          {vision && (
            <span style={{
              fontSize: '8px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase',
              color: '#a78bfa', background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.2)',
              padding: '1px 6px', borderRadius: '3px',
              display: 'flex', alignItems: 'center', gap: '3px',
            }}>
              <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
              Vision
            </span>
          )}
          {freeTier && !configured && (
            <span style={{
              fontSize: '8px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
              color: 'rgba(52,211,153,0.7)', background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.15)',
              padding: '1px 6px', borderRadius: '3px',
            }}>Free</span>
          )}
        </div>
        {description && (
          <p style={{ fontSize: '10px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.5)', marginBottom: '6px', lineHeight: 1.5 }}>
            {description}
          </p>
        )}

        <div style={{ position: 'relative', paddingBottom: '2px' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <input
              type={revealed ? 'text' : 'password'}
              value={value}
              onChange={e => onChange(e.target.value)}
              placeholder={configured ? '••••••••  (saved)' : placeholder}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                borderBottom: `1px solid ${focused ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.08)'}`,
                color: 'rgba(226,232,240,0.9)',
                fontFamily: 'monospace',
                fontSize: '12px',
                padding: '4px 0 8px',
                outline: 'none',
                transition: 'border-color 0.15s',
              }}
            />
            <button
              type="button"
              onClick={() => setRevealed(r => !r)}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px',
                color: 'rgba(100,116,139,0.4)', transition: 'color 0.15s', flexShrink: 0,
              }}
              onMouseEnter={e => (e.currentTarget.style.color = 'rgba(226,232,240,0.7)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.4)')}
              title={revealed ? 'Hide' : 'Reveal'}
            >
              {revealed ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
          </div>
          <div style={{
            position: 'absolute', bottom: 0, left: 0, height: '1px',
            width: focused ? '100%' : '0%',
            background: 'linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2))',
            transition: 'width 0.25s ease',
            boxShadow: '0 0 8px rgba(34,211,238,0.5)',
          }} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px' }}>
          <a
            href={helpUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: '10px', fontFamily: 'monospace', color: 'rgba(34,211,238,0.5)',
              textDecoration: 'none', transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#22d3ee')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(34,211,238,0.5)')}
          >
            {helpLabel} &rarr;
          </a>
          {configured && (
            <button
              onClick={onRemove}
              disabled={removing}
              style={{
                background: 'transparent', border: 'none', cursor: removing ? 'wait' : 'pointer',
                fontSize: '10px', fontFamily: 'monospace', color: 'rgba(248,113,113,0.5)',
                transition: 'color 0.15s', padding: 0,
              }}
              onMouseEnter={e => (e.currentTarget.style.color = '#f87171')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(248,113,113,0.5)')}
            >
              {removing ? 'Removing...' : 'Remove'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Core Credentials section: custom dropdown for LLM + regular fields for others ── */
function CoreCredentialsContent({
  keys, values, onValueChange, onSave, onRemove, saving, removing,
}: {
  keys: ApiKeyInfo[]
  values: Record<string, string>
  onValueChange: (keyName: string, value: string) => void
  onSave: (keyNames: string[]) => void
  onRemove: (keyName: string) => void
  saving: boolean
  removing: string | null
}) {
  const [selectedProvider, setSelectedProvider] = useState('')
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [inputFocused, setInputFocused] = useState(false)
  const [revealed, setRevealed] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const configuredLLMs = keys.filter(k => LLM_DROPDOWN_KEYS.includes(k.key_name) && k.configured)
  const unconfiguredLLMs = LLM_DROPDOWN_KEYS.filter(kn => !configuredLLMs.some(ck => ck.key_name === kn))

  const activeMeta = selectedProvider ? META[selectedProvider] : null

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setDropdownOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div>
      {/* Vision recommendation banner */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: '12px',
        padding: '14px 16px', marginBottom: '16px', borderRadius: '10px',
        background: 'rgba(167,139,250,0.05)', border: '1px solid rgba(167,139,250,0.12)',
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="1.8" strokeLinecap="round" style={{ flexShrink: 0, marginTop: '1px' }}>
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
        </svg>
        <div>
          <p style={{ fontSize: '11px', fontFamily: 'monospace', fontWeight: 700, color: 'rgba(167,139,250,0.85)', marginBottom: '3px' }}>
            For full overlay support, add a vision-capable provider
          </p>
          <p style={{ fontSize: '10px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.5)', lineHeight: 1.6 }}>
            The screen overlay reads your screen to suggest answers in real-time. This requires a provider that supports image input — look for the <span style={{ color: '#a78bfa', fontWeight: 700 }}>Vision</span> badge. Anthropic (Claude), Gemini, and OpenAI all support this.
          </p>
        </div>
      </div>

      {/* ── LLM section label ── */}
      <p style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.45)', marginBottom: '10px' }}>
        LLM Providers
      </p>

      {/* Configured LLM providers */}
      {configuredLLMs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
          {configuredLLMs.map(k => {
            const meta = META[k.key_name]
            if (!meta) return null
            const isEditing = editingKey === k.key_name

            return (
              <div key={k.key_name} style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '14px 16px',
                background: isEditing ? 'rgba(34,211,238,0.03)' : 'rgba(52,211,153,0.03)',
                border: `1px solid ${isEditing ? 'rgba(34,211,238,0.15)' : 'rgba(52,211,153,0.1)'}`,
                borderRadius: '12px', transition: 'all 0.15s',
              }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  {LOGOS[k.key_name]}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '12px', fontFamily: 'monospace', fontWeight: 700, color: 'rgba(226,232,240,0.9)' }}>{meta.label}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#34d399', boxShadow: '0 0 6px #34d399' }} />
                      <span style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, color: '#34d399', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Live</span>
                    </div>
                    {meta.vision && (
                      <span style={{ fontSize: '8px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#a78bfa', background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.2)', padding: '1px 6px', borderRadius: '3px', display: 'flex', alignItems: 'center', gap: '3px' }}>
                        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        Vision
                      </span>
                    )}
                  </div>
                  {isEditing && (
                    <div style={{ marginTop: '8px', position: 'relative', paddingBottom: '2px' }}>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <input type={revealed ? 'text' : 'password'} value={values[k.key_name] || ''} onChange={e => onValueChange(k.key_name, e.target.value)} placeholder={`Enter new ${meta.label} key...`} onFocus={() => setInputFocused(true)} onBlur={() => setInputFocused(false)} autoFocus
                          style={{ flex: 1, background: 'transparent', border: 'none', borderBottom: `1px solid ${inputFocused ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.08)'}`, color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace', fontSize: '12px', padding: '4px 0 8px', outline: 'none', transition: 'border-color 0.15s' }} />
                        <button type="button" onClick={() => setRevealed(r => !r)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px', color: 'rgba(100,116,139,0.4)', transition: 'color 0.15s', flexShrink: 0 }} onMouseEnter={e => (e.currentTarget.style.color = 'rgba(226,232,240,0.7)')} onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.4)')}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                            {revealed ? (<><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></>) : (<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>)}
                          </svg>
                        </button>
                      </div>
                      <div style={{ position: 'absolute', bottom: 0, left: 0, height: '1px', width: inputFocused ? '100%' : '0%', background: 'linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2))', transition: 'width 0.25s ease', boxShadow: '0 0 8px rgba(34,211,238,0.5)' }} />
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                  {isEditing ? (
                    <>
                      <button onClick={() => { if (values[k.key_name]?.trim()) onSave([k.key_name]); setEditingKey(null); setRevealed(false) }} disabled={saving || !values[k.key_name]?.trim()}
                        style={{ background: !values[k.key_name]?.trim() ? 'transparent' : 'rgba(34,211,238,0.1)', border: `1px solid ${!values[k.key_name]?.trim() ? 'rgba(255,255,255,0.06)' : 'rgba(34,211,238,0.35)'}`, color: !values[k.key_name]?.trim() ? 'rgba(255,255,255,0.15)' : '#22d3ee', fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', padding: '5px 12px', borderRadius: '6px', cursor: !values[k.key_name]?.trim() ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}
                      >{saving ? '...' : 'Save'}</button>
                      <button onClick={() => { setEditingKey(null); setRevealed(false); onValueChange(k.key_name, '') }}
                        style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.07)', color: 'rgba(100,116,139,0.6)', fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, padding: '5px 10px', borderRadius: '6px', cursor: 'pointer' }}
                      >Cancel</button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => { setEditingKey(k.key_name); setSelectedProvider(''); setRevealed(false) }}
                        style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.07)', color: 'rgba(100,116,139,0.6)', fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', padding: '5px 12px', borderRadius: '6px', cursor: 'pointer', transition: 'all 0.15s' }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'; e.currentTarget.style.color = 'rgba(226,232,240,0.7)' }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'rgba(100,116,139,0.6)' }}
                      >Edit</button>
                      <button onClick={() => onRemove(k.key_name)} disabled={removing === k.key_name}
                        style={{ background: 'transparent', border: '1px solid rgba(248,113,113,0.12)', color: 'rgba(248,113,113,0.5)', fontFamily: 'monospace', fontSize: '10px', fontWeight: 700, padding: '5px 10px', borderRadius: '6px', cursor: removing === k.key_name ? 'wait' : 'pointer', transition: 'all 0.15s' }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(248,113,113,0.3)'; e.currentTarget.style.color = '#f87171' }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(248,113,113,0.12)'; e.currentTarget.style.color = 'rgba(248,113,113,0.5)' }}
                      >{removing === k.key_name ? '...' : '\u2715'}</button>
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Add LLM provider — custom dropdown with logos + input */}
      {configuredLLMs.length === 0 && unconfiguredLLMs.length > 0 && !editingKey && (
        <div style={{
          padding: '16px 18px',
          background: selectedProvider ? 'rgba(34,211,238,0.03)' : 'rgba(255,255,255,0.015)',
          border: `1px solid ${selectedProvider ? 'rgba(34,211,238,0.15)' : 'rgba(255,255,255,0.06)'}`,
          borderRadius: '12px', transition: 'all 0.15s', marginBottom: '20px',
        }}>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end' }}>
            {/* Custom dropdown trigger */}
            <div ref={dropdownRef} style={{ position: 'relative', width: '220px', flexShrink: 0 }}>
              <label style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)', display: 'block', marginBottom: '6px' }}>
                Provider
              </label>
              <button
                type="button"
                onClick={() => setDropdownOpen(o => !o)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
                  background: '#0c1829',
                  border: `1px solid ${dropdownOpen ? 'rgba(34,211,238,0.4)' : 'rgba(255,255,255,0.1)'}`,
                  borderRadius: '8px', padding: '8px 12px',
                  cursor: 'pointer', transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => { if (!dropdownOpen) e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)' }}
                onMouseLeave={e => { if (!dropdownOpen) e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)' }}
              >
                {selectedProvider ? (
                  <>
                    <div style={{ width: '20px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      {LOGOS[selectedProvider]}
                    </div>
                    <span style={{ flex: 1, fontSize: '12px', fontFamily: 'monospace', fontWeight: 600, color: 'rgba(226,232,240,0.9)', textAlign: 'left' }}>
                      {META[selectedProvider]?.label}
                    </span>
                  </>
                ) : (
                  <span style={{ flex: 1, fontSize: '12px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.5)', textAlign: 'left' }}>
                    Select provider...
                  </span>
                )}
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(100,116,139,0.5)" strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0, transform: dropdownOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.15s' }}>
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </button>

              {/* Dropdown menu with logos */}
              {dropdownOpen && (
                <div style={{
                  position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
                  background: '#0c1829', border: '1px solid rgba(34,211,238,0.15)',
                  borderRadius: '10px', overflow: 'hidden', zIndex: 50,
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                }}>
                  {unconfiguredLLMs.map((keyName, i) => {
                    const meta = META[keyName]
                    if (!meta) return null
                    return (
                      <button key={keyName}
                        onClick={() => { setSelectedProvider(keyName); setDropdownOpen(false); setRevealed(false) }}
                        style={{
                          width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
                          padding: '10px 12px', background: 'transparent', border: 'none',
                          borderTop: i > 0 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                          cursor: 'pointer', transition: 'background 0.1s', textAlign: 'left',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.05)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                      >
                        <div style={{ width: '24px', height: '24px', borderRadius: '5px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          {LOGOS[keyName]}
                        </div>
                        <span style={{ flex: 1, fontSize: '12px', fontFamily: 'monospace', fontWeight: 600, color: 'rgba(226,232,240,0.85)' }}>
                          {meta.label}
                        </span>
                        <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                          {meta.vision && (
                            <span style={{ fontSize: '7px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#a78bfa', background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.2)', padding: '1px 5px', borderRadius: '3px', display: 'flex', alignItems: 'center', gap: '2px' }}>
                              <svg width="7" height="7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                              Vision
                            </span>
                          )}
                          {meta.recommended && (
                            <span style={{ fontSize: '7px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#fbbf24', background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.2)', padding: '1px 5px', borderRadius: '3px' }}>
                              Recommended
                            </span>
                          )}
                          {meta.freeTier && (
                            <span style={{ fontSize: '7px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'rgba(52,211,153,0.7)', background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.15)', padding: '1px 5px', borderRadius: '3px' }}>
                              Free
                            </span>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Key input */}
            <div style={{ flex: 1, position: 'relative', paddingBottom: '2px' }}>
              <label style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.5)', display: 'block', marginBottom: '6px' }}>
                API Key
              </label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type={revealed ? 'text' : 'password'}
                  value={selectedProvider ? (values[selectedProvider] || '') : ''}
                  onChange={e => selectedProvider && onValueChange(selectedProvider, e.target.value)}
                  placeholder={activeMeta?.placeholder || 'Select a provider first...'}
                  disabled={!selectedProvider}
                  onFocus={() => setInputFocused(true)}
                  onBlur={() => setInputFocused(false)}
                  style={{
                    flex: 1, background: 'transparent', border: 'none',
                    borderBottom: `1px solid ${inputFocused && selectedProvider ? 'rgba(34,211,238,0.5)' : 'rgba(255,255,255,0.08)'}`,
                    color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace', fontSize: '12px',
                    padding: '4px 0 8px', outline: 'none', transition: 'border-color 0.15s',
                    opacity: selectedProvider ? 1 : 0.4,
                  }}
                />
                <button type="button" onClick={() => setRevealed(r => !r)}
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px', color: 'rgba(100,116,139,0.4)', transition: 'color 0.15s', flexShrink: 0 }}
                  onMouseEnter={e => (e.currentTarget.style.color = 'rgba(226,232,240,0.7)')}
                  onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.4)')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                    {revealed ? (<><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></>) : (<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>)}
                  </svg>
                </button>
              </div>
              <div style={{ position: 'absolute', bottom: 0, left: 0, height: '1px', width: inputFocused && selectedProvider ? '100%' : '0%', background: 'linear-gradient(90deg, #22d3ee, rgba(34,211,238,0.2))', transition: 'width 0.25s ease', boxShadow: '0 0 8px rgba(34,211,238,0.5)' }} />
            </div>

            {/* Save button */}
            <button
              onClick={() => {
                if (selectedProvider && values[selectedProvider]?.trim()) {
                  onSave([selectedProvider]); setSelectedProvider(''); setRevealed(false)
                }
              }}
              disabled={saving || !selectedProvider || !values[selectedProvider]?.trim()}
              style={{
                background: (!selectedProvider || !values[selectedProvider]?.trim()) ? 'transparent' : 'rgba(34,211,238,0.1)',
                border: `1px solid ${(!selectedProvider || !values[selectedProvider]?.trim()) ? 'rgba(255,255,255,0.06)' : 'rgba(34,211,238,0.35)'}`,
                color: (!selectedProvider || !values[selectedProvider]?.trim()) ? 'rgba(255,255,255,0.15)' : '#22d3ee',
                fontFamily: 'monospace', fontSize: '10px', fontWeight: 700,
                letterSpacing: '0.15em', textTransform: 'uppercase',
                padding: '9px 18px', borderRadius: '8px', flexShrink: 0,
                cursor: (!selectedProvider || !values[selectedProvider]?.trim()) ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s', marginBottom: '2px',
              }}
            >{saving ? '...' : 'Save'}</button>
          </div>

          {/* Description + help link */}
          {activeMeta && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '10px' }}>
              <p style={{ fontSize: '10px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.45)', lineHeight: 1.4 }}>{activeMeta.description}</p>
              <a href={activeMeta.helpUrl} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: '10px', fontFamily: 'monospace', color: 'rgba(34,211,238,0.5)', textDecoration: 'none', transition: 'color 0.15s', flexShrink: 0, marginLeft: '16px' }}
                onMouseEnter={e => (e.currentTarget.style.color = '#22d3ee')} onMouseLeave={e => (e.currentTarget.style.color = 'rgba(34,211,238,0.5)')}
              >{activeMeta.helpLabel} &rarr;</a>
            </div>
          )}
        </div>
      )}

      {/* ── Non-dropdown keys (Deepgram etc.) as regular fields ── */}
      {NON_DROPDOWN_CORE_KEYS.length > 0 && (
        <>
          <p style={{ fontSize: '9px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(100,116,139,0.45)', marginBottom: '10px' }}>
            Other Services
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {NON_DROPDOWN_CORE_KEYS.map(keyName => {
              const info = keys.find(k => k.key_name === keyName)
              const meta = META[keyName]
              if (!meta) return null
              return (
                <KeyField
                  key={keyName}
                  label={meta.label}
                  value={values[keyName] || ''}
                  onChange={v => onValueChange(keyName, v)}
                  placeholder={meta.placeholder}
                  logo={LOGOS[keyName]}
                  helpUrl={meta.helpUrl}
                  helpLabel={meta.helpLabel}
                  configured={info?.configured ?? false}
                  onRemove={() => onRemove(keyName)}
                  removing={removing === keyName}
                  description={meta.description}
                  vision={meta.vision}
                  recommended={meta.recommended}
                  freeTier={meta.freeTier}
                />
              )
            })}
          </div>
          <div className="flex justify-end" style={{ marginTop: '16px' }}>
            <button
              onClick={() => {
                const toSave = NON_DROPDOWN_CORE_KEYS.filter(k => values[k]?.trim())
                if (toSave.length) onSave(toSave)
              }}
              disabled={saving || NON_DROPDOWN_CORE_KEYS.every(k => !values[k])}
              style={{
                background: saving || NON_DROPDOWN_CORE_KEYS.every(k => !values[k]) ? 'transparent' : 'rgba(34,211,238,0.1)',
                border: `1px solid ${saving || NON_DROPDOWN_CORE_KEYS.every(k => !values[k]) ? 'rgba(255,255,255,0.06)' : 'rgba(34,211,238,0.35)'}`,
                color: saving || NON_DROPDOWN_CORE_KEYS.every(k => !values[k]) ? 'rgba(255,255,255,0.15)' : '#22d3ee',
                fontFamily: 'monospace', fontSize: '10px', fontWeight: 700,
                letterSpacing: '0.15em', textTransform: 'uppercase',
                padding: '9px 22px', borderRadius: '8px',
                cursor: saving || NON_DROPDOWN_CORE_KEYS.every(k => !values[k]) ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s',
              }}
            >{saving ? 'Saving...' : 'Save Keys'}</button>
          </div>
        </>
      )}
    </div>
  )
}

/* ── Category card (collapsible) — used for non-core categories ── */
function CategoryCard({
  category, keys, values, onValueChange, onSave, onRemove, saving, removing,
}: {
  category: Category
  keys: ApiKeyInfo[]
  values: Record<string, string>
  onValueChange: (keyName: string, value: string) => void
  onSave: () => void
  onRemove: (keyName: string) => void
  saving: boolean
  removing: string | null
}) {
  const [open, setOpen] = useState(false)
  const configuredCount = keys.filter(k => k.configured).length
  const allConfigured = configuredCount === keys.length

  return (
    <div style={{
      position: 'relative',
      background: 'rgba(255,255,255,0.025)',
      backdropFilter: 'blur(12px)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '16px',
      overflow: 'hidden',
      transition: 'border-color 0.2s',
      ...(open ? { borderColor: `${category.accentColor}30` } : {}),
    }}>
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: '3px',
        background: open ? category.accentColor : 'transparent',
        boxShadow: open ? `0 0 12px ${category.accentColor}80` : 'none',
        transition: 'all 0.2s',
      }} />

      <div className="flex items-center gap-5" style={{ padding: '20px 24px 20px 28px' }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '12px',
          background: `${category.accentColor}12`,
          border: `1px solid ${category.accentColor}25`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {category.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="flex items-center gap-2">
            <p style={{ fontSize: '14px', fontFamily: 'monospace', fontWeight: 700, color: 'rgba(226,232,240,0.95)', letterSpacing: '0.02em' }}>
              {category.title}
            </p>
            <span style={{
              fontSize: '9px', fontFamily: 'monospace', fontWeight: 700,
              color: `${category.accentColor}80`,
              background: `${category.accentColor}10`,
              border: `1px solid ${category.accentColor}20`,
              padding: '2px 7px', borderRadius: '4px',
              letterSpacing: '0.14em', textTransform: 'uppercase',
            }}>
              {category.tag}
            </span>
          </div>
          <p style={{ fontSize: '11px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.6)', marginTop: '2px' }}>
            {category.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-3" style={{ flexShrink: 0 }}>
          <span style={{
            fontSize: '11px', fontFamily: 'monospace',
            color: allConfigured ? '#34d399' : configuredCount > 0 ? 'rgba(226,232,240,0.5)' : 'rgba(100,116,139,0.35)',
          }}>
            {configuredCount}/{keys.length}
          </span>

          <button
            onClick={() => setOpen(o => !o)}
            style={{
              background: 'transparent',
              border: `1px solid ${open ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.07)'}`,
              color: open ? 'rgba(226,232,240,0.7)' : 'rgba(100,116,139,0.6)',
              fontFamily: 'monospace', fontSize: '10px', fontWeight: 700,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              padding: '6px 14px', borderRadius: '8px',
              cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = 'rgba(226,232,240,0.9)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = open ? 'rgba(226,232,240,0.7)' : 'rgba(100,116,139,0.6)' }}
          >
            {open ? '\u2715 Close' : allConfigured ? 'Update' : 'Set up \u2192'}
          </button>
        </div>
      </div>

      {open && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', padding: '24px 28px 28px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {category.keys.map(keyName => {
              const info = keys.find(k => k.key_name === keyName)
              const meta = META[keyName]
              if (!meta) return null
              return (
                <KeyField
                  key={keyName}
                  label={meta.label}
                  value={values[keyName] || ''}
                  onChange={v => onValueChange(keyName, v)}
                  placeholder={meta.placeholder}
                  logo={LOGOS[keyName]}
                  helpUrl={meta.helpUrl}
                  helpLabel={meta.helpLabel}
                  configured={info?.configured ?? false}
                  onRemove={() => onRemove(keyName)}
                  removing={removing === keyName}
                  description={meta.description}
                  vision={meta.vision}
                  recommended={meta.recommended}
                  freeTier={meta.freeTier}
                />
              )
            })}
          </div>

          <div className="flex justify-end" style={{ marginTop: '24px' }}>
            <button
              onClick={onSave}
              disabled={saving || category.keys.every(k => !values[k])}
              style={{
                background: saving || category.keys.every(k => !values[k]) ? 'transparent' : 'rgba(34,211,238,0.1)',
                border: `1px solid ${saving || category.keys.every(k => !values[k]) ? 'rgba(255,255,255,0.06)' : 'rgba(34,211,238,0.35)'}`,
                color: saving || category.keys.every(k => !values[k]) ? 'rgba(255,255,255,0.15)' : '#22d3ee',
                fontFamily: 'monospace', fontSize: '10px', fontWeight: 700,
                letterSpacing: '0.15em', textTransform: 'uppercase',
                padding: '9px 22px', borderRadius: '8px',
                cursor: saving || category.keys.every(k => !values[k]) ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { if (!saving && !category.keys.every(k => !values[k])) { e.currentTarget.style.background = 'rgba(34,211,238,0.18)'; e.currentTarget.style.boxShadow = '0 0 16px rgba(34,211,238,0.15)' } }}
              onMouseLeave={e => { e.currentTarget.style.background = saving || category.keys.every(k => !values[k]) ? 'transparent' : 'rgba(34,211,238,0.1)'; e.currentTarget.style.boxShadow = 'none' }}
            >
              {saving ? 'Saving...' : 'Save Keys'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Core Credentials card wrapper ── */
function CoreCredentialsCard({
  category, keys, values, onValueChange, onSave, onRemove, saving, removing,
}: {
  category: Category
  keys: ApiKeyInfo[]
  values: Record<string, string>
  onValueChange: (keyName: string, value: string) => void
  onSave: (keyNames: string[]) => void
  onRemove: (keyName: string) => void
  saving: boolean
  removing: string | null
}) {
  const [open, setOpen] = useState(false)
  const configuredCount = keys.filter(k => k.configured).length

  return (
    <div style={{
      position: 'relative',
      background: 'rgba(255,255,255,0.025)',
      backdropFilter: 'blur(12px)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '16px',
      overflow: 'hidden',
      transition: 'border-color 0.2s',
      ...(open ? { borderColor: `${category.accentColor}30` } : {}),
    }}>
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: '3px',
        background: open ? category.accentColor : 'transparent',
        boxShadow: open ? `0 0 12px ${category.accentColor}80` : 'none',
        transition: 'all 0.2s',
      }} />

      <div className="flex items-center gap-5" style={{ padding: '20px 24px 20px 28px' }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '12px',
          background: `${category.accentColor}12`,
          border: `1px solid ${category.accentColor}25`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {category.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="flex items-center gap-2">
            <p style={{ fontSize: '14px', fontFamily: 'monospace', fontWeight: 700, color: 'rgba(226,232,240,0.95)', letterSpacing: '0.02em' }}>
              {category.title}
            </p>
            <span style={{
              fontSize: '9px', fontFamily: 'monospace', fontWeight: 700,
              color: 'rgba(248,113,113,0.8)',
              background: 'rgba(248,113,113,0.1)',
              border: '1px solid rgba(248,113,113,0.2)',
              padding: '2px 7px', borderRadius: '4px',
              letterSpacing: '0.14em', textTransform: 'uppercase',
            }}>
              {category.tag}
            </span>
          </div>
          <p style={{ fontSize: '11px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.6)', marginTop: '2px' }}>
            {category.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-3" style={{ flexShrink: 0 }}>
          <span style={{
            fontSize: '11px', fontFamily: 'monospace',
            color: configuredCount > 0 ? 'rgba(226,232,240,0.5)' : 'rgba(100,116,139,0.35)',
          }}>
            {configuredCount} active
          </span>

          <button
            onClick={() => setOpen(o => !o)}
            style={{
              background: 'transparent',
              border: `1px solid ${open ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.07)'}`,
              color: open ? 'rgba(226,232,240,0.7)' : 'rgba(100,116,139,0.6)',
              fontFamily: 'monospace', fontSize: '10px', fontWeight: 700,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              padding: '6px 14px', borderRadius: '8px',
              cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = 'rgba(226,232,240,0.9)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = open ? 'rgba(226,232,240,0.7)' : 'rgba(100,116,139,0.6)' }}
          >
            {open ? '\u2715 Close' : configuredCount > 0 ? 'Manage' : 'Set up \u2192'}
          </button>
        </div>
      </div>

      {open && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', padding: '24px 28px 28px' }}>
          <CoreCredentialsContent
            keys={keys}
            values={values}
            onValueChange={onValueChange}
            onSave={onSave}
            onRemove={onRemove}
            saving={saving}
            removing={removing}
          />
        </div>
      )}
    </div>
  )
}

/* ── Main panel ── */
export default function ApiKeysPanel() {
  const { getStatus, setKey, deleteKey } = useApiKeys()
  const [keys, setKeys] = useState<ApiKeyInfo[]>([])
  const [values, setValues] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    getStatus().then(setKeys).catch(() => {})
  }, [])

  const handleValueChange = (keyName: string, value: string) => {
    setValues(v => ({ ...v, [keyName]: value }))
  }

  const handleSaveKeys = async (keyNames: string[]) => {
    setSaving(true); setError(''); setSuccess('')
    try {
      const toSave = keyNames.filter(k => values[k]?.trim())
      for (const keyName of toSave) {
        await setKey(keyName, values[keyName].trim())
      }
      const updated = await getStatus()
      setKeys(updated)
      setValues(v => {
        const next = { ...v }
        for (const k of toSave) delete next[k]
        return next
      })
      setSuccess(`${toSave.length} key${toSave.length > 1 ? 's' : ''} saved successfully.`)
      setTimeout(() => setSuccess(''), 3000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveCategory = async (category: Category) => {
    const toSave = category.keys.filter(k => values[k]?.trim())
    await handleSaveKeys(toSave)
  }

  const handleRemove = async (keyName: string) => {
    setRemoving(keyName); setError(''); setSuccess('')
    try {
      await deleteKey(keyName)
      const updated = await getStatus()
      setKeys(updated)
      setSuccess(`${META[keyName]?.label ?? keyName} removed.`)
      setTimeout(() => setSuccess(''), 3000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to remove')
    } finally {
      setRemoving(null)
    }
  }

  const LLM_KEY_NAMES = ['deepseek_api_key', 'anthropic_api_key', 'gemini_api_key', 'openai_api_key', 'groq_api_key']
  const VISION_KEY_NAMES = ['anthropic_api_key', 'gemini_api_key', 'openai_api_key']
  const hasAnyLLM = keys.some(k => LLM_KEY_NAMES.includes(k.key_name) && k.configured)
  const hasVision = keys.some(k => VISION_KEY_NAMES.includes(k.key_name) && k.configured)
  const totalConfigured = keys.filter(k => k.configured).length

  const coreCategory = CATEGORIES.find(c => c.id === 'ai')!
  const otherCategories = CATEGORIES.filter(c => c.id !== 'ai')

  return (
    <div style={{ position: 'relative', padding: '40px 48px' }}>

      {/* Background shapes */}
      <div style={{
        position: 'fixed', top: '-120px', right: '-80px',
        width: '420px', height: '420px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(34,211,238,0.07) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />
      <div style={{
        position: 'fixed', bottom: '60px', left: '80px',
        width: '300px', height: '300px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(56,189,248,0.05) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />
      <div style={{
        position: 'fixed', inset: 0,
        backgroundImage: 'linear-gradient(rgba(34,211,238,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.03) 1px, transparent 1px)',
        backgroundSize: '48px 48px',
        pointerEvents: 'none', zIndex: 0,
      }} />

      {/* Content */}
      <div style={{ position: 'relative', zIndex: 1, maxWidth: '640px' }}>

        {/* Header */}
        <div style={{ marginBottom: '40px' }}>
          <div className="flex items-end justify-between">
            <div>
              <div className="flex items-center gap-3" style={{ marginBottom: '8px' }}>
                <div style={{ width: '28px', height: '1px', background: '#22d3ee', boxShadow: '0 0 8px rgba(34,211,238,0.6)' }} />
                <span style={{ fontSize: '10px', fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.25em', textTransform: 'uppercase', color: '#22d3ee' }}>
                  Settings
                </span>
              </div>
              <h1 style={{
                fontSize: '28px', fontFamily: '"Courier New", monospace',
                fontWeight: 700, color: 'rgba(226,232,240,0.95)',
                letterSpacing: '-0.01em', lineHeight: 1,
              }}>
                API Keys
              </h1>
              <p style={{ fontSize: '12px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.55)', marginTop: '8px' }}>
                Configure your provider API keys — encrypted and stored locally.
              </p>
            </div>
            {/* Status counter */}
            <div style={{ textAlign: 'right', paddingBottom: '2px' }}>
              <span style={{
                fontSize: '36px', fontFamily: 'monospace', fontWeight: 700, lineHeight: 1,
                color: hasAnyLLM ? '#22d3ee' : 'rgba(248,113,113,0.6)',
              }}>
                {totalConfigured}
              </span>
              <span style={{ fontSize: '11px', fontFamily: 'monospace', color: 'rgba(100,116,139,0.4)', display: 'block', marginTop: '2px' }}>
                {totalConfigured === 1 ? 'key' : 'keys'} configured
              </span>
              {hasAnyLLM && (
                <span style={{
                  fontSize: '10px', fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: '4px',
                  justifyContent: 'flex-end', marginTop: '3px',
                  color: hasVision ? '#a78bfa' : 'rgba(251,191,36,0.6)',
                }}>
                  {hasVision ? (
                    <>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                      </svg>
                      Vision ready
                    </>
                  ) : 'No vision provider'}
                </span>
              )}
            </div>
          </div>

          <div style={{ height: '1px', background: 'linear-gradient(90deg, rgba(34,211,238,0.2), transparent)', marginTop: '20px' }} />
        </div>

        {/* Notifications */}
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.15)', borderRadius: '10px', padding: '12px 16px', marginBottom: '20px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <p style={{ fontSize: '11px', fontFamily: 'monospace', color: '#f87171' }}>{error}</p>
          </div>
        )}
        {success && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(52,211,153,0.06)', border: '1px solid rgba(52,211,153,0.15)', borderRadius: '10px', padding: '12px 16px', marginBottom: '20px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            <p style={{ fontSize: '11px', fontFamily: 'monospace', color: '#34d399' }}>{success}</p>
          </div>
        )}

        {/* Cards */}
        <div className="flex flex-col" style={{ gap: '12px' }}>
          {/* Core Credentials — dropdown-based */}
          <CoreCredentialsCard
            category={coreCategory}
            keys={keys.filter(k => coreCategory.keys.includes(k.key_name))}
            values={values}
            onValueChange={handleValueChange}
            onSave={handleSaveKeys}
            onRemove={handleRemove}
            saving={saving}
            removing={removing}
          />

          {/* Other categories — standard field-based */}
          {otherCategories.map(cat => (
            <CategoryCard
              key={cat.id}
              category={cat}
              keys={keys.filter(k => cat.keys.includes(k.key_name))}
              values={values}
              onValueChange={handleValueChange}
              onSave={() => handleSaveCategory(cat)}
              onRemove={handleRemove}
              saving={saving}
              removing={removing}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
