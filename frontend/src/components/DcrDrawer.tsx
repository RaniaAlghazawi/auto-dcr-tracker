import { useEffect, useState } from 'react'
import { api, type DCR, type Meta } from '../api'
import { formatDate, StatusBadge, TypeBadge } from './ui'

type Field = {
  key: keyof DCR
  label: string
  kind?: 'text' | 'area' | 'date' | 'yn' | 'list'
  options?: string[]
  wide?: boolean
}

interface Props {
  dcr: DCR
  meta: Meta
  onClose: () => void
  onSaved: (d: DCR) => void
}

export function DcrDrawer({ dcr, meta, onClose, onSaved }: Props) {
  const [form, setForm] = useState<DCR>(dcr)
  const [saving, setSaving] = useState(false)
  const [enteredBy, setEnteredBy] = useState(dcr.entered_by ?? '')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setForm(dcr)
    setEnteredBy(dcr.entered_by ?? '')
  }, [dcr])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const fields: Field[] = [
    { key: 'type', label: 'Type D/C/R/S/PIR', kind: 'list', options: meta.types },
    { key: 'critical', label: 'Critical DCR', kind: 'yn' },
    { key: 'occurred_on', label: 'DCR occurred on', kind: 'date' },
    { key: 'amex_office', label: 'AMEX office', kind: 'list', options: meta.offices },
    { key: 'pharma', label: 'Pharma', kind: 'yn' },
    { key: 'project', label: 'Project' },
    { key: 'customer', label: 'Customer' },
    { key: 'supplier', label: 'Supplier' },
    { key: 'freight_forwarder', label: 'Freight forwarder' },
    { key: 'responsible_party', label: 'Responsible party', kind: 'list', options: meta.responsible_parties },
    { key: 'responsible_party_name', label: 'Responsible party name' },
    { key: 'category', label: 'Category', kind: 'list', options: meta.categories },
    { key: 'description', label: 'Description of the issue (what happened)', kind: 'area', wide: true },
    { key: 'root_cause', label: 'Root cause (how / why it happened)', kind: 'area', wide: true },
    { key: 'financial_impact', label: 'Financial impact on AMEX' },
    { key: 'capa_needed', label: 'CAPA report needed', kind: 'yn' },
    { key: 'actions_taken', label: 'Actions taken (when CAPA is not needed)', kind: 'area', wide: true },
    { key: 'capa_plan', label: 'CAPA plan', kind: 'area', wide: true },
    { key: 'actions', label: 'Actions', kind: 'area', wide: true },
    { key: 'closure_date', label: 'Closure date', kind: 'date' },
    { key: 'entered_by', label: 'Entered by' },
  ]

  const dirty = fields.some((f) => (form[f.key] ?? '') !== (dcr[f.key] ?? ''))

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const patch: Record<string, unknown> = {}
      for (const f of fields) if ((form[f.key] ?? '') !== (dcr[f.key] ?? '')) patch[f.key] = form[f.key] ?? ''
      onSaved(await api.update(dcr.id, patch as Partial<DCR>))
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  async function confirm() {
    setSaving(true)
    setError(null)
    try {
      if (dirty) await save()
      onSaved(await api.confirm(dcr.id, enteredBy))
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const input =
    'w-full rounded-md border border-cool-steel/60 bg-white px-2.5 py-1.5 text-sm text-charcoal focus:border-oxblood focus:outline-none'

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-charcoal/30" onClick={onClose}>
      <aside
        className="flex h-full w-full max-w-3xl flex-col bg-brand-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
        aria-label="DCR detail"
      >
        <header className="flex items-start justify-between gap-4 border-b border-cool-steel/40 px-6 py-4">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-xl text-charcoal">{dcr.tracking_number ?? 'New DCR draft'}</h2>
              <TypeBadge type={dcr.type} />
              <StatusBadge status={dcr.status} />
            </div>
            <p className="mt-1 text-xs text-charcoal/60">
              {dcr.source === 'email'
                ? `From ${dcr.source_emails.length} e-mail${dcr.source_emails.length === 1 ? '' : 's'} · extracted by ${
                    dcr.extraction_method === 'claude' ? 'Claude' : 'keyword rules'
                  }${dcr.reported_by_party ? ` · raised by ${dcr.reported_by_party}` : ''}`
                : 'Imported from the DCR tracker workbook'}
            </p>
          </div>
          <button onClick={onClose} className="rounded p-1 text-2xl leading-none text-charcoal/60 hover:text-oxblood" aria-label="Close">
            ×
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          {dcr.issues.length > 0 && (
            <div className="rounded-md border border-oxblood/30 bg-oxblood/5 px-4 py-3">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-oxblood">
                {dcr.issues.length} data-quality finding{dcr.issues.length === 1 ? '' : 's'}
              </div>
              <ul className="list-disc space-y-0.5 pl-5 text-sm text-charcoal">
                {dcr.issues.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
            </div>
          )}

          {dcr.requested_actions && (
            <div className="rounded-md border border-air-force-blue/40 bg-air-force-blue/5 px-4 py-3 text-sm">
              <span className="font-semibold text-air-force-blue">Requested by sender: </span>
              {dcr.requested_actions}
            </div>
          )}

          <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2">
            {fields.map((f) => {
              const value = (form[f.key] as string | null) ?? ''
              const set = (v: string) => setForm({ ...form, [f.key]: v || null })
              return (
                <label key={f.key} className={`flex flex-col gap-1 text-xs font-medium text-charcoal/70 ${f.wide ? 'sm:col-span-2' : ''}`}>
                  {f.label}
                  {f.kind === 'area' ? (
                    <textarea rows={3} className={input} value={value} onChange={(e) => set(e.target.value)} />
                  ) : f.kind === 'list' || f.kind === 'yn' ? (
                    <select className={input} value={value} onChange={(e) => set(e.target.value)}>
                      <option value="">—</option>
                      {(f.kind === 'yn' ? ['Y', 'N'] : f.options ?? []).map((o) => (
                        <option key={o}>{o}</option>
                      ))}
                      {value && !(f.kind === 'yn' ? ['Y', 'N'] : f.options ?? []).includes(value) && (
                        <option value={value}>{value} (not in list)</option>
                      )}
                    </select>
                  ) : f.kind === 'date' && (!value || /^\d{4}-\d{2}-\d{2}$/.test(value)) ? (
                    <input type="date" className={input} value={value} onChange={(e) => set(e.target.value)} />
                  ) : (
                    <input className={input} value={value} onChange={(e) => set(e.target.value)} />
                  )}
                </label>
              )
            })}
          </div>

          {dcr.source_emails.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm text-charcoal">Source e-mails</h3>
              <div className="space-y-3">
                {dcr.source_emails.map((e) => (
                  <details key={e.message_id} className="rounded-md border border-cool-steel/40 bg-white" open={dcr.source_emails.length === 1}>
                    <summary className="cursor-pointer px-4 py-2 text-sm">
                      <span className="font-medium text-charcoal">{e.subject}</span>
                      <span className="block text-xs text-charcoal/60">
                        {e.sender} · {formatDate(e.date)}
                      </span>
                    </summary>
                    <pre className="whitespace-pre-wrap border-t border-cool-steel/30 px-4 py-3 font-body text-xs leading-relaxed text-charcoal">
                      {e.body}
                    </pre>
                  </details>
                ))}
              </div>
            </section>
          )}
        </div>

        <footer className="flex flex-wrap items-center gap-3 border-t border-cool-steel/40 px-6 py-3">
          {error && <span className="text-xs text-oxblood">{error}</span>}
          {dcr.status === 'Draft' && (
            <label className="flex items-center gap-2 text-xs text-charcoal/70">
              Entered by
              <input
                className="w-32 rounded-md border border-cool-steel/60 px-2 py-1 text-sm"
                placeholder="nsurname"
                value={enteredBy}
                onChange={(e) => setEnteredBy(e.target.value)}
              />
            </label>
          )}
          <div className="ml-auto flex gap-2">
            <button
              onClick={save}
              disabled={!dirty || saving}
              className="rounded-md border border-charcoal/40 px-4 py-1.5 text-sm text-charcoal hover:border-charcoal disabled:opacity-40"
            >
              Save changes
            </button>
            {dcr.status === 'Draft' && (
              <button
                onClick={confirm}
                disabled={saving || !enteredBy.trim()}
                title={enteredBy.trim() ? '' : 'Enter your initials/surname first'}
                className="rounded-md bg-oxblood px-4 py-1.5 text-sm font-medium text-white hover:bg-oxblood-dark disabled:opacity-40"
              >
                Confirm &amp; add to tracker
              </button>
            )}
          </div>
        </footer>
      </aside>
    </div>
  )
}
