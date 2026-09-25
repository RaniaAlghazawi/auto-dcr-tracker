import { useEffect, useState } from 'react'
import { api, type DCR, type Filters, type Meta } from '../api'
import { Card, formatDate, Select, StatusBadge, TypeBadge } from '../components/ui'

interface Props {
  meta: Meta
  filters: Filters
  setFilters: (f: Filters) => void
  refreshKey: number
  openDcr: (d: DCR) => void
}

export function RegisterPage({ meta, filters, setFilters, refreshKey, openDcr }: Props) {
  const [rows, setRows] = useState<DCR[] | null>(null)
  const [search, setSearch] = useState(filters.search ?? '')

  useEffect(() => setSearch(filters.search ?? ''), [filters.search])
  useEffect(() => {
    api.list(filters).then(setRows).catch(() => setRows([]))
  }, [filters, refreshKey])

  const set = (patch: Partial<Filters>) => setFilters({ ...filters, ...patch })

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <form
          className="flex flex-col gap-1 text-xs font-medium text-charcoal/70"
          onSubmit={(e) => {
            e.preventDefault()
            set({ search: search || undefined })
          }}
        >
          Search
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onBlur={() => set({ search: search || undefined })}
            placeholder="Project, customer, supplier, text…"
            className="w-64 rounded-md border border-cool-steel/60 px-2.5 py-1.5 text-sm text-charcoal focus:border-oxblood focus:outline-none"
          />
        </form>
        <Select label="Type" value={filters.type} onChange={(v) => set({ type: v })} options={meta.types} />
        <Select label="Status" value={filters.status} onChange={(v) => set({ status: v })} options={['Draft', 'Open', 'Closed']} />
        <Select
          label="Data quality"
          value={filters.has_issues}
          onChange={(v) => set({ has_issues: v })}
          options={[
            { value: 'true', label: 'With findings' },
            { value: 'false', label: 'Complete' },
          ]}
        />
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-charcoal/60">{rows ? `${rows.length} entries` : ''}</span>
          <a
            href={api.exportUrl(filters)}
            className="rounded-md border border-oxblood px-3 py-1.5 text-sm font-medium text-oxblood hover:bg-oxblood hover:text-white"
          >
            Export to Excel
          </a>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] text-sm">
          <thead>
            <tr className="border-b border-cool-steel/50 text-left text-xs font-medium text-charcoal/70">
              <th className="py-2 pr-3">No.</th>
              <th className="py-2 pr-3">Type</th>
              <th className="py-2 pr-3">Occurred</th>
              <th className="py-2 pr-3">Project</th>
              <th className="py-2 pr-3">Customer</th>
              <th className="py-2 pr-3">Supplier</th>
              <th className="py-2 pr-3">Responsible</th>
              <th className="py-2 pr-3">Category</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2 pr-3 text-right">Findings</th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((r) => (
              <tr
                key={r.id}
                onClick={() => openDcr(r)}
                className="cursor-pointer border-b border-cool-steel/20 hover:bg-cool-steel/10"
              >
                <td className="py-2 pr-3 font-medium text-charcoal">{r.tracking_number ?? <span className="text-air-force-blue">new</span>}</td>
                <td className="py-2 pr-3">
                  <TypeBadge type={r.type} />
                </td>
                <td className="whitespace-nowrap py-2 pr-3 tabular-nums">{formatDate(r.occurred_on)}</td>
                <td className="py-2 pr-3 tabular-nums">{r.project ?? '—'}</td>
                <td className="max-w-44 truncate py-2 pr-3">{r.customer ?? '—'}</td>
                <td className="max-w-44 truncate py-2 pr-3">{r.supplier ?? '—'}</td>
                <td className="py-2 pr-3">{r.responsible_party ?? '—'}</td>
                <td className="py-2 pr-3">{r.category ?? '—'}</td>
                <td className="py-2 pr-3">
                  <StatusBadge status={r.status} />
                </td>
                <td className="py-2 pr-3 text-right">
                  {r.issues.length > 0 && (
                    <span title={r.issues.join('\n')} className="rounded bg-oxblood/10 px-1.5 text-xs font-semibold text-oxblood">
                      {r.issues.length}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows?.length === 0 && <p className="py-8 text-center text-sm text-charcoal/60">No entries match these filters.</p>}
      </div>
    </Card>
  )
}
