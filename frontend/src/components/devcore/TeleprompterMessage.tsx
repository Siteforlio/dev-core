import React, { useState, useCallback, useEffect, useRef } from 'react'

/**
 * TeleprompterMessage — Click-to-advance sentence highlighter.
 *
 * Design goal: minimize lateral eye movement during video calls.
 * Text is displayed in a narrow, tall column with one sentence highlighted
 * at a time. The user reads the highlighted sentence aloud, clicks (or
 * presses Space) to advance to the next, then repeats.
 *
 * The full text is always visible so the user can preview what's coming.
 */

function splitSentences(text: string): string[] {
  // Split on sentence-ending punctuation followed by whitespace, OR double newlines
  const parts = text
    .split(/(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*\n+|\n{2,}/)
    .map(s => s.trim())
    .filter(Boolean)
  return parts.length > 0 ? parts : [text.trim()]
}

interface Props {
  content: string
  pending?: boolean
}

export function TeleprompterMessage({ content, pending }: Props) {
  const [current, setCurrent] = useState(0)
  const sentences = splitSentences(content)
  const total = sentences.length
  const containerRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLParagraphElement>(null)

  const advance = useCallback(() => {
    setCurrent(i => Math.min(i + 1, total - 1))
  }, [total])

  const retreat = useCallback(() => {
    setCurrent(i => Math.max(i - 1, 0))
  }, [])

  const reset = useCallback(() => setCurrent(0), [])

  // Reset position when content changes (new message)
  useEffect(() => {
    setCurrent(0)
  }, [content])

  // Scroll active sentence into view
  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [current])

  // Keyboard: Space/ArrowRight = advance, ArrowLeft = retreat
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Only when not in an input field
      if ((e.target as HTMLElement).tagName === 'INPUT') return
      if (e.key === ' ' || e.key === 'ArrowRight') { e.preventDefault(); advance() }
      if (e.key === 'ArrowLeft') { e.preventDefault(); retreat() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [advance, retreat])

  return (
    <div className="w-full">
      {/* Sentence list */}
      <div
        ref={containerRef}
        className="space-y-3 max-h-[50vh] overflow-y-auto pr-1 [&::-webkit-scrollbar]:w-[2px] [&::-webkit-scrollbar-thumb]:bg-white/10"
        onClick={advance}
        style={{ cursor: 'pointer' }}
      >
        {sentences.map((s, i) => {
          const isActive  = i === current
          const isPast    = i < current
          const isFuture  = i > current

          return (
            <p
              key={i}
              ref={isActive ? activeRef : undefined}
              className={[
                'leading-snug transition-all duration-300 select-none',
                isActive  ? 'text-white font-semibold text-[20px]'  : '',
                isPast    ? 'text-white/20 text-[16px]'              : '',
                isFuture  ? 'text-white/45 text-[16px]'             : '',
              ].join(' ')}
            >
              {isActive && (
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-violet-400 mr-2 mb-0.5 flex-shrink-0 align-middle" />
              )}
              {s}
              {isActive && pending && (
                <span className="inline-block w-0.5 h-5 bg-violet-400 ml-1 animate-pulse align-middle" />
              )}
            </p>
          )
        })}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mt-3 pt-2 border-t border-white/[0.06]" onClick={e => e.stopPropagation()}>
        <button
          onClick={retreat}
          disabled={current === 0}
          className="font-mono text-[9px] text-white/25 hover:text-white/60 disabled:opacity-0 transition-all px-1"
        >
          ← prev
        </button>
        <span className="font-mono text-[9px] text-white/20 flex-1 text-center">
          {current + 1} / {total} · click or Space to advance
        </span>
        <button
          onClick={reset}
          className="font-mono text-[9px] text-white/25 hover:text-white/60 transition-all px-1"
        >
          ↺ reset
        </button>
      </div>
    </div>
  )
}
