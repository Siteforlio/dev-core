import ReactMarkdown from 'react-markdown'

interface Props {
  content: string
  streaming?: boolean
  compact?: boolean
}

const ACCENT = '#22d3ee'
const TEXT_PRIMARY = '#e2e8f0'
const TEXT_SECONDARY = '#94a3b8'

export default function ChatMarkdown({ content, streaming, compact = false }: Props) {
  const base = compact ? '12px' : '13px'

  return (
    <div style={{ fontSize: base, lineHeight: 1.65, color: '#cbd5e1', wordBreak: 'break-word' }}>
      <ReactMarkdown
        components={{
          p: ({ children }) => (
            <p style={{ margin: '0 0 8px 0', lineHeight: 1.65 }}>{children}</p>
          ),
          ul: ({ children }) => (
            <ul style={{ paddingLeft: '16px', margin: '4px 0 8px', listStyleType: 'disc' }}>
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol style={{ paddingLeft: '16px', margin: '4px 0 8px' }}>{children}</ol>
          ),
          li: ({ children }) => (
            <li style={{ marginBottom: '3px', lineHeight: 1.55 }}>{children}</li>
          ),
          strong: ({ children }) => (
            <strong style={{ color: TEXT_PRIMARY, fontWeight: 600 }}>{children}</strong>
          ),
          em: ({ children }) => (
            <em style={{ color: TEXT_SECONDARY, fontStyle: 'italic' }}>{children}</em>
          ),
          code: ({ children, className }) => {
            const isBlock = !!className
            if (isBlock) {
              return (
                <pre
                  style={{
                    background: '#09090f',
                    border: '1px solid #1a1a2c',
                    borderRadius: '7px',
                    padding: '10px 14px',
                    overflowX: 'auto',
                    margin: '8px 0',
                  }}
                >
                  <code
                    style={{
                      fontSize: '11px',
                      fontFamily: 'ui-monospace, "Cascadia Code", "SF Mono", Menlo, monospace',
                      color: '#a5f3fc',
                      whiteSpace: 'pre',
                    }}
                  >
                    {children}
                  </code>
                </pre>
              )
            }
            return (
              <code
                style={{
                  background: '#161626',
                  border: '1px solid #222236',
                  borderRadius: '4px',
                  padding: '1px 5px',
                  fontSize: '0.88em',
                  fontFamily: 'ui-monospace, "Cascadia Code", monospace',
                  color: '#7dd3fc',
                }}
              >
                {children}
              </code>
            )
          },
          blockquote: ({ children }) => (
            <blockquote
              style={{
                borderLeft: `2px solid ${ACCENT}`,
                paddingLeft: '12px',
                margin: '8px 0',
                color: TEXT_SECONDARY,
                fontStyle: 'italic',
              }}
            >
              {children}
            </blockquote>
          ),
          h1: ({ children }) => (
            <h1
              style={{
                fontSize: compact ? '14px' : '15px',
                fontWeight: 700,
                color: TEXT_PRIMARY,
                margin: '12px 0 6px',
                lineHeight: 1.3,
              }}
            >
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2
              style={{
                fontSize: compact ? '13px' : '14px',
                fontWeight: 600,
                color: TEXT_PRIMARY,
                margin: '10px 0 5px',
                lineHeight: 1.3,
              }}
            >
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3
              style={{
                fontSize: compact ? '12px' : '13px',
                fontWeight: 600,
                color: '#cbd5e1',
                margin: '8px 0 4px',
                lineHeight: 1.3,
              }}
            >
              {children}
            </h3>
          ),
          hr: () => (
            <hr style={{ border: 'none', borderTop: '1px solid #1a1a2c', margin: '12px 0' }} />
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: ACCENT,
                textDecoration: 'underline',
                textDecorationColor: 'rgba(34,211,238,0.4)',
              }}
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>

      {streaming && (
        <span
          aria-hidden
          style={{
            display: 'inline-block',
            width: '2px',
            height: compact ? '12px' : '13px',
            background: ACCENT,
            verticalAlign: 'text-bottom',
            marginLeft: '2px',
            animation: 'blink 1s step-start infinite',
          }}
        />
      )}
    </div>
  )
}
