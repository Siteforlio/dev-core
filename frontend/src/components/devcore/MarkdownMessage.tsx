import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handle = () => {
    navigator.clipboard.writeText(text).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={handle}
      className={[
        'flex items-center gap-1 px-2 py-0.5 rounded border font-mono text-[10px] tracking-wide transition-all',
        copied
          ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-400'
          : 'border-white/[0.08] bg-white/[0.04] text-white/30 hover:text-white/60 hover:bg-white/[0.07]',
      ].join(' ')}
    >
      {copied ? (
        <>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          copied
        </>
      ) : (
        <>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          copy
        </>
      )}
    </button>
  )
}

const codeTheme = {
  ...oneDark,
  'pre[class*="language-"]': {
    ...oneDark['pre[class*="language-"]'],
    background: 'rgba(9,9,18,0.97)',
    margin: 0,
    padding: '12px 16px',
    fontSize: '12px',
    lineHeight: '1.7',
    borderRadius: 0,
  },
  'code[class*="language-"]': {
    ...oneDark['code[class*="language-"]'],
    background: 'transparent',
    fontSize: '12px',
  },
}

type ReadingMode = 'normal' | 'narrow' | 'large' | 'teleprompter'

// Shared inline style for the gradient text effect — can't do this in Tailwind alone
const gradientText: React.CSSProperties = {
  background: 'linear-gradient(135deg, #e2e8f0 0%, #c4b5fd 55%, #93c5fd 100%)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  backgroundClip: 'text',
}

const gradientTextLarge: React.CSSProperties = {
  ...gradientText,
  background: 'linear-gradient(135deg, #f8fafc 0%, #c4b5fd 45%, #67e8f9 100%)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  backgroundClip: 'text',
}

export function MarkdownMessage({ content, readingMode = 'normal' }: { content: string; readingMode?: ReadingMode }) {
  const isLarge = readingMode === 'large' || readingMode === 'teleprompter'
  const textStyle = isLarge ? gradientTextLarge : gradientText

  return (
    <ReactMarkdown
      components={{
        p({ children }) {
          return (
            <p
              className={isLarge
                ? 'font-semibold leading-snug mb-3 last:mb-0 tracking-[-0.01em]'
                : 'font-medium leading-relaxed mb-2 last:mb-0 tracking-[-0.005em]'
              }
              style={{
                ...textStyle,
                fontSize: isLarge ? '18px' : '14px',
              }}
            >
              {children}
            </p>
          )
        },

        code({ className, children }) {
          const match = /language-(\w+)/.exec(className || '')
          const codeText = String(children).replace(/\n$/, '')
          if (match) {
            return (
              <div className="rounded-lg overflow-hidden border border-violet-400/20 my-2">
                <div className="flex items-center justify-between px-3 py-1.5 bg-violet-400/[0.07] border-b border-violet-400/10">
                  <span className="font-mono text-[10px] tracking-widest text-violet-400/80 uppercase font-bold">
                    {match[1]}
                  </span>
                  <CopyButton text={codeText} />
                </div>
                <SyntaxHighlighter
                  style={codeTheme}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{ margin: 0 }}
                >
                  {codeText}
                </SyntaxHighlighter>
              </div>
            )
          }
          return (
            <code className="font-mono text-[11.5px] text-cyan-300 bg-cyan-400/10 border border-cyan-400/20 px-1 py-0.5 rounded">
              {children}
            </code>
          )
        },

        h1({ children }) {
          return (
            <h1 className="text-[15px] font-bold mb-2 mt-3 first:mt-0 tracking-tight" style={gradientTextLarge}>
              {children}
            </h1>
          )
        },
        h2({ children }) {
          return (
            <h2 className="text-[14px] font-bold mb-1.5 mt-3 first:mt-0" style={gradientText}>
              {children}
            </h2>
          )
        },
        h3({ children }) {
          return (
            <h3 className="text-[13px] font-semibold mb-1 mt-2 first:mt-0 text-white/70">
              {children}
            </h3>
          )
        },

        ul({ children }) {
          return <ul className="my-2 flex flex-col gap-1.5 list-none pl-0">{children}</ul>
        },
        ol({ children }) {
          return <ol className="my-2 flex flex-col gap-1.5 list-none pl-0">{children}</ol>
        },
        li({ children }) {
          return (
            <li
              className={`flex gap-2 items-baseline ${isLarge ? 'text-[17px]' : 'text-[13px]'} leading-relaxed`}
              style={textStyle}
            >
              <span className="text-violet-400/70 flex-shrink-0 text-[9px] mt-0.5 font-bold">◆</span>
              <span>{children}</span>
            </li>
          )
        },

        strong({ children }) {
          return (
            <strong className="font-bold" style={{ ...gradientTextLarge, filter: 'brightness(1.15)' }}>
              {children}
            </strong>
          )
        },
        em({ children }) {
          return <em className="text-violet-300/70 italic">{children}</em>
        },

        blockquote({ children }) {
          return (
            <blockquote className="border-l-2 border-violet-400/40 pl-3 my-2 text-white/50 italic text-[12px]">
              {children}
            </blockquote>
          )
        },

        hr() {
          return (
            <hr className="my-3 border-0 h-px" style={{ background: 'linear-gradient(90deg, transparent, rgba(167,139,250,0.3), transparent)' }} />
          )
        },

        a({ children }) {
          return (
            <span className="text-cyan-300/80 underline underline-offset-2 decoration-cyan-400/30 cursor-default">
              {children}
            </span>
          )
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
