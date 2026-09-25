import type { DCR } from './api'

/** Signed-in reviewer. Login name follows the tracker's "Entered by" format (first letter + surname). */
export const CURRENT_USER = { name: 'Nikolina Ilic', initials: 'NI', login: 'nilic', email: 'nikolina.ilic@amex-healthcare.com' }

// Tracker values -> labels as written in the UI mockup
export const TYPE_LABEL: Record<string, string> = {
  Deviation: 'Deviation',
  Complaint: 'Complaint',
  Recall: 'Recall',
  'Safety notice': 'Safety Notice',
  'Partner issue report': 'Partner Issue Report',
}

export const TYPE_COLOR: Record<string, string> = {
  Deviation: 'var(--type-deviation)',
  Complaint: 'var(--type-complaint)',
  Recall: 'var(--type-recall)',
  'Safety notice': 'var(--type-safety)',
  'Partner issue report': 'var(--type-pir)',
}

const TODAY = new Date(new Date().toDateString())

function toDate(iso: string | null): Date | null {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return null
  const d = new Date(iso.slice(0, 10) + 'T00:00:00')
  return Number.isNaN(d.getTime()) ? null : d
}

export function fmtShort(iso: string | null): string {
  const d = toDate(iso)
  if (!d) return iso || '—'
  const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' }
  if (d.getFullYear() !== TODAY.getFullYear()) opts.year = '2-digit'
  return d.toLocaleDateString('en-US', opts)
}

export function fmtLong(iso: string | null): string {
  const d = toDate(iso)
  return d ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : iso || '—'
}

export function fmtMoney(v: number): string {
  return v > 0 ? '€' + Math.round(v).toLocaleString('en-US') : '—'
}

export const isOpen = (r: DCR) => r.status === 'Open'

export function daysOpen(r: DCR): number | null {
  const d = toDate(r.occurred_on)
  return d ? Math.round((TODAY.getTime() - d.getTime()) / 86_400_000) : null
}

export const show = (v: string | null | undefined) => (v && v.trim() ? v : '—')

export function TypeBadge({ type }: { type: string | null }) {
  if (!type) return <span className="badge cell-muted">—</span>
  return (
    <span className="badge">
      <span className="dot" style={{ background: TYPE_COLOR[type] ?? 'var(--baseline)' }} />
      {TYPE_LABEL[type] ?? type}
    </span>
  )
}

export function StatusBadge({ r }: { r: DCR }) {
  if (r.status === 'Draft')
    return (
      <span className="badge">
        <span className="dot" style={{ background: 'var(--warning)' }} />
        Awaiting review
      </span>
    )
  if (isOpen(r))
    return (
      <span className="badge">
        <span className="dot" style={{ background: 'var(--status-open)' }} />
        Open
      </span>
    )
  return <span className="badge status-closed">Closed</span>
}

export function CriticalBadge({ r }: { r: DCR }) {
  if (r.critical === 'Y')
    return (
      <span className="badge is-critical">
        <span className="tri" />
        Critical
      </span>
    )
  if (r.critical === 'N')
    return (
      <span className="badge">
        <span className="dot" style={{ background: 'var(--good)' }} />
        Not critical
      </span>
    )
  return (
    <span className="badge cell-muted">
      <span className="dot" style={{ background: 'var(--baseline)' }} />
      Not assessed
    </span>
  )
}

export function CapaBadge({ r }: { r: DCR }) {
  if (r.capa_needed === 'Y')
    return (
      <span className="badge capa-yes">
        <span className="dot" />
        CAPA needed
      </span>
    )
  return <span className="capa-no">No CAPA</span>
}

export function OccurredCell({ r }: { r: DCR }) {
  const days = isOpen(r) ? daysOpen(r) : null
  return (
    <>
      <span className="tnum">{fmtShort(r.occurred_on)}</span>
      {days !== null && <span className="flag-tag">{days}d open</span>}
    </>
  )
}

export function BackLink({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button className="back-link" onClick={onClick}>
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M10 3.5 5 8l5 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {label}
    </button>
  )
}
