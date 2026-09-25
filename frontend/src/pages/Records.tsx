import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { api, type DCR, type Meta, type RecordFilters } from '../api'
import { CapaBadge, CriticalBadge, fmtMoney, fmtShort, isOpen, show, StatusBadge, TYPE_LABEL, TypeBadge } from '../ui'

const FINANCIAL_COLUMN = { key: 'financial_impact' as const, label: 'Financial impact' }

/** Leading amount of the free-text "Financial impact" cell, for sorting ("1.785 €" → 1785). */
function amountOf(text: string | null): number {
  const m = /\d[\d.,\s]*/.exec(text ?? '')
  if (!m) return 0
  let n = m[0].replace(/\s/g, '')
  if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(n)) n = n.replace(/\./g, '').replace(',', '.')
  else if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(n)) n = n.replace(/,/g, '')
  else n = n.replace(',', '.')
  return parseFloat(n) || 0
}

type SortKey =
  | 'tracking_number' | 'type' | 'critical' | 'occurred_on' | 'amex_office' | 'supplier'
  | 'customer' | 'category' | 'capa_needed' | 'status' | 'closure_date' | 'financial_impact'

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
  const [financialTotal, setFinancialTotal] = useState<number | null>(null)
  const financial = Boolean(filters.financial_year)
  const columns = financial ? [...COLUMNS, FINANCIAL_COLUMN] : COLUMNS

  // the financial list sorts by amount, largest first; other lists keep the default order
  useEffect(() => {
    setSort(financial ? { key: 'financial_impact', dir: 'desc' } : { key: 'occurred_on', dir: 'desc' })
  }, [financial])

  // the exact EUR total comes from the dashboard, so the list and the tile always agree
  useEffect(() => {
    if (!financial) return setFinancialTotal(null)
    api.dashboard().then((d) => setFinancialTotal(d.kpis.financial_ytd_eur)).catch(() => setFinancialTotal(null))
  }, [financial, refreshKey])

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
      const av = sort.key === 'financial_impact' ? amountOf(a.financial_impact) : ((a[sort.key] ?? '') as string)
      const bv = sort.key === 'financial_impact' ? amountOf(b.financial_impact) : ((b[sort.key] ?? '') as string)
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
          {filters.overdue && (
            <span className="filter-chip">
              Overdue: open more than 60 days
              <button aria-label="Remove overdue filter" onClick={() => set({ overdue: undefined })}>×</button>
            </span>
          )}
          {filters.financial_year && (
            <span className="filter-chip">
              {filters.financial_year} cases with a EUR financial impact
              <button aria-label="Remove financial impact filter" onClick={() => set({ financial_year: undefined })}>×</button>
            </span>
          )}
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
            <>
              {`Showing ${rows.length} of ${meta.record_count} records`}
              {financial && financialTotal !== null && <> · total financial impact <b className="tnum">{fmtMoney(financialTotal)}</b></>}
            </>
          ) : (
            'Loading…'
          )}
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((c) => {
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
                  {financial && <td className="tnum cell-clip">{show(r.financial_impact)}</td>}
                </tr>
              ))}
              {rows && rows.length === 0 && (
                <tr>
                  <td colSpan={columns.length} className="empty-row">
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
