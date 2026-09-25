import { useEffect, useState } from 'react'
import { api, type DCR, type Dashboard, type Filters, type Meta } from '../api'
import { Matrix, PartyBars, TrendChart } from '../components/charts'
import { Card, formatDate, TYPE_COLORS, TYPE_LETTER, TypeBadge } from '../components/ui'

interface Props {
  meta: Meta
  filters: Filters
  refreshKey: number
  openRegister: (f: Filters) => void
  openDcr: (d: DCR) => void
}

export function DashboardPage({ meta, filters, refreshKey, openRegister, openDcr }: Props) {
  const [data, setData] = useState<Dashboard | null>(null)
  const [drafts, setDrafts] = useState<DCR[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.dashboard(filters).then(setData).catch((e) => setError(String(e)))
    api.list({ ...filters, status: 'Draft' }).then(setDrafts).catch(() => setDrafts([]))
  }, [filters, refreshKey])

  if (error) return <p className="text-sm text-oxblood">Could not load dashboard: {error}</p>
  if (!data) return <p className="text-sm text-charcoal/60">Loading…</p>

  const k = data.kpis
  const tiles: { label: string; value: number; hint?: string; onClick?: () => void; accent?: boolean }[] = [
    { label: 'DCRs', value: k.total, hint: `${k.closed} closed`, onClick: () => openRegister({}) },
    { label: 'Open', value: k.open, onClick: () => openRegister({ status: 'Open' }), accent: true },
    { label: 'Awaiting review', value: k.drafts, hint: 'drafts from e-mail', onClick: () => openRegister({ status: 'Draft' }) },
    { label: 'Projects affected', value: k.projects },
    { label: 'Customers', value: k.customers },
    { label: 'Suppliers', value: k.suppliers },
    { label: 'Critical', value: k.critical, hint: `${k.capa_needed} need CAPA` },
    { label: 'Entries to fix', value: k.with_issues, hint: 'data-quality findings', onClick: () => openRegister({ has_issues: 'true' }) },
  ]
  const totalTyped = data.by_type.reduce((a, t) => a + t.count, 0) || 1

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
        {tiles.map((t) => {
          const Tag = t.onClick ? 'button' : 'div'
          return (
            <Tag
              key={t.label}
              onClick={t.onClick}
              className={`rounded-lg border bg-white px-4 py-3 text-left ${
                t.onClick ? 'cursor-pointer hover:border-oxblood/60' : ''
              } ${t.accent ? 'border-oxblood/40' : 'border-cool-steel/40'}`}
            >
              <div className="text-xs font-medium text-charcoal/70">{t.label}</div>
              <div className={`mt-1 font-heading text-2xl ${t.accent ? 'text-oxblood' : 'text-charcoal'}`}>{t.value}</div>
              {t.hint && <div className="mt-0.5 text-[11px] text-charcoal/60">{t.hint}</div>}
            </Tag>
          )
        })}
      </div>

      <Card title="Incidents by type">
        <div className="mb-4 flex h-3 gap-[2px] overflow-hidden rounded">
          {data.by_type
            .filter((t) => t.count)
            .map((t) => (
              <span
                key={t.name}
                title={`${t.name}: ${t.count}`}
                style={{ flexGrow: t.count, background: TYPE_COLORS[t.name] }}
              />
            ))}
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {data.by_type.map((t) => (
            <button
              key={t.name}
              type="button"
              onClick={() => openRegister({ type: t.name === 'Not set' ? undefined : t.name })}
              className="flex items-center gap-3 rounded-md border border-cool-steel/30 px-3 py-2.5 text-left hover:border-oxblood/50"
            >
              <span
                className="inline-flex h-9 min-w-9 items-center justify-center rounded-md px-1.5 text-sm font-bold text-white"
                style={{ background: TYPE_COLORS[t.name] }}
              >
                {TYPE_LETTER[t.name]}
              </span>
              <span>
                <span className="block font-heading text-xl text-charcoal">{t.count}</span>
                <span className="block text-xs text-charcoal/70">
                  {t.name} · {Math.round((t.count / totalTyped) * 100)}%
                </span>
              </span>
            </button>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="DCRs per month" className="lg:col-span-2">
          <TrendChart data={data.trend} types={[...meta.types, 'Not set']} />
        </Card>
        <Card
          title="Awaiting QA review"
          action={
            drafts.length > 0 && (
              <button className="text-xs font-medium text-oxblood hover:underline" onClick={() => openRegister({ status: 'Draft' })}>
                View all
              </button>
            )
          }
        >
          {drafts.length === 0 ? (
            <p className="text-sm text-charcoal/60">No drafts. New DCR e-mails show up here.</p>
          ) : (
            <ul className="divide-y divide-cool-steel/30">
              {drafts.slice(0, 6).map((d) => (
                <li key={d.id}>
                  <button className="w-full py-2.5 text-left hover:bg-cool-steel/10" onClick={() => openDcr(d)}>
                    <div className="flex items-center justify-between gap-2">
                      <TypeBadge type={d.type} />
                      <span className="text-[11px] text-charcoal/60">{formatDate(d.occurred_on)}</span>
                    </div>
                    <div className="mt-1 truncate text-sm text-charcoal">{d.source_emails[0]?.subject}</div>
                    <div className="truncate text-xs text-charcoal/60">
                      {[d.project, d.customer].filter(Boolean).join(' · ') || 'Project/customer not identified'}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Top customers">
          <PartyBars data={data.top_customers} types={meta.types} onSelect={(n) => openRegister({ search: n })} />
        </Card>
        <Card title="Top suppliers">
          <PartyBars data={data.top_suppliers} types={meta.types} onSelect={(n) => openRegister({ search: n })} />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Where issues happen — category × responsible party" className="lg:col-span-2">
          <Matrix matrix={data.matrix} parties={meta.responsible_parties} />
        </Card>
        <Card title="Data-quality findings">
          {data.quality_issues.length === 0 ? (
            <p className="text-sm text-charcoal/60">No findings — all entries complete.</p>
          ) : (
            <ul className="space-y-2">
              {data.quality_issues.map((q) => (
                <li key={q.issue} className="flex items-start justify-between gap-3 text-sm">
                  <span className="text-charcoal">{q.issue}</span>
                  <span className="shrink-0 rounded bg-oxblood/10 px-1.5 text-xs font-semibold tabular-nums text-oxblood">
                    {q.count}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <button
            className="mt-4 text-xs font-medium text-oxblood hover:underline"
            onClick={() => openRegister({ has_issues: 'true' })}
          >
            Review entries with findings →
          </button>
        </Card>
      </div>
    </div>
  )
}
