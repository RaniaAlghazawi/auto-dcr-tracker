import { useEffect, useState, type CSSProperties } from 'react'
import { api, type Dashboard as DashboardData, type DCR, type NamedCount, type RecordFilters } from '../api'
import { CapaBadge, fmtMoney, OccurredCell, show, TYPE_COLOR, TYPE_LABEL, TypeBadge } from '../ui'

interface Props {
  refreshKey: number
  openRecords: (filters: RecordFilters) => void
  openDetail: (r: DCR) => void
}

export function Dashboard({ refreshKey, openDetail, openRecords }: Props) {
  const [year, setYear] = useState<number | null>(null) // charts only; KPIs cover the whole tracker
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .dashboard(year)
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [year, refreshKey])

  if (error) return <section className="view"><div className="notice is-critical">Could not load the dashboard: {error}</div></section>
  if (!data) return <section className="view"><div className="result-count">Loading…</div></section>

  const k = data.kpis
  const tiles = [
    { label: 'Total entries', value: k.total, caption: 'every DCR ever logged in the tracker', bar: 'var(--accent)', filters: {} },
    { label: 'Open cases', value: k.open, caption: 'across Vienna & Kenya', bar: 'var(--status-open)', filters: { status: 'Open' } },
    { label: 'Overdue', value: k.overdue, caption: 'open more than 60 days (SOP 5 threshold)', bar: 'var(--critical)', filters: { overdue: 'true' } },
    { label: `${data.year} financial impact`, value: fmtMoney(k.financial_ytd_eur), caption: 'logged YTD, EUR-denominated', bar: 'var(--finance)', filters: { financial_year: String(data.year) } },
  ]
  const period = year ? String(year) : 'full tracker'

  return (
    <section className="view">
      <div className="kpi-grid">
        {tiles.map((t) => (
          <button
            key={t.label}
            type="button"
            className="card kpi-tile is-clickable"
            style={{ '--bar-color': t.bar } as CSSProperties}
            onClick={() => openRecords(t.filters)}
            title={`Show the ${t.label.toLowerCase()} as a list`}
          >
            <div className="kpi-tile__label">{t.label}</div>
            <div className="kpi-tile__value tnum">{t.value}</div>
            <div className="kpi-tile__caption">{t.caption}</div>
            <div className="kpi-tile__more">View list →</div>
          </button>
        ))}
      </div>

      <div className="chart-filter-bar">
        <span className="chart-filter-bar__label">Filter charts by year</span>
        <div className="pill-group" role="group" aria-label="Filter charts by year">
          {[null, ...data.years].map((y) => (
            <button key={y ?? 'all'} type="button" className={`pill${year === y ? ' is-active' : ''}`} aria-pressed={year === y} onClick={() => setYear(y)}>
              {y ?? 'All years'}
            </button>
          ))}
        </div>
      </div>

      <div className="charts-row">
        <div className="card chart-card">
          <div className="chart-card__title">By type</div>
          <div className="chart-card__sub">Deviation · Complaint · Recall · Safety Notice · Partner Issue Report</div>
          <BarList rows={data.by_type.map((t) => ({ name: TYPE_LABEL[t.name] ?? t.name, count: t.count, color: TYPE_COLOR[t.name] }))} dots />
        </div>
        <div className="card chart-card">
          <div className="chart-card__title">By issue category</div>
          <div className="chart-card__sub">Most common root categories, {year ? year : 'all records'}</div>
          <BarList rows={withColor(data.by_category, 'var(--accent)')} />
        </div>
      </div>

      <div className="charts-row">
        <div className="card chart-card">
          <div className="chart-card__title">Open cases by supplier</div>
          <div className="chart-card__sub">Top suppliers with unresolved DCRs, {period}</div>
          <BarList rows={withColor(data.open_by_supplier, 'var(--serious)')} empty="No open cases in this period." />
        </div>
        <div className="card chart-card">
          <div className="chart-card__title">Open cases by customer</div>
          <div className="chart-card__sub">Top customers with unresolved DCRs, {period}</div>
          <BarList rows={withColor(data.open_by_customer, 'var(--warning)')} empty="No open cases in this period." />
        </div>
      </div>

      <div className="card table-card">
        <div className="table-card__head">
          <div className="section-title" style={{ margin: 0 }}>
            Needs attention
          </div>
          <span className="chart-card__sub" style={{ margin: 0 }}>
            Critical &amp; still open · click a row to open
          </span>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>DCR #</th>
                <th>Type</th>
                <th>Office</th>
                <th>Customer</th>
                <th>Category</th>
                <th>Occurred on</th>
                <th>CAPA</th>
              </tr>
            </thead>
            <tbody>
              {data.attention.map((r) => (
                <tr key={r.id} className="is-clickable" onClick={() => openDetail(r)}>
                  <td className="cell-id mono">{r.tracking_number}</td>
                  <td>
                    <TypeBadge type={r.type} />
                  </td>
                  <td>{show(r.amex_office)}</td>
                  <td className="cell-clip">{show(r.customer)}</td>
                  <td>{show(r.category)}</td>
                  <td>
                    <OccurredCell r={r} />
                  </td>
                  <td>
                    <CapaBadge r={r} />
                  </td>
                </tr>
              ))}
              {data.attention.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty-row">
                    Nothing needs attention right now.
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

type Bar = NamedCount & { color?: string }

const withColor = (rows: NamedCount[], color: string): Bar[] => rows.map((r) => ({ ...r, color }))

function BarList({ rows, dots, empty }: { rows: Bar[]; dots?: boolean; empty?: string }) {
  if (!rows.length) return <div className="bar-empty">{empty ?? 'No data for this period.'}</div>
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <div className="bar-list">
      {rows.map((r) => (
        <div key={r.name} className="bar-row" title={`${r.name}: ${r.count}`}>
          <div className="bar-row__label">
            {dots && <span className="dot" style={{ background: r.color }} />}
            {r.name}
          </div>
          <div className="bar-row__track">
            <div className="bar-row__fill" style={{ width: `${Math.round((r.count / max) * 100)}%`, background: r.color }} />
          </div>
          <div className="bar-row__count tnum">{r.count}</div>
        </div>
      ))}
    </div>
  )
}
