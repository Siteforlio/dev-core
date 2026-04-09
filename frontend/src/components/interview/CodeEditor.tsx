import Editor from '@monaco-editor/react'
import { useState } from 'react'

const STARTER: Record<string, string> = {
  python: '# Write your solution here\ndef solution():\n    pass\n',
  javascript: '// Write your solution here\nfunction solution() {\n\n}\n',
  typescript: '// Write your solution here\nfunction solution(): void {\n\n}\n',
  java: '// Write your solution here\nclass Solution {\n    public void solution() {\n\n    }\n}\n',
}

interface Props {
  question: string
  company: string
  sessionId: string
  onReaction: (comment: string) => void
}

export default function CodeEditor({ question, company, sessionId, onReaction }: Props) {
  const [language, setLanguage] = useState('python')
  const [code, setCode] = useState(STARTER['python'])
  const [loading, setLoading] = useState(false)

  const handleLanguageChange = (lang: string) => {
    setLanguage(lang)
    setCode(STARTER[lang] ?? '')
  }

  const requestReaction = async () => {
    if (!code.trim() || loading) return
    setLoading(true)
    try {
      const res = await fetch(`/api/v1/ws/code-react`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code_snapshot: code, question, company, session_id: sessionId }),
      })
      if (res.ok) {
        const json = await res.json()
        onReaction(json.data?.comment ?? '')
      }
    } catch {
      // silently fail — reaction is optional
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-gray-900 border-b border-gray-800 shrink-0">
        <span className="text-xs text-gray-500 uppercase tracking-wider">Language</span>
        {(['python', 'javascript', 'typescript', 'java'] as const).map((lang) => (
          <button
            key={lang}
            onClick={() => handleLanguageChange(lang)}
            className={`text-xs px-3 py-1 rounded-md transition-colors ${
              language === lang
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
            }`}
          >
            {lang}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={requestReaction}
          disabled={loading}
          className="text-xs bg-gray-700 hover:bg-gray-600 disabled:opacity-40 px-3 py-1.5 rounded-md transition-colors"
        >
          {loading ? 'Analyzing…' : 'Ask AI'}
        </button>
      </div>

      {/* Monaco */}
      <div className="flex-1 min-h-0">
        <Editor
          height="100%"
          language={language}
          value={code}
          onChange={(val) => setCode(val ?? '')}
          theme="vs-dark"
          options={{
            fontSize: 13,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            padding: { top: 12 },
            lineNumbers: 'on',
            renderLineHighlight: 'all',
            automaticLayout: true,
          }}
        />
      </div>
    </div>
  )
}
