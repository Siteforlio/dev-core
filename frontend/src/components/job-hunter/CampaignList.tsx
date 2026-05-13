import { useState } from 'react'
import type { Campaign } from '../../types/jobHunter'
import { useJobHunter } from '../../hooks/useJobHunter'

interface Props {
  campaigns: Campaign[]
  onSelect: (campaignId: string) => void
  onCreateNew: () => void
  onDeleted: (campaignId: string) => void
}

const STATUS_STYLE: Record<string, { dot: string; label: string; bg: string; border: string }> = {
  active:   { dot: '#34d399', label: '#34d399', bg: 'rgba(52,211,153,0.08)',  border: 'rgba(52,211,153,0.2)'  },
  paused:   { dot: '#fbbf24', label: '#fbbf24', bg: 'rgba(251,191,36,0.08)',  border: 'rgba(251,191,36,0.2)'  },
  archived: { dot: '#6b7280', label: '#6b7280', bg: 'rgba(107,114,128,0.08)', border: 'rgba(107,114,128,0.2)' },
}

export default function CampaignList({ campaigns, onSelect, onCreateNew, onDeleted }: Props) {
  const { deleteCampaign } = useJobHunter()
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const handleDelete = async (id: string) => {
    setDeleting(id)
    try {
      await deleteCampaign(id)
      onDeleted(id)
    } catch {
      // silent
    } finally {
      setDeleting(null)
      setConfirmId(null)
    }
  }

  return (
    <div className="flex flex-col gap-6 h-full">

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2
            className="text-xs font-semibold uppercase tracking-[0.18em]"
            style={{ color: 'rgba(34,211,238,0.6)', fontFamily: 'monospace' }}
          >
            Campaigns
          </h2>
          <p className="text-[11px] mt-0.5" style={{ color: 'rgba(100,116,139,0.6)', fontFamily: 'monospace' }}>
            {campaigns.length} active hunt{campaigns.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={onCreateNew}
          className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] px-4 py-2 rounded transition-all duration-150"
          style={{
            background: 'rgba(34,211,238,0.08)',
            border: '1px solid rgba(34,211,238,0.25)',
            color: '#22d3ee',
            fontFamily: 'monospace',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = 'rgba(34,211,238,0.14)'
            e.currentTarget.style.borderColor = 'rgba(34,211,238,0.45)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'rgba(34,211,238,0.08)'
            e.currentTarget.style.borderColor = 'rgba(34,211,238,0.25)'
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Campaign
        </button>
      </div>

      {/* Table header */}
      {campaigns.length > 0 && (
        <div
          className="grid items-center"
          style={{
            gridTemplateColumns: '1fr 180px 120px 140px',
            padding: '6px 20px',
            borderTop: '1px solid rgba(34,211,238,0.08)',
            borderBottom: '1px solid rgba(34,211,238,0.08)',
            background: 'rgba(34,211,238,0.02)',
          }}
        >
          {(['Campaign', 'Category', 'Status', 'Actions'] as const).map(col => (
            <span
              key={col}
              className="text-[10px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: 'rgba(34,211,238,0.4)', fontFamily: 'monospace' }}
            >
              {col}
            </span>
          ))}
        </div>
      )}

      {/* Rows */}
      {campaigns.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 gap-4">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.12)' }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.6">
              <rect x="2" y="7" width="20" height="14" rx="2" />
              <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
            </svg>
          </div>
          <p className="text-sm" style={{ color: 'rgba(100,116,139,0.7)', fontFamily: 'monospace' }}>
            No campaigns yet
          </p>
          <button
            onClick={onCreateNew}
            className="text-xs underline transition-colors"
            style={{ color: 'rgba(34,211,238,0.6)' }}
          >
            Create your first campaign
          </button>
        </div>
      ) : (
        <div className="flex flex-col">
          {campaigns.map((c) => {
            const s = STATUS_STYLE[c.status] ?? STATUS_STYLE.archived
            return (
              <div
                key={c.id}
                className="grid items-center transition-all duration-150"
                style={{
                  gridTemplateColumns: '1fr 180px 120px 140px',
                  padding: '14px 20px',
                  borderBottom: '1px solid rgba(34,211,238,0.05)',
                  background: 'transparent',
                  cursor: 'default',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.03)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                {/* Name */}
                <div className="min-w-0 pr-4">
                  <p className="text-sm font-semibold truncate" style={{ color: 'rgba(226,232,240,0.92)', fontFamily: 'monospace' }}>
                    {c.name}
                  </p>
                </div>

                {/* Category */}
                <p className="text-xs truncate" style={{ color: 'rgba(100,116,139,0.7)', fontFamily: 'monospace' }}>
                  {c.broadCategory}
                </p>

                {/* Status pill */}
                <div>
                  <span
                    className="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded"
                    style={{ background: s.bg, border: `1px solid ${s.border}`, color: s.label, fontFamily: 'monospace' }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: s.dot }} />
                    {c.status}
                  </span>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  {confirmId === c.id ? (
                    <>
                      <span className="text-[11px]" style={{ color: 'rgba(148,163,184,0.6)', fontFamily: 'monospace' }}>Delete?</span>
                      <button
                        onClick={() => handleDelete(c.id)}
                        disabled={deleting === c.id}
                        className="text-[11px] px-2.5 py-1 rounded transition-all"
                        style={{ background: 'rgba(248,113,113,0.12)', border: '1px solid rgba(248,113,113,0.3)', color: '#f87171', fontFamily: 'monospace' }}
                      >
                        {deleting === c.id ? '…' : 'Yes'}
                      </button>
                      <button
                        onClick={() => setConfirmId(null)}
                        className="text-[11px] px-2.5 py-1 rounded transition-all"
                        style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(148,163,184,0.6)', fontFamily: 'monospace' }}
                      >
                        No
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => onSelect(c.id)}
                        className="text-[11px] font-semibold px-3 py-1.5 rounded transition-all duration-150"
                        style={{
                          background: 'rgba(34,211,238,0.07)',
                          border: '1px solid rgba(34,211,238,0.2)',
                          color: '#22d3ee',
                          fontFamily: 'monospace',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.background = 'rgba(34,211,238,0.13)'
                          e.currentTarget.style.borderColor = 'rgba(34,211,238,0.4)'
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.background = 'rgba(34,211,238,0.07)'
                          e.currentTarget.style.borderColor = 'rgba(34,211,238,0.2)'
                        }}
                      >
                        Open →
                      </button>
                      <button
                        onClick={() => setConfirmId(c.id)}
                        className="flex items-center justify-center rounded transition-all duration-150"
                        style={{ width: '28px', height: '28px', color: 'rgba(100,116,139,0.4)', background: 'transparent', border: '1px solid transparent' }}
                        title="Delete campaign"
                        onMouseEnter={e => {
                          e.currentTarget.style.color = '#f87171'
                          e.currentTarget.style.borderColor = 'rgba(248,113,113,0.2)'
                          e.currentTarget.style.background = 'rgba(248,113,113,0.06)'
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.color = 'rgba(100,116,139,0.4)'
                          e.currentTarget.style.borderColor = 'transparent'
                          e.currentTarget.style.background = 'transparent'
                        }}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                        </svg>
                      </button>
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
