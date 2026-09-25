import type { DcrPatch, EditableField, Meta } from './api'
import { TYPE_LABEL } from './ui'

interface FieldDef {
  key: EditableField
  label: string
  kind: 'select' | 'date' | 'text' | 'textarea'
  options?: { value: string; label: string }[]
  wide?: boolean
  placeholder?: string
  required?: boolean
  group?: 'capa' | 'noCapa'
}

const opts = (values: string[], labels: Record<string, string> = {}) =>
  values.map((v) => ({ value: v, label: labels[v] ?? v }))

/** Fields of the "New DCR entry" form in the UI mockup (tracker columns B–U). */
export function entryFields(meta: Meta): FieldDef[] {
  return [
    { key: 'type', label: 'Type', kind: 'select', options: opts(meta.types, TYPE_LABEL) },
    { key: 'category', label: 'Category', kind: 'select', options: opts(meta.categories) },
    { key: 'critical', label: 'Critical DCR', kind: 'select', options: opts(['N/A', 'Y', 'N']) },
    { key: 'occurred_on', label: 'DCR occurred on', kind: 'date' },
    { key: 'amex_office', label: 'AMEX office', kind: 'select', options: opts(meta.offices) },
    { key: 'pharma', label: 'Pharma', kind: 'select', options: opts(['N', 'Y']) },
    { key: 'supplier', label: 'Supplier', kind: 'text', placeholder: 'Supplier name' },
    { key: 'customer', label: 'Customer', kind: 'text', placeholder: 'Customer name' },
    { key: 'project', label: 'Project', kind: 'text', placeholder: 'Project / PO number' },
    { key: 'responsible_party', label: 'Responsible party', kind: 'select', options: opts(['N/A', ...meta.responsible_parties]) },
    { key: 'responsible_party_name', label: 'Specify the name of the responsible party', kind: 'text', placeholder: 'Company name (if different from supplier)' },
    { key: 'entered_by', label: 'Entered by', kind: 'text', placeholder: 'nsurname' },
    { key: 'description', label: 'Description of the issue', kind: 'textarea', wide: true, placeholder: 'What happened?', required: true },
    { key: 'root_cause', label: 'Root cause of the issue', kind: 'textarea', wide: true, placeholder: 'How / why the issue happened' },
    { key: 'financial_impact', label: 'Financial impact', kind: 'text', placeholder: 'e.g. 1.200 € or — €' },
    { key: 'capa_needed', label: 'CAPA report needed', kind: 'select', options: opts(['N', 'Y']) },
    { key: 'closure_date', label: 'Closure date (leave blank if still open)', kind: 'date' },
    { key: 'actions_taken', label: 'Actions taken (when CAPA not needed)', kind: 'textarea', wide: true, group: 'noCapa' },
    { key: 'capa_plan', label: 'CAPA plan', kind: 'textarea', wide: true, group: 'capa' },
    { key: 'actions', label: 'Actions', kind: 'textarea', wide: true, group: 'capa' },
  ]
}

interface Props {
  meta: Meta
  values: DcrPatch
  onChange: (values: DcrPatch) => void
}

export function EntryFields({ meta, values, onChange }: Props) {
  const capa = values.capa_needed === 'Y'
  return (
    <div className="detail-grid">
      {entryFields(meta)
        .filter((f) => !f.group || (f.group === 'capa') === capa)
        .map((f) => {
          const id = `ne-${f.key}`
          const value = values[f.key] ?? ''
          const set = (v: string) => onChange({ ...values, [f.key]: v })
          let input
          if (f.kind === 'select') {
            const known = f.options!.some((o) => o.value === value)
            input = (
              <select className="field-input" id={id} value={value} onChange={(e) => set(e.target.value)}>
                {!value && <option value="">—</option>}
                {!known && value && <option value={value}>{value} (not in list)</option>}
                {f.options!.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            )
          } else if (f.kind === 'textarea') {
            input = (
              <textarea className="field-input" id={id} value={value} placeholder={f.placeholder} required={f.required} onChange={(e) => set(e.target.value)} />
            )
          } else if (f.kind === 'date' && (!value || /^\d{4}-\d{2}-\d{2}$/.test(value))) {
            input = <input className="field-input tnum" type="date" id={id} value={value} onChange={(e) => set(e.target.value)} />
          } else {
            // free-text dates from the old tracker stay editable as text
            input = <input className="field-input" type="text" id={id} value={value} placeholder={f.placeholder} onChange={(e) => set(e.target.value)} />
          }
          return (
            <div key={f.key} className={`detail-field${f.wide ? ' detail-field--wide' : ''}`}>
              <label className="detail-field__label" htmlFor={id}>
                {f.label}
              </label>
              {input}
            </div>
          )
        })}
    </div>
  )
}
