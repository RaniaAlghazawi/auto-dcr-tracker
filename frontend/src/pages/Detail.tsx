import { useEffect, useState } from 'react'
import { api, type DCR, type DcrPatch, type EditableField, type Meta } from '../api'
import { EntryFields, entryFields } from '../EntryFields'
import { BackLink, CriticalBadge, daysOpen, fmtLong, isOpen, show, StatusBadge, TypeBadge } from '../ui'

interface Props {
  record: DCR
  meta: Meta
  backLabel: string
  onBack: () => void
  onSaved: (r: DCR) => void
}

const toPatch = (r: DCR, meta: Meta): DcrPatch =>
  Object.fromEntries(entryFields(meta).map((f) => [f.key, r[f.key] ?? ''])) as DcrPatch

export function Detail({ record: r, meta, backLabel, onBack, onSaved }: Props) {
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState<DcrPatch>(() => toPatch(r, meta))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setValues(toPatch(r, meta))
    setEditing(false)
    setError(null)
  }, [r, meta])

  const changed = (Object.keys(values) as EditableField[]).filter((k) => (values[k] ?? '') !== (r[k] ?? ''))

  async function save(): Promise<DCR | null> {
    if (!changed.length) return r
    const patch = Object.fromEntries(changed.map((k) => [k, values[k] || null])) as DcrPatch
    return api.update(r.id, patch)
  }

  async function run(action: () => Promise<DCR | null>) {
    setBusy(true)
    setError(null)
    try {
      const updated = await action()
      if (updated) onSaved(updated)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const days = isOpen(r) ? daysOpen(r) : null
  const fields: { label: string; value: string; wide?: boolean }[] = [
    { label: 'Occurred on', value: fmtLong(r.occurred_on) },
    days !== null ? { label: 'Days open', value: `${days} days` } : { label: 'Closure date', value: fmtLong(r.closure_date) },
    { label: 'Financial impact', value: show(r.financial_impact) },
    { label: 'Customer', value: show(r.customer) },
    { label: 'Supplier', value: show(r.supplier) },
    { label: 'Project', value: show(r.project) },
    {
      label: 'Responsible party',
      value: r.responsible_party_name && r.responsible_party_name !== 'N/A'
        ? `${show(r.responsible_party)} — ${r.responsible_party_name}`
        : show(r.responsible_party),
    },
    { label: 'Category', value: show(r.category) },
    { label: 'AMEX office', value: show(r.amex_office) },
    { label: 'Description of the issue', value: show(r.description), wide: true },
    { label: 'Root cause', value: show(r.root_cause), wide: true },
    ...(r.capa_needed === 'Y'
      ? [
          { label: 'CAPA plan', value: show(r.capa_plan), wide: true },
          { label: 'Actions', value: show(r.actions), wide: true },
        ]
      : [{ label: 'Actions taken', value: show(r.actions_taken), wide: true }]),
  ]

  const emails = r.source_emails.length
  return (
    <section className="view">
      <BackLink label={backLabel} onClick={onBack} />

      <div className="card">
        <div className="detail-header">
          <div>
            <div className="detail-header__id mono">{r.tracking_number}</div>
            <div className="detail-header__badges">
              <TypeBadge type={r.type} />
              <CriticalBadge r={r} />
              <StatusBadge r={r} />
              {r.source === 'email' && (
                <span className={`tag${r.extraction_method === 'claude' ? ' is-ai' : ''}`}>
                  {r.extraction_method === 'claude' ? 'Filled by AI' : 'Filled by rules'} from {emails} e-mail{emails === 1 ? '' : 's'}
                </span>
              )}
            </div>
            <div className="detail-header__sub">
              Project {show(r.project)} · Entered by {show(r.entered_by)} · {show(r.amex_office)} office · Pharma product:{' '}
              {r.pharma === 'Y' ? 'Yes' : r.pharma === 'N' ? 'No' : '—'}
              {r.excel_row ? ` · Excel row ${r.excel_row}` : ''}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            {!editing && (
              <button className="btn-secondary" onClick={() => setEditing(true)}>
                Edit
              </button>
            )}
          </div>
        </div>

        {editing ? (
          <>
            <EntryFields meta={meta} values={values} onChange={setValues} />
            <div className="form-actions" style={{ borderTop: '1px solid var(--border)' }}>
              {error && <span className="error-note">{error}</span>}
              <button
                className="btn-secondary"
                onClick={() => {
                  setValues(toPatch(r, meta))
                  setEditing(false)
                }}
              >
                Cancel
              </button>
              <button className="btn-primary" disabled={busy || !changed.length} onClick={() => run(save)}>
                {busy ? 'Saving…' : 'Save to Excel'}
              </button>
            </div>
          </>
        ) : (
          <div className="detail-grid">
            {fields.map((f) => (
              <div key={f.label} className={`detail-field${f.wide ? ' detail-field--wide' : ''}`}>
                <div className="detail-field__label">{f.label}</div>
                <div className="detail-field__value">{f.value}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {(r.requested_actions || r.issues.length > 0) && (
        <div className="card placeholder-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {r.requested_actions && (
            <div className="notice">
              <b>Requested by the sender:</b> {r.requested_actions}
            </div>
          )}
          {r.issues.length > 0 && (
            <div className="notice is-critical">
              <b>Completeness check against SOP 5-A1</b>
              <ul>
                {r.issues.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="card placeholder-card">
        <div className="placeholder-card__title">
          Source e-mails
          <span className="tag">{emails ? `${emails} linked` : 'Not tracked in Excel'}</span>
        </div>
        {emails === 0 ? (
          <div className="empty-note">No e-mails linked. Entries imported from the Excel tracker or created manually have no source e-mails.</div>
        ) : (
          r.source_emails.map((e, i) => (
            <details key={e.message_id} className="email" open={i === emails - 1 && emails < 3}>
              <summary>
                {e.subject}
                <span className="email__meta">
                  {e.sender} · {fmtLong(e.date)}
                  {e.attachments.length ? ` · 📎 ${e.attachments.join(', ')}` : ''}
                </span>
              </summary>
              <pre>{e.body}</pre>
            </details>
          ))
        )}
      </div>
    </section>
  )
}
