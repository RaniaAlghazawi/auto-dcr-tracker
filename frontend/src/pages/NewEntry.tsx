import { useState, type FormEvent } from 'react'
import { api, type DCR, type DcrPatch, type Meta } from '../api'
import { EntryFields } from '../EntryFields'
import { BackLink, CURRENT_USER } from '../ui'

interface Props {
  meta: Meta
  onCancel: () => void
  onCreated: (r: DCR) => void
}

/** Manual entry. To fill an entry from a project's e-mails, use "From project" (the wizard). */
export function NewEntry({ meta, onCancel, onCreated }: Props) {
  const [values, setValues] = useState<DcrPatch>({
    type: 'Deviation',
    category: 'Other',
    critical: 'N/A',
    occurred_on: meta.today,
    amex_office: 'Vienna',
    pharma: 'N',
    responsible_party: 'N/A',
    capa_needed: 'N',
    entered_by: CURRENT_USER.login,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      // CAPA plan/actions and "actions taken" are alternatives — only send the visible group
      const payload = { ...values }
      if (payload.capa_needed === 'Y') delete payload.actions_taken
      else {
        delete payload.capa_plan
        delete payload.actions
      }
      onCreated(await api.create(payload))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="view">
      <BackLink label="Cancel" onClick={onCancel} />
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        <div className="card">
          <div className="detail-header">
            <div>
              <div className="detail-header__id mono">{meta.next_tracking_number} (new)</div>
              <div className="detail-header__sub">
                DCR number is assigned automatically on save · written as a new row to {meta.tracker_file}
              </div>
            </div>
          </div>
          <EntryFields meta={meta} values={values} onChange={setValues} />
        </div>
        <div className="card form-actions">
          {error && <span className="error-note">{error}</span>}
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Saving…' : 'Save entry'}
          </button>
        </div>
      </form>
    </section>
  )
}
