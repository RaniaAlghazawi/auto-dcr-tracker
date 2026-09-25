import type { ReactNode } from 'react'

// Validated categorical order (dataviz palette check, light surface) — never reorder or cycle.
export const TYPE_COLORS: Record<string, string> = {
  Deviation: '#2f78b8',
  Complaint: '#b8322b',
  Recall: '#a87a12',
  'Safety notice': '#8a5aa8',
  'Partner issue report': '#5b9148',
  'Not set': '#9db2bf',
}

export const TYPE_LETTER: Record<string, string> = {
  Deviation: 'D',
  Complaint: 'C',
  Recall: 'R',
  'Safety notice': 'S',
  'Partner issue report': 'PIR',
  'Not set': '?',
}

export function TypeBadge({ type }: { type: string | null }) {
  const t = type ?? 'Not set'
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-charcoal">
      <span
        className="inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-[10px] font-bold text-white"
        style={{ background: TYPE_COLORS[t] ?? TYPE_COLORS['Not set'] }}
      >
        {TYPE_LETTER[t] ?? '?'}
      </span>
      {t}
    </span>
  )
}

const STATUS_STYLE: Record<string, string> = {
  Draft: 'bg-air-force-blue/15 text-air-force-blue ring-air-force-blue/40',
  Open: 'bg-oxblood/10 text-oxblood ring-oxblood/30',
  Closed: 'bg-dusty-olive/15 text-[#4f6349] ring-dusty-olive/40',
}

export function StatusBadge({ status }: { status: string }) {
  const label = status === 'Draft' ? 'Draft · review' : status
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${STATUS_STYLE[status] ?? ''}`}>
      {label}
    </span>
  )
}

export function Card({
  title,
  action,
  children,
  className = '',
}: {
  title?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-lg border border-cool-steel/40 bg-white p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-base font-normal text-charcoal">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Select({
  label,
  value,
  onChange,
  options,
  allLabel = 'All',
}: {
  label: string
  value: string | undefined
  onChange: (v: string | undefined) => void
  options: (string | { value: string; label: string })[]
  allLabel?: string
}) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-charcoal/70">
      {label}
      <select
        className="rounded-md border border-cool-steel/60 bg-white px-2.5 py-1.5 text-sm text-charcoal focus:border-oxblood focus:outline-none"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || undefined)}
      >
        <option value="">{allLabel}</option>
        {options.map((o) => {
          const opt = typeof o === 'string' ? { value: o, label: o } : o
          return (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          )
        })}
      </select>
    </label>
  )
}

export function TypeLegend({ types }: { types: string[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-charcoal/80">
      {types.map((t) => (
        <span key={t} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: TYPE_COLORS[t] }} />
          {t}
        </span>
      ))}
    </div>
  )
}

export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  return m ? `${m[3]}-${m[2]}-${m[1]}` : iso
}
