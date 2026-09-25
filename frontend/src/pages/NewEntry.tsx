import { useEffect, useState, type FormEvent } from 'react'
import { api, type DCR, type DcrPatch, type Meta, type ProjectFolder, type ProjectReading } from '../api'
import { EntryFields } from '../EntryFields'
import { BackLink, CURRENT_USER, fmtLong } from '../ui'

interface Props {
  meta: Meta
  onCancel: () => void
  onCreated: (r: DCR) => void
}

const defaults = (meta: Meta): DcrPatch => ({
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

export function NewEntry({ meta, onCancel, onCreated }: Props) {
  const [values, setValues] = useState<DcrPatch>(() => defaults(meta))
  const [project, setProject] = useState('')
  const [folders, setFolders] = useState<ProjectFolder[]>([])
  const [reading, setReading] = useState<ProjectReading | null>(null)
  const [readBusy, setReadBusy] = useState(false)
  const [readError, setReadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.projects().then(setFolders).catch(() => setFolders([]))
  }, [])

  async function readEmails() {
    const number = project.trim()
    if (!number) return
    setReadBusy(true)
    setReadError(null)
    setReading(null)
    try {
      const r = await api.readProject(number)
      setReading(r)
      // e-mail findings replace the form defaults; who enters the case stays the signed-in user
      setValues({ ...defaults(meta), ...r.fields, project: r.fields.project || number, entered_by: CURRENT_USER.login })
    } catch (e) {
      setReadError(e instanceof Error ? e.message : String(e))
    } finally {
      setReadBusy(false)
    }
  }

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
      onCreated(
        await api.create({
          ...payload,
          ...(reading
            ? {
                source_project: reading.project,
                extraction_method: reading.method,
                requested_actions: reading.requested_actions,
                reported_by_party: reading.reported_by_party,
              }
            : {}),
        }),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="view">
      <BackLink label="Cancel" onClick={onCancel} />

      <div className="card placeholder-card">
        <div className="placeholder-card__title">
          Fill from project e-mails
          <span className={`tag${meta.extractor === 'claude' ? ' is-ai' : ''}`}>
            {meta.extractor === 'claude' ? `AI · ${meta.model}` : 'keyword rules — set CLAUDE_API_KEY'}
          </span>
        </div>
        <div className="chart-card__sub">
          Enter the project number. The e-mails saved in <span className="mono">resources/&lt;project number&gt;/</span> are
          read and the fields below are filled in for you to check.
        </div>
        <form
          className="filter-bar"
          onSubmit={(e) => {
            e.preventDefault()
            readEmails()
          }}
        >
          <div className="filter-field">
            <input
              list="project-folders"
              value={project}
              onChange={(e) => setProject(e.target.value)}
              placeholder="Project number, e.g. 20241189"
              aria-label="Project number"
              style={{ minWidth: 260 }}
              disabled={readBusy}
            />
            <datalist id="project-folders">
              {folders.map((f) => (
                <option key={f.folder} value={f.project}>
                  {f.emails} e-mail{f.emails === 1 ? '' : 's'} · {f.folder}
                </option>
              ))}
            </datalist>
          </div>
          <button type="submit" className="btn-primary" disabled={readBusy || !project.trim()}>
            {readBusy ? 'Reading e-mails…' : 'Read e-mails'}
          </button>
          {readBusy && <span className="chart-card__sub" style={{ margin: 0 }}>This takes 20–60 seconds for long threads.</span>}
        </form>
        {readError && <div className="notice is-critical" style={{ marginTop: 12 }}>{readError}</div>}

        {reading && (
          <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {reading.is_dcr === false && (
              <div className="notice is-critical">
                These e-mails don't look like a deviation, complaint or recall. Check before saving.
              </div>
            )}
            <div className="notice">
              Read <b>{reading.emails.length}</b> e-mail{reading.emails.length === 1 ? '' : 's'} from{' '}
              <span className="mono">{reading.folders.join(', ')}</span> with {reading.method === 'claude' ? 'Claude' : 'keyword rules'}.
              {reading.skipped.length > 0 && <> Skipped {reading.skipped.length} ({[...new Set(reading.skipped.map((s) => s.reason))].join(', ')}).</>}
              {reading.missing_information.length > 0 && (
                <>
                  <br />
                  Not found in the e-mails: {reading.missing_information.join(', ')}.
                </>
              )}
              {reading.requested_actions && (
                <>
                  <br />
                  <b>Requested by the sender:</b> {reading.requested_actions}
                </>
              )}
            </div>
            <details className="email">
              <summary>
                E-mails used
                <span className="email__meta">These will be linked to the new entry.</span>
              </summary>
              <ul className="list">
                {reading.emails.map((m, i) => (
                  <li key={i}>
                    <span className="grow">
                      <span className="title">{m.subject}</span>
                      <span className="sub">
                        {m.sender} · {fmtLong(m.date)}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        )}
      </div>

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
          <button type="submit" className="btn-primary" disabled={busy || readBusy}>
            {busy ? 'Saving…' : 'Save entry'}
          </button>
        </div>
      </form>
    </section>
  )
}
