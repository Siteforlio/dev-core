interface Recipient { name: string }

interface Props {
  open: boolean
  recipients: Recipient[]
  toEmails: string
  onToEmailsChange: (v: string) => void
  subject: string
  body: string
  onSubjectChange: (v: string) => void
  onBodyChange: (v: string) => void
  onClose: () => void
  onSend: () => void
  sending?: boolean
  composing?: boolean
}

export default function DebriefEmailModal({ open, recipients, toEmails, onToEmailsChange, subject, body, onSubjectChange, onBodyChange, onClose, onSend, sending, composing }: Props) {
  if (!open) return null

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        background: 'rgba(3,10,20,0.75)',
        backdropFilter: 'blur(8px)',
        display: 'grid',
        placeItems: 'center',
        padding: '20px',
        animation: 'dcFade .2s ease both',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '540px',
          maxHeight: '90vh',
          overflow: 'auto',
          borderRadius: '20px',
          background: '#070f1c',
          border: '1px solid rgba(34,211,238,0.15)',
          boxShadow: '0 40px 80px rgba(3,10,20,0.9)',
          animation: 'dcFadeUp .28s cubic-bezier(.2,.7,.2,1) both',
          fontFamily: "'Manrope', sans-serif",
          color: '#e2e8f0',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '18px 22px',
          borderBottom: '1px solid rgba(34,211,238,0.08)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '34px', height: '34px',
              borderRadius: '10px',
              background: 'rgba(34,211,238,0.1)',
              border: '1px solid rgba(34,211,238,0.2)',
              display: 'grid',
              placeItems: 'center',
              color: '#22d3ee',
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="5" width="18" height="14" rx="3" stroke="currentColor" strokeWidth="1.8"/>
                <path d="m4 7 8 6 8-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '15px', color: '#f1f5f9' }}>Follow-up email</div>
              <div style={{ fontSize: '11.5px', fontWeight: 500, color: 'rgba(148,163,184,0.5)' }}>Draft ready · edit before sending</div>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" style={{
            width: '30px', height: '30px',
            borderRadius: '8px',
            border: '1px solid rgba(34,211,238,0.1)',
            background: 'rgba(255,255,255,0.03)',
            cursor: 'pointer',
            display: 'grid',
            placeItems: 'center',
            color: 'rgba(148,163,184,0.6)',
            outline: 'none',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Fields */}
        <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <Field label="To">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {recipients.length > 0 && (
                <div style={{
                  display: 'flex', flexWrap: 'wrap', gap: '5px',
                  padding: '8px 10px',
                  border: '1px solid rgba(34,211,238,0.08)',
                  borderRadius: '10px',
                  background: 'rgba(255,255,255,0.01)',
                }}>
                  {recipients.map(r => (
                    <span key={r.name} style={{
                      display: 'inline-flex', alignItems: 'center',
                      fontSize: '12px', fontWeight: 600,
                      padding: '3px 8px', borderRadius: '6px',
                      background: 'rgba(34,211,238,0.08)',
                      color: '#22d3ee',
                      border: '1px solid rgba(34,211,238,0.15)',
                    }}>
                      {r.name}
                    </span>
                  ))}
                </div>
              )}
              <input
                value={toEmails}
                onChange={e => onToEmailsChange(e.target.value)}
                placeholder="email@example.com, another@example.com"
                style={{
                  width: '100%', padding: '10px 12px',
                  border: '1px solid rgba(34,211,238,0.1)',
                  borderRadius: '10px',
                  background: 'rgba(255,255,255,0.02)',
                  fontSize: '13px', fontWeight: 500, color: '#e2e8f0',
                  outline: 'none', fontFamily: "'Manrope', sans-serif",
                }}
              />
            </div>
          </Field>

          <Field label="Subject">
            <input
              value={subject}
              onChange={e => onSubjectChange(e.target.value)}
              disabled={composing}
              placeholder={composing ? 'Generating…' : 'Subject'}
              style={{
                width: '100%', padding: '10px 12px',
                border: '1px solid rgba(34,211,238,0.1)',
                borderRadius: '10px',
                background: 'rgba(255,255,255,0.02)',
                fontSize: '13.5px', fontWeight: 600,
                color: composing ? 'rgba(148,163,184,0.4)' : '#e2e8f0',
                outline: 'none', fontFamily: "'Manrope', sans-serif",
              }}
            />
          </Field>

          <Field label="Message">
            <div style={{ position: 'relative' }}>
              <textarea
                value={body}
                onChange={e => onBodyChange(e.target.value)}
                disabled={composing}
                placeholder={composing ? '' : 'Email body…'}
                style={{
                  width: '100%', minHeight: '190px', resize: 'vertical',
                  padding: '12px',
                  border: '1px solid rgba(34,211,238,0.1)',
                  borderRadius: '10px',
                  background: 'rgba(255,255,255,0.02)',
                  fontSize: '13px', lineHeight: 1.65, color: 'rgba(226,232,240,0.8)',
                  outline: 'none', fontFamily: "'Manrope', sans-serif",
                  opacity: composing ? 0.3 : 1,
                }}
              />
              {composing && (
                <div style={{
                  position: 'absolute', inset: 0,
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center', gap: '10px',
                  pointerEvents: 'none',
                }}>
                  <div style={{ width: '20px', height: '20px', border: '2px solid rgba(34,211,238,0.3)', borderTopColor: '#22d3ee', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'rgba(34,211,238,0.7)', fontFamily: "'Manrope', sans-serif" }}>
                    AI is composing your email…
                  </span>
                </div>
              )}
            </div>
          </Field>
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', justifyContent: 'flex-end', gap: '9px',
          padding: '14px 22px',
          borderTop: '1px solid rgba(34,211,238,0.08)',
        }}>
          <button onClick={onClose} style={{
            padding: '10px 18px', borderRadius: '10px',
            border: '1px solid rgba(34,211,238,0.1)',
            background: 'rgba(255,255,255,0.02)',
            fontWeight: 600, fontSize: '13px',
            cursor: 'pointer', color: 'rgba(148,163,184,0.7)',
            outline: 'none', fontFamily: "'Manrope', sans-serif",
          }}>
            Cancel
          </button>
          <button
            onClick={onSend}
            disabled={sending || composing}
            style={{
              display: 'flex', alignItems: 'center', gap: '7px',
              padding: '10px 20px', borderRadius: '10px',
              border: `1px solid ${(sending || composing) ? 'rgba(34,211,238,0.15)' : 'rgba(34,211,238,0.35)'}`,
              background: (sending || composing)
                ? 'rgba(34,211,238,0.05)'
                : 'linear-gradient(180deg, rgba(34,211,238,0.16), rgba(34,211,238,0.09))',
              color: (sending || composing) ? 'rgba(34,211,238,0.45)' : '#22d3ee',
              fontWeight: 700, fontSize: '13px',
              cursor: (sending || composing) ? 'default' : 'pointer', outline: 'none',
              fontFamily: "'Manrope', sans-serif",
              transition: 'all .15s ease',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M4 12 20 4l-6 16-3-6-7-2Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/>
            </svg>
            {composing ? 'Composing…' : sending ? 'Sending…' : 'Send follow-up'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{
        display: 'block',
        fontSize: '10.5px', fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '0.07em',
        color: 'rgba(148,163,184,0.4)',
        marginBottom: '6px',
        fontFamily: "'Manrope', sans-serif",
      }}>
        {label}
      </label>
      {children}
    </div>
  )
}
