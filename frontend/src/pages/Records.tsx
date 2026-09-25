import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { api, type DCR, type Meta, type RecordFilters } from '../api'
import { CapaBadge, CriticalBadge, fmtShort, isOpen, show, StatusBadge, TYPE_LABEL, TypeBadge } from '../ui'

type SortKey =
  | 'tracking_number' | 'type' | 'critical' | 'occurred_on' | 'amex_office' | 'supplier'
  | 'customer' | 'category' | 'capa_needed' | 'status' | 'closure_date'

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'tracking_number', label: 'DCR #' },
  { key: 'type', label: 'Type' },
  { key: 'critical', label: 'Critical' },
  { key: 'occurred_on', label: 'Occurred on' },
  { key: 'amex_office', label: 'Office' },
  { key: 'supplier', label: 'Supplier' },
  { key: 'customer', label: 'Customer' },
  { key: 'category', label: 'Category' },
  { key: 'capa_needed', label: 'CAPA' },
  { key: 'status', label: 'Status' },
  { key: 'closure_date', label: 'Closure date' },
]

interface Props {
  meta: Meta
  filters: RecordFilters
  setFilters: (f: RecordFilters) => void
  refreshKey: number
  openDetail: (r: DCR) => void
}

export function Records({ meta, filters, setFilters, refreshKey, openDetail }: Props) {
  const [rows, setRows] = useState<DCR[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState(filters.search ?? '')
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'occurred_on', dir: 'desc' })

  // debounce free-text search
  useEffect(() => {
    const t = setTimeout(() => {
      if ((filters.search ?? '') !== search) setFilters({ ...filters, search: search || undefined })
    }, 250)
    return () => clearTimeout(t)
  }, [search]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setError(null)
    api.list(filters).then(setRows).catch((e) => setError(String(e.message ?? e)))
  }, [filters, refreshKey])

  const sorted = useMemo(() => {
    if (!rows) return []
    const dir = sort.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const av = (a[sort.key] ?? '') as string
      const bv = (b[sort.key] ?? '') as string
      return av < bv ? -dir : av > bv ? dir : 0
    })
  }, [rows, sort])

  const set = (patch: Partial<RecordFilters>) => setFilters({ ...filters, ...patch })
  const select = (key: keyof RecordFilters) => (e: ChangeEvent<HTMLSelectElement>) =>
    set({ [key]: e.target.value === 'All' ? undefined : e.target.value })

  return (
    <section className="view">
      <div className="card" style={{ padding: '14px 18px' }}>
        <div className="filter-bar">
          <div className="filter-field">
            <input
              type="search"
              placeholder="Search DCR #, customer, supplier, category…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search records"
            />
          </div>
          <div className="filter-field">
            <select value={filters.type ?? 'All'} onChange={select('type')} aria-label="Type">
              <option value="All">All types</option>
              {meta.types.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABEL[t] ?? t}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-field">
            <select value={filters.status ?? 'All'} onChange={select('status')} aria-label="Status">
              <option value="All">All statuses</option>
              <option>Open</option>
              <option>Closed</option>
            </select>
          </div>
          <div className="filter-field">
            <select value={filters.critical ?? 'All'} onChange={select('critical')} aria-label="Critical">
              <option value="All">Critical: all</option>
              <option value="Y">Critical only</option>
              <option value="N">Marked not critical</option>
              <option value="N/A">Not assessed</option>
            </select>
          </div>
          <div className="filter-field">
            <select value={filters.office ?? 'All'} onChange={select('office')} aria-label="Office">
              <option value="All">All offices</option>
              {meta.offices.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          </div>
          <div className="filter-field">
            <select value={filters.customer ?? 'All'} onChange={select('customer')} aria-label="Customer">
              <option value="All">All customers</option>
              {meta.customers.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <button
            className="filter-reset"
            onClick={() => {
              setSearch('')
              setFilters({})
            }}
          >
            Reset filters
          </button>
        </div>
      </div>

      <div className="card table-card">
        <div className="result-count" style={{ paddingTop: 14 }}>
          {error ? (
            <span className="error-note">Could not load records: {error}</span>
          ) : rows ? (
            `Showing ${rows.length} of ${meta.record_count} records`
          ) : (
            'Loading…'
          )}
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {COLUMNS.map((c) => {
                  const sortedBy = sort.key === c.key
                  return (
                    <th
                      key={c.key}
                      className={`sortable${sortedBy ? ' is-sorted' : ''}`}
                      onClick={() =>
                        setSort(sortedBy ? { key: c.key, dir: sort.dir === 'asc' ? 'desc' : 'asc' } : { key: c.key, dir: 'asc' })
                      }
                      aria-sort={sortedBy ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      {c.label}
                      <span className="sort-arrow">{sortedBy && sort.dir === 'desc' ? '▼' : '▲'}</span>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id} className="is-clickable" onClick={() => openDetail(r)}>
                  <td className="cell-id mono">{r.tracking_number}</td>
                  <td>
                    <TypeBadge type={r.type} />
                  </td>
                  <td>
                    <CriticalBadge r={r} />
                  </td>
                  <td className="tnum">{fmtShort(r.occurred_on)}</td>
                  <td>{show(r.amex_office)}</td>
                  <td className="cell-clip">{show(r.supplier)}</td>
                  <td className="cell-clip">{show(r.customer)}</td>
                  <td>{show(r.category)}</td>
                  <td>
                    <CapaBadge r={r} />
                  </td>
                  <td>
                    <StatusBadge r={r} />
                  </td>
                  <td className={`tnum${isOpen(r) ? ' cell-muted' : ''}`}>{fmtShort(r.closure_date)}</td>
                </tr>
              ))}
              {rows && rows.length === 0 && (
                <tr>
                  <td colSpan={11} className="empty-row">
                    No records match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
