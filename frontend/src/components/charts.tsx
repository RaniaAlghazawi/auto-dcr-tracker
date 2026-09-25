import { useState } from 'react'
import type { Dashboard, RankedParty } from '../api'
import { TYPE_COLORS, TypeLegend } from './ui'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function monthLabel(ym: string) {
  const [y, m] = ym.split('-')
  return `${MONTHS[Number(m) - 1]} ${y.slice(2)}`
}

/** Monthly DCR count, stacked by type. */
export function TrendChart({ data, types }: { data: Dashboard['trend']; types: string[] }) {
  const [hover, setHover] = useState<number | null>(null)
  if (!data.length) return <p className="text-sm text-charcoal/60">No dated entries for this selection.</p>

  const W = 720
  const H = 220
  const pad = { l: 28, r: 8, t: 10, b: 26 }
  const max = Math.max(...data.map((d) => d.total), 1)
  const step = Math.ceil(max / 4)
  const top = step * 4
  const bw = (W - pad.l - pad.r) / data.length
  const barW = Math.max(3, Math.min(28, bw - 3))
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / top)
  const labelEvery = Math.ceil(data.length / 12)
  const h = hover !== null ? data[hover] : null

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="DCRs per month by type">
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={y(i * step)} y2={y(i * step)} stroke="#9db2bf" strokeOpacity={i ? 0.35 : 0.8} />
            <text x={pad.l - 6} y={y(i * step) + 3} textAnchor="end" fontSize="10" fill="#575656">
              {i * step}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = pad.l + i * bw + (bw - barW) / 2
          let acc = 0
          const segs = types.filter((t) => d.by_type[t])
          return (
            <g key={d.month} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={pad.l + i * bw} y={pad.t} width={bw} height={H - pad.t - pad.b} fill="transparent" />
              {hover === i && (
                <rect x={pad.l + i * bw} y={pad.t} width={bw} height={H - pad.t - pad.b} fill="#9db2bf" opacity={0.15} />
              )}
              {segs.map((t, si) => {
                const v = d.by_type[t]
                const y0 = y(acc)
                acc += v
                const y1 = y(acc)
                const isTop = si === segs.length - 1
                // 2px surface gap between stacked segments; round only the top data-end
                const hgt = Math.max(0, y0 - y1 - (si > 0 ? 2 : 0))
                return (
                  <path
                    key={t}
                    d={roundedTop(x, y1, barW, hgt, isTop ? Math.min(3, barW / 2, hgt) : 0)}
                    fill={TYPE_COLORS[t]}
                  />
                )
              })}
              {i % labelEvery === 0 && (
                <text x={pad.l + i * bw + bw / 2} y={H - 8} textAnchor="middle" fontSize="10" fill="#575656">
                  {monthLabel(d.month)}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      {h && hover !== null && (
        <div
          className="pointer-events-none absolute top-0 z-10 min-w-36 rounded-md border border-cool-steel/50 bg-white px-3 py-2 text-xs shadow-md"
          style={{ left: `min(calc(${((hover + 0.5) / data.length) * 100}% + 12px), calc(100% - 10rem))` }}
        >
          <div className="mb-1 font-semibold text-charcoal">
            {monthLabel(h.month)} · {h.total} DCR{h.total === 1 ? '' : 's'}
          </div>
          {types
            .filter((t) => h.by_type[t])
            .map((t) => (
              <div key={t} className="flex items-center justify-between gap-4 text-charcoal/80">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm" style={{ background: TYPE_COLORS[t] }} />
                  {t}
                </span>
                <span className="tabular-nums text-charcoal">{h.by_type[t]}</span>
              </div>
            ))}
        </div>
      )}
      <div className="mt-2">
        <TypeLegend types={types.filter((t) => data.some((d) => d.by_type[t]))} />
      </div>
    </div>
  )
}

function roundedTop(x: number, y: number, w: number, h: number, r: number) {
  if (h <= 0) return ''
  if (r <= 0) return `M${x},${y}h${w}v${h}h${-w}Z`
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`
}

/** Ranked horizontal bars (customers / suppliers), stacked by type. */
export function PartyBars({
  data,
  types,
  onSelect,
}: {
  data: RankedParty[]
  types: string[]
  onSelect?: (name: string) => void
}) {
  if (!data.length) return <p className="text-sm text-charcoal/60">Nothing recorded.</p>
  const max = Math.max(...data.map((d) => d.total), 1)
  return (
    <ul className="space-y-2.5">
      {data.map((d) => (
        <li key={d.name}>
          <button
            type="button"
            onClick={() => onSelect?.(d.name)}
            className="group w-full text-left"
            title={types
              .filter((t) => d.by_type[t])
              .map((t) => `${t}: ${d.by_type[t]}`)
              .join('\n')}
          >
            <div className="mb-1 flex justify-between text-xs">
              <span className="truncate text-charcoal group-hover:text-oxblood">{d.name}</span>
              <span className="ml-2 tabular-nums text-charcoal">{d.total}</span>
            </div>
            <div className="flex h-2.5 gap-[2px] overflow-hidden rounded" style={{ width: `${(d.total / max) * 100}%` }}>
              {types
                .filter((t) => d.by_type[t])
                .map((t) => (
                  <span key={t} className="h-full" style={{ flexGrow: d.by_type[t], background: TYPE_COLORS[t] }} />
                ))}
            </div>
          </button>
        </li>
      ))}
    </ul>
  )
}

/** Category x responsible party — mirrors the "Occurence" pivot of the tracker workbook. */
export function Matrix({ matrix, parties }: { matrix: Dashboard['matrix']; parties: string[] }) {
  const rows = Object.entries(matrix)
    .map(([cat, cells]) => ({ cat, cells, total: Object.values(cells).reduce((a, b) => a + b, 0) }))
    .sort((a, b) => b.total - a.total)
  const cols = [...parties, ...(rows.some((r) => r.cells['Not set']) ? ['Not set'] : [])]
  const max = Math.max(1, ...rows.flatMap((r) => Object.values(r.cells)))
  const colTotals = cols.map((c) => rows.reduce((a, r) => a + (r.cells[c] ?? 0), 0))

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-separate border-spacing-[2px] text-xs">
        <thead>
          <tr>
            <th className="px-2 py-1 text-left font-medium text-charcoal/70">Category \ Responsible</th>
            {cols.map((c) => (
              <th key={c} className="px-2 py-1 text-center font-medium text-charcoal/70">
                {c}
              </th>
            ))}
            <th className="px-2 py-1 text-center font-semibold text-charcoal">Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.cat}>
              <td className="whitespace-nowrap px-2 py-1.5 text-charcoal">{r.cat}</td>
              {cols.map((c) => {
                const v = r.cells[c] ?? 0
                const a = v ? 0.12 + 0.78 * (v / max) : 0
                return (
                  <td
                    key={c}
                    title={`${r.cat} · ${c}: ${v}`}
                    className="rounded px-2 py-1.5 text-center tabular-nums"
                    style={{ background: v ? `rgba(148,22,18,${a})` : '#f4f5f6', color: a > 0.5 ? '#fff' : '#575656' }}
                  >
                    {v || ''}
                  </td>
                )
              })}
              <td className="px-2 py-1.5 text-center font-semibold tabular-nums text-charcoal">{r.total}</td>
            </tr>
          ))}
          <tr>
            <td className="px-2 py-1.5 font-semibold text-charcoal">Total</td>
            {colTotals.map((t, i) => (
              <td key={cols[i]} className="px-2 py-1.5 text-center font-semibold tabular-nums text-charcoal">
                {t}
              </td>
            ))}
            <td className="px-2 py-1.5 text-center font-semibold tabular-nums text-charcoal">
              {colTotals.reduce((a, b) => a + b, 0)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
