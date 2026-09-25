import { useState, useEffect, type FormEvent } from 'react'
import { api } from '../api'
import { BackLink } from '../ui'

interface ProjectSuggestion {
  number: string
  status: 'new' | 'draft' | 'recorded'
  dcr_number: string | null
}

interface WizardStartResponse {
  suggestions: ProjectSuggestion[]
  engine: string
  pending_drafts: number
}

export function Wizard({ onCancel, onCreated }: { onCancel: () => void; onCreated: (id: string) => void }) {
  const [suggestions, setSuggestions] = useState<ProjectSuggestion[]>([])
  const [engine, setEngine] = useState<string>('')
  const [project, setProject] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [force, setForce] = useState(false)

  useEffect(() => {
    api.wizardStart().then(data => {
      setSuggestions(data.suggestions)
      setEngine(data.engine)
    }).catch(err => setError(err instanceof Error ? err.message : String(err)))
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!project.trim()) {
      setError('Enter the project number this DCR relates to.')
      return
    }

    setBusy(true)
    setError(null)

    try {
      const response = await api.wizardSubmit(project.trim(), force)
      if (response.result === 'started') {
        // Navigate to working page
        window.location.hash = `#wizard/working/${project}`
      } else if (response.result === 'created' || response.result === 'drafted') {
        onCreated(response.id)
      } else if (response.result === 'existing_draft' || response.result === 'existing_record') {
        setError(response.message)
        if (response.dcr_id) {
          onCreated(response.dcr_id)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  function selectProject(number: string) {
    setProject(number)
    setForce(true)
  }

  return (
    <section className="view">
      <BackLink label="Cancel" onClick={onCancel} />
      <div className="card">
        <h1>New DCR entry</h1>
        <p className="help">
          Give the project number. The tracker reads that project's emails and fills
          in the entry for you — type, category, parties, dates, what happened and
          the root cause. You check it and approve.
        </p>

        {engine === 'rule' && (
          <div className="notice is-warn">
            <strong>No reader available.</strong> Neither an API key nor the Claude Code
            CLI was found, so fields cannot be filled automatically. The entry will be
            created blank.
          </div>
        )}

        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label htmlFor="project">Project number</label>
            <input
              type="text"
              id="project"
              value={project}
              onChange={e => setProject(e.target.value)}
              placeholder="e.g. 20241189"
              list="known-projects"
              autoFocus
              required
              autoComplete="off"
            />
            <datalist id="known-projects">
              {suggestions.map(p => (
                <option key={p.number} value={p.number} />
              ))}
            </datalist>
          </div>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Starting…' : 'Read the emails & complete the entry'}
          </button>
        </form>

        {error && <span className="error-note">{error}</span>}
      </div>

      {suggestions.length > 0 && (
        <div className="card" style={{ marginTop: 14 }}>
          <h2>Projects with correspondence on file</h2>
          <div className="project-grid">
            {suggestions.map(p => (
              <button
                key={p.number}
                type="button"
                onClick={() => selectProject(p.number)}
                className={`btn-secondary project-card ${p.status !== 'new' ? 'is-taken' : ''}`}
              >
                <span className="project-number">{p.number}</span>
                <span className="project-status">
                  {p.status === 'new' ? 'No DCR yet' : p.status === 'draft' ? 'Draft waiting' : p.dcr_number}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

export function WizardWorking({ project, onCancel }: { project: string; onCancel: () => void }) {
  const [info, setInfo] = useState<any>(null)
  const [status, setStatus] = useState<string>('')
  const [percent, setPercent] = useState(0)
  const [nextUrl, setNextUrl] = useState<string | null>(null)

  useEffect(() => {
    // Load initial info
    api.wizardWorking(project).then(data => {
      setInfo(data)
    }).catch(console.error)

    // Poll for status
    const interval = setInterval(() => {
      api.wizardWorkingStatus(project).then(data => {
        setStatus(data.current || (data.running ? 'Reading the correspondence…' : 'Finished'))
        setPercent(data.percent || 0)
        if (!data.running && data.next_url) {
          setNextUrl(data.next_url)
          clearInterval(interval)
          window.location.href = data.next_url
        }
      }).catch(console.error)
    }, 2000)

    return () => clearInterval(interval)
  }, [project])

  return (
    <section className="view">
      <BackLink label="Cancel" onClick={onCancel} />
      <div className="card">
        <h1>Reading project {project}</h1>
        <p className="help">
          Going through {info?.info?.email_count || 0} email{info?.info?.email_count === 1 ? '' : 's'}
          {info?.info?.thread_count > 1 ? ` across ${info.info.thread_count} separate chains` : ''}
          and filling in the DCR entry.
        </p>

        <div style={{ padding: 20, textAlign: 'center' }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>{status}</div>
          <div style={{ height: 8, background: '#e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ height: '100%', background: '#3b82f6', width: `${percent}%`, transition: 'width 0.3s' }} />
          </div>
          <p className="help" style={{ marginTop: 12 }}>
            This takes a minute or two — it is reading every email properly, not
            scanning for keywords. The page moves on by itself when it is done.
          </p>
          {info?.info?.parties && info.info.parties.length > 0 && (
            <p className="help">
              Companies in this correspondence: {info.info.parties.map((p: any) => p.name).join(', ')}
            </p>
          )}
        </div>
      </div>
    </section>
  )
}

export function WizardNotADCR({ project, onCancel, onCreateAnyway }: {
  project: string
  onCancel: () => void
  onCreateAnyway: () => void
}) {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    api.wizardNotADCR(project).then(setData).catch(console.error)
  }, [project])

  return (
    <section className="view">
      <BackLink label="Cancel" onClick={onCancel} />
      <div className="card">
        <h1>No quality issue found in project {project}</h1>
        <p className="help">
          {data?.emails || 0} email{data?.emails === 1 ? '' : 's'} were read and none of them
          describes a deviation, complaint, recall, safety notice or partner issue.
        </p>

        <div style={{ padding: 20 }}>
          <p><strong>Why:</strong> {data?.reason || 'No reason provided'}</p>
          {data?.summary && <p className="help">First subject line: {data.summary}</p>}

          <p className="help" style={{ marginTop: 14 }}>
            If you know this is a DCR anyway — the emails may not tell the whole
            story — create the entry and fill it in yourself.
          </p>

          <div style={{ display: 'flex', gap: 9, marginTop: 12 }}>
            <button className="btn-primary" onClick={onCreateAnyway}>
              Create the entry anyway
            </button>
            <button className="btn-secondary" onClick={onCancel}>
              Try another project
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
