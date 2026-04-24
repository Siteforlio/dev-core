import { useEffect, useRef, useState } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'
import type { ApplicationDetail, ChatMessage } from '../../types/jobHunter'

interface Props {
  campaignId: string
  applicationId: string
  onClose: () => void
}

const QUICK_PROMPTS = [
  'Write cover letter',
  'What should I emphasise?',
  'Answer custom form questions',
  'Summarise this job',
]

/** Renders **bold** markdown as <strong> nodes without dangerouslySetInnerHTML */
function BoldText({ text }: { text: string }) {
  const parts = text.split(/\*\*(.*?)\*\*/g)
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? <strong key={i} className="text-[#e0e0e0]">{part}</strong> : <span key={i}>{part}</span>
      )}
    </>
  )
}

export default function ApplyPanel({ campaignId, applicationId, onClose }: Props) {
  const { getApplicationDetail, generateCoverLetter, chatWithApplication, openInChrome, patchApplicationStatus } = useJobHunter()

  const [detail, setDetail] = useState<ApplicationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  const [coverLoading, setCoverLoading] = useState(false)
  const [coverLetter, setCoverLetter] = useState<string | null>(null)
  const [showCover, setShowCover] = useState(false)

  const [chromeLoading, setChromeLoading] = useState(false)
  const [markingApplied, setMarkingApplied] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLoading(true)
    setError('')
    setMessages([])
    getApplicationDetail(campaignId, applicationId)
      .then((d) => {
        setDetail(d)
        setCoverLetter(d.coverLetter)
        setMessages([{
          role: 'assistant',
          content: `Context loaded for **${d.title}** at **${d.company}**. Your tailored resume is ready${d.resumeFilename ? ` — ${d.resumeFilename}` : ''}. Ask me anything about this application, or use the quick actions below.`,
        }])
      })
      .catch(() => setError('Failed to load application details.'))
      .finally(() => setLoading(false))
  }, [applicationId])

  useEffect(() => {
    if (messagesEndRef.current?.scrollIntoView) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!text.trim() || chatLoading) return
    const userMsg: ChatMessage = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setChatLoading(true)
    try {
      const reply = await chatWithApplication(campaignId, applicationId, text, messages)
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }])
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Sorry, something went wrong.' }])
    } finally {
      setChatLoading(false)
    }
  }

  const handleGenerateCoverLetter = async () => {
    setCoverLoading(true)
    try {
      const cl = await generateCoverLetter(campaignId, applicationId)
      setCoverLetter(cl)
      setShowCover(true)
    } catch {
      // user can retry
    } finally {
      setCoverLoading(false)
    }
  }

  const handleOpenInChrome = async () => {
    setChromeLoading(true)
    try {
      await openInChrome(campaignId, applicationId)
    } finally {
      setChromeLoading(false)
    }
  }

  const handleMarkApplied = async () => {
    setMarkingApplied(true)
    try {
      await patchApplicationStatus(campaignId, applicationId, 'applied')
      setDetail((d) => d ? { ...d, status: 'applied' } : d)
    } catch {
      // silent — user can retry
    } finally {
      setMarkingApplied(false)
    }
  }

  const handleOpenFolder = () => {
    if (!detail?.resumeFolder) return
    if (window.electronAPI?.openPath) {
      window.electronAPI.openPath(detail.resumeFolder)
    } else {
      alert(`Resume folder:\n${detail.resumeFolder}`)
    }
  }

  const handleExportCoverLetter = () => {
    if (!coverLetter) return
    const blob = new Blob([coverLetter], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${detail?.company ?? 'cover'}-letter.txt`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-[#0a0a0a] items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="flex flex-col h-full bg-[#0a0a0a] items-center justify-center gap-3">
        <p className="text-red-400 text-sm">{error || 'Not found'}</p>
        <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">Close</button>
      </div>
    )
  }

  return (
    <div className="relative flex flex-col h-full bg-[#0a0a0a] overflow-hidden">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#141414] flex-shrink-0">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] text-[#444] mb-0.5">{detail.company} · {detail.location || 'Remote'}</p>
          <p className="text-base font-semibold text-[#efefef] truncate">{detail.title}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-4">
          {detail.applyUrl && (
            <a
              href={detail.applyUrl}
              target="_blank"
              rel="noreferrer"
              className="text-[12px] px-3 py-1.5 rounded-md border border-[#1c1c1c] text-[#444] hover:text-[#888] hover:border-[#2a2a2a] transition-all whitespace-nowrap"
            >
              View posting ↗
            </a>
          )}
          <button
            onClick={handleOpenInChrome}
            disabled={chromeLoading}
            className="text-[12px] px-3 py-1.5 rounded-md bg-[#111] border border-[#222] text-[#d0d0d0] hover:bg-[#161616] hover:border-[#2e2e2e] transition-all whitespace-nowrap disabled:opacity-50"
          >
            {chromeLoading ? 'Opening…' : 'Open in Chrome →'}
          </button>
          {detail.status !== 'applied' && detail.status !== 'interview' && detail.status !== 'offer' && detail.status !== 'responded' ? (
            <button
              onClick={handleMarkApplied}
              disabled={markingApplied}
              className="text-[12px] px-3 py-1.5 rounded-md bg-[#0f2a1a] border border-[#1a3d24] text-[#34d399] hover:bg-[#132e1e] hover:border-[#1f4a2a] transition-all whitespace-nowrap disabled:opacity-50 font-medium"
            >
              {markingApplied ? '…' : '✓ Applied'}
            </button>
          ) : (
            <span className="text-[12px] px-3 py-1.5 rounded-md bg-[#0a1a11] border border-[#122018] text-[#1e7a4a] font-medium whitespace-nowrap select-none">
              ✓ Applied
            </span>
          )}
          <button onClick={onClose} className="text-[12px] px-2 py-1.5 text-[#444] hover:text-[#888] transition-colors">✕</button>
        </div>
      </div>

      {/* Resume strip */}
      <div className="flex items-center gap-4 px-6 py-3 border-b border-[#141414] flex-shrink-0">
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-[#383838] uppercase tracking-widest mb-1">Resume</p>
          {detail.resumeFilename ? (
            <>
              <p className="text-[12px] text-[#999] font-medium truncate">{detail.resumeFilename}</p>
              {detail.resumeFolder && (
                <p className="text-[10px] text-[#333] font-mono mt-0.5 truncate">{detail.resumeFolder}</p>
              )}
            </>
          ) : (
            <p className="text-[12px] text-[#444] italic">No resume yet — trigger tailoring first.</p>
          )}
        </div>
        <div className="flex gap-1.5 flex-shrink-0">
          {detail.resumeFolder && (
            <button
              onClick={handleOpenFolder}
              className="text-[11px] px-2.5 py-1 rounded-md border border-[#1c1c1c] text-[#555] hover:text-[#888] hover:border-[#2a2a2a] transition-all"
            >
              Open folder
            </button>
          )}
          <button
            onClick={coverLetter ? () => setShowCover(true) : handleGenerateCoverLetter}
            disabled={coverLoading}
            className="text-[11px] px-2.5 py-1 rounded-md border border-[#1e1b33] text-[#7c6edb] hover:bg-[#13102a] hover:border-[#2a2550] hover:text-[#a89ef5] transition-all disabled:opacity-50"
          >
            {coverLoading ? '…' : coverLetter ? '✦ Cover letter' : '✦ Generate cover letter'}
          </button>
        </div>
      </div>

      {/* Cover letter overlay */}
      {showCover && coverLetter && (
        <div className="absolute inset-0 z-50 bg-black/80 flex items-center justify-center p-6">
          <div className="bg-[#0f0f0f] border border-[#222] rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#1c1c1c]">
              <p className="text-sm font-semibold text-[#ddd]">Cover Letter — {detail.company}</p>
              <div className="flex gap-2">
                <button
                  onClick={handleExportCoverLetter}
                  className="text-[11px] px-2.5 py-1 rounded border border-[#1c1c1c] text-[#555] hover:text-[#888] transition-colors"
                >
                  Export .txt
                </button>
                <button onClick={() => setShowCover(false)} className="text-[11px] text-[#444] hover:text-[#888] transition-colors">✕</button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <p className="text-sm text-[#b0b0b0] leading-relaxed whitespace-pre-wrap">{coverLetter}</p>
            </div>
          </div>
        </div>
      )}

      {/* Chat */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center gap-2 px-6 py-2 border-b border-[#111] text-[11px] text-[#333] flex-shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-[#34d399] flex-shrink-0" />
          Context loaded — {detail.company} · {detail.title} · tailored resume + job description
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] flex-shrink-0 mt-0.5 border ${
                msg.role === 'assistant'
                  ? 'bg-[#0d0b1a] border-[#1e1b33] text-[#7c6edb]'
                  : 'bg-[#111] border-[#1c1c1c] text-[#555]'
              }`}>
                {msg.role === 'assistant' ? '✦' : 'S'}
              </div>
              <div className={`px-3.5 py-2.5 rounded-lg text-[13px] leading-[1.55] max-w-[82%] ${
                msg.role === 'assistant'
                  ? 'bg-[#0f0f0f] border border-[#171717] text-[#b0b0b0] rounded-tl-sm'
                  : 'bg-[#111] border border-[#1c1c1c] text-[#d5d5d5] rounded-tr-sm'
              }`}>
                <BoldText text={msg.content} />
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="flex gap-2.5">
              <div className="w-6 h-6 rounded-md flex items-center justify-center text-[10px] flex-shrink-0 mt-0.5 border bg-[#0d0b1a] border-[#1e1b33] text-[#7c6edb]">✦</div>
              <div className="px-3.5 py-2.5 rounded-lg rounded-tl-sm bg-[#0f0f0f] border border-[#171717] text-[#555] text-[13px]">
                <span className="animate-pulse">···</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="px-6 pb-2 flex gap-1.5 flex-wrap flex-shrink-0">
          {QUICK_PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => sendMessage(p)}
              disabled={chatLoading}
              className="text-[11px] px-3 py-1 rounded-full border border-[#161616] text-[#3a3a3a] hover:border-[#222] hover:text-[#666] transition-all disabled:opacity-30"
            >
              {p}
            </button>
          ))}
        </div>

        <div className="px-6 pb-5 flex gap-2 items-end flex-shrink-0">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage(input)
              }
            }}
            rows={1}
            placeholder="Ask anything about this application…"
            className="flex-1 bg-[#0f0f0f] border border-[#181818] rounded-lg px-3.5 py-2.5 text-[13px] text-[#d5d5d5] placeholder-[#2a2a2a] resize-none outline-none focus:border-[#222] leading-[1.4] font-[inherit]"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={chatLoading || !input.trim()}
            className="w-9 h-9 rounded-lg bg-[#111] border border-[#1e1e1e] text-[#555] hover:border-[#2a2a2a] hover:text-[#aaa] flex items-center justify-center text-[13px] flex-shrink-0 transition-all disabled:opacity-30"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  )
}

declare global {
  interface Window {
    electronAPI?: { openPath: (path: string) => void }
  }
}
