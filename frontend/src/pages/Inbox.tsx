import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type DCR, type IgnoredEmail, type IngestResult, type Meta, type SampleEmail } from '../api'
import { CURRENT_USER, fmtShort, show, TypeBadge } from '../ui'

interface Props {
  meta: Meta
  refreshKey: number
  onChanged: () => void
  openDetail: (r: DCR) => void
  openById: (id: string) => void
}

const RESULT_LABEL: Record<string, string> = {
  added: 'Added to Excel',
  created: 'Draft created',
  updated: 'Draft updated',
  attached: 'Case updated',
  not_dcr: 'Not a DCR',
  duplicate: 'Already done',
  pending: 'Waiting',
  running: 'Analysing…',
  error: 'Error',
}

interface Row {
  name: string
  subject: string
  status: string
  detail?: string
  id?: string
}

export function Inbox({ meta, refreshKey, onChanged, openDetail, openById }: Props) {
  const [drafts, setDrafts] = useState<DCR[]>([])
  const [samples, setSamples] = useState<SampleEmail[]>([])
  const [ignored, setIgnored] = useState<IgnoredEmail[]>([])
  const [autoAdd, setAutoAdd] = useState(true)
  const [rows, setRows] = useState<Row[]>([])
  const [busy, setBusy] = useState(false)
  const [raw, setRaw] = useState('')
  const [error, setError] = useState<string | null>(null)
  const stop = useRef(false)

  const load = useCallback(() => {
    api.drafts().then(setDrafts).catch(() => setDrafts([]))
    api.samples().then(setSamples).catch(() => setSamples([]))
    api.ignored().then(setIgnored).catch(() => setIgnored([]))
  }, [])
  useEffect(load, [load, refreshKey])

  const record = (r: IngestResult, name: string): Row => ({
    name,
    subject: r.subject ?? name,
    status: r.result,
    detail: r.tracking_number ? r.tracking_number : r.method === 'rules' ? 'keyword rules' : undefined,
    id: r.id,
  })

  async function runSamples() {
    const todo = samples.filter((s) => !s.processed)
    if (!todo.length) return
    stop.current = false
    setBusy(true)
    setError(null)
    setRows(todo.map((s) => ({ name: s.name, subject: s.subject, status: 'pending' })))
    for (const [i, s] of todo.entries()) {
      if (stop.current) break
      setRows((prev) => prev.map((r, j) => (j === i ? { ...r, status: 'running' } : r)))
      try {
        const res = await api.ingestSample(s.name, autoAdd, CURRENT_USER.login)
        setRows((prev) => prev.map((r, j) => (j === i ? record(res, s.name) : r)))
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e)
        setRows((prev) => prev.map((r, j) => (j === i ? { ...r, status: 'error', detail: msg } : r)))
        if (msg.includes('locked')) {
          setError(msg)
          break
        }
      }
      onChanged()
    }
    setBusy(false)
    load()
  }

  async function runUpload(files: FileList) {
    setBusy(true)
    setError(null)
    try {
      const res = await api.ingestFiles(files, autoAdd, CURRENT_USER.login)
      setRows((prev) => [...res.map((r) => record(r, r.file ?? '')), ...prev])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
      onChanged()
      load()
    }
  }

  async function runPaste() {
    setBusy(true)
    setError(null)
    try {
      const res = await api.ingestText(raw, autoAdd, CURRENT_USER.login)
      setRows((prev) => [record(res, 'Pasted e-mail'), ...prev])
      setRaw('')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
      onChanged()
      load()
    }
  }

  const done = rows.filter((r) => !['pending', 'running'].includes(r.status)).length
  const unprocessed = samples.filter((s) => !s.processed).length
  const aiLabel = meta.extractor === 'claude' ? `Claude (${meta.model})` : 'keyword rules — set CLAUDE_API_KEY in backend/.env'

  return (
    <section className="view">
      <div className="card" style={{ padding: '14px 18px' }}>
        <div className="filter-bar" style={{ justifyContent: 'space-between' }}>
          <div style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>
            <span className={`tag${meta.extractor === 'claude' ? ' is-ai' : ''}`}>AI</span> E-mails are analysed by{' '}
            <b>{aiLabel}</b> and written to <b>{meta.tracker_file}</b>.
          </div>
          <label className="check">
            <input type="checkbox" checked={autoAdd} onChange={(e) => setAutoAdd(e.target.checked)} />
            Add new DCRs straight to Excel (otherwise they wait for review)
          </label>
        </div>
      </div>

      {error && <div className="notice is-critical">{error}</div>}

      <div className="inbox-grid">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card table-card">
            <div className="table-card__head">
              <div>
                <div className="section-title" style={{ margin: 0 }}>
                  E-mail files
                </div>
                <span className="chart-card__sub" style={{ margin: 0 }}>
                  {samples.length} e-mail files in resources/ · {unprocessed} not analysed yet
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {busy && (
                  <button className="btn-secondary" onClick={() => (stop.current = true)}>
                    Stop
                  </button>
                )}
                <button className="btn-primary" disabled={busy || unprocessed === 0} onClick={runSamples}>
                  {busy ? `Analysing ${done}/${rows.length}…` : `Analyse ${unprocessed} e-mail${unprocessed === 1 ? '' : 's'}`}
                </button>
              </div>
            </div>
            {rows.length > 0 && (
              <div className="progress" aria-hidden="true">
                <span style={{ width: `${(done / rows.length) * 100}%` }} />
              </div>
            )}
            <ul className="list">
              {(rows.length ? rows : samples.map((s) => ({ name: s.name, subject: s.subject, status: s.processed ? 'duplicate' : 'pending' }) as Row)).map((r) => (
                <li key={r.name + r.status}>
                  <span className="grow">
                    <span className="title">{r.subject}</span>
                    <span className="sub mono">{r.name}</span>
                  </span>
                  {r.detail && <span className="sub mono" style={{ maxWidth: 220 }}>{r.detail}</span>}
                  <span className={`result ${r.status}`}>{RESULT_LABEL[r.status] ?? r.status}</span>
                  {r.id && (
                    <button className="link-btn" onClick={() => openById(r.id!)}>
                      Open
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>

          <div className="card placeholder-card">
            <div className="placeholder-card__title">Analyse your own e-mails</div>
            <div className="chart-card__sub">Upload Outlook .msg or .eml files, or paste an e-mail with its headers.</div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <label className="btn-secondary" style={{ cursor: busy ? 'not-allowed' : 'pointer' }}>
                Upload .msg / .eml
                <input
                  type="file"
                  multiple
                  accept=".msg,.eml,.txt,message/rfc822,application/vnd.ms-outlook"
                  hidden
                  disabled={busy}
                  onChange={(e) => {
                    if (e.target.files?.length) runUpload(e.target.files)
                    e.target.value = ''
                  }}
                />
              </label>
            </div>
            <textarea
              className="field-input mono"
              style={{ minHeight: 120, fontSize: 12 }}
              placeholder={'From: someone@customer.org\nSubject: Complaint – damaged goods, project 20260412\n\nDear team, …'}
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
            />
            <div className="form-actions" style={{ padding: '10px 0 0' }}>
              <button className="btn-primary" disabled={busy || !raw.trim()} onClick={runPaste}>
                Analyse pasted e-mail
              </button>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card table-card">
            <div className="table-card__head">
              <div className="section-title" style={{ margin: 0 }}>
                Awaiting review
              </div>
              <span className="chart-card__sub" style={{ margin: 0 }}>
                {drafts.length} draft{drafts.length === 1 ? '' : 's'}
              </span>
            </div>
            <ul className="list">
              {drafts.map((d) => (
                <li key={d.id} style={{ cursor: 'pointer' }} onClick={() => openDetail(d)}>
                  <TypeBadge type={d.type} />
                  <span className="grow">
                    <span className="title">{d.source_emails[0]?.subject ?? show(d.description)}</span>
                    <span className="sub">
                      {[d.customer, d.project, fmtShort(d.occurred_on)].filter(Boolean).join(' · ')}
                    </span>
                  </span>
                  <span className="link-btn">Review</span>
                </li>
              ))}
              {drafts.length === 0 && <li className="cell-muted">No drafts — untick “Add straight to Excel” to review first.</li>}
            </ul>
          </div>

          <div className="card table-card">
            <div className="table-card__head">
              <div className="section-title" style={{ margin: 0 }}>
                Not a DCR
              </div>
              <span className="chart-card__sub" style={{ margin: 0 }}>
                Auto-replies, confirmations, logistics
              </span>
            </div>
            <ul className="list">
              {ignored.map((m) => (
                <li key={m.message_id}>
                  <span className="grow">
                    <span className="title">{m.subject}</span>
                    <span className="sub">
                      {m.sender} · {fmtShort(m.date)}
                    </span>
                  </span>
                </li>
              ))}
              {ignored.length === 0 && <li className="cell-muted">None yet.</li>}
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}
