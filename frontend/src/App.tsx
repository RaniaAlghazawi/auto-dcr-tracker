import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, type DCR, type Meta, type RecordFilters } from './api'
import { Dashboard } from './pages/Dashboard'
import { Detail } from './pages/Detail'
import { NewEntry } from './pages/NewEntry'
import { Records } from './pages/Records'
import { Wizard, WizardWorking, WizardNotADCR } from './pages/Wizard'
import { CURRENT_USER } from './ui'

type View = 'dashboard' | 'records' | 'detail' | 'new' | 'wizard' | 'wizard-working' | 'wizard-not-dcr'
type ListView = 'dashboard' | 'records'
const LIST_VIEWS: ListView[] = ['dashboard', 'records']

/** View from the URL hash (#records, #wizard, #wizard/working/<project>), so reloads and browser back keep it. */
const viewFromHash = (): View => {
  const h = window.location.hash.slice(1)
  if (h.startsWith('wizard/working/')) return 'wizard-working'
  if (h.startsWith('wizard/not-a-dcr/')) return 'wizard-not-dcr'
  if (h === 'wizard') return 'wizard'
  const listView = h as ListView
  return LIST_VIEWS.includes(listView) ? listView : 'dashboard'
}

/** Project number in #wizard/working/<project> or #wizard/not-a-dcr/<project>. */
const wizardProjectFromHash = (): string | null => {
  const m = window.location.hash.match(/^#wizard\/(?:working|not-a-dcr)\/(.+)$/)
  return m ? decodeURIComponent(m[1]) : null
}

const listViewOf = (v: View): ListView | null => (LIST_VIEWS.includes(v as ListView) ? (v as ListView) : null)

function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [offline, setOffline] = useState<string | null>(null)
  const [view, setView] = useState<View>(viewFromHash)
  const [from, setFrom] = useState<ListView>(() => listViewOf(viewFromHash()) ?? 'dashboard') // where "back" goes
  const [selected, setSelected] = useState<DCR | null>(null)
  const [filters, setFilters] = useState<RecordFilters>({})
  const [refreshKey, setRefreshKey] = useState(0)
  const [wizardProject, setWizardProject] = useState<string | null>(wizardProjectFromHash)

  const refresh = useCallback(() => {
    api
      .meta()
      .then((m) => {
        setMeta(m)
        setOffline(null)
      })
      .catch((e) => setOffline(e instanceof Error ? e.message : String(e)))
    setRefreshKey((k) => k + 1)
  }, [])

  useEffect(refresh, [refresh])

  useEffect(() => {
    const onHash = () => {
      const v = viewFromHash()
      const list = listViewOf(v)
      if (list) setFrom(list)
      setView(v)
      setWizardProject(wizardProjectFromHash())
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (v: View) => {
    const list = listViewOf(v)
    if (list) setFrom(list)
    const hash = list ?? (v === 'wizard' ? 'wizard' : null)
    if (hash && window.location.hash !== '#' + hash) window.history.pushState(null, '', '#' + hash)
    setView(v)
    window.scrollTo(0, 0)
  }
  const openDetail = (r: DCR) => {
    setSelected(r)
    go('detail')
  }
  const openById = (id: string) => api.get(id).then(openDetail).catch(() => undefined)

  const titles: Record<View, [string, string]> = {
    dashboard: ['Overview', meta ? `${meta.record_count} records · Vienna & Kenya offices · ${meta.tracker_file}` : ''],
    records: ['Records', 'Filter, sort and open any Deviation, Complaint, Recall, Safety Notice or Partner Issue Report'],
    detail: [selected?.status === 'Draft' ? 'Review draft' : 'Record detail', 'Full record view'],
    new: ['New DCR entry', 'Fill in the fields below, then save'],
    wizard: ['New DCR from project', 'Read project emails and auto-fill the entry'],
    'wizard-working': ['Reading project', 'Processing emails'],
    'wizard-not-dcr': ['No quality issue found', 'Project does not contain a DCR'],
  }
  const nav: { id: ListView; label: string; icon: ReactNode }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <IconDashboard /> },
    { id: 'records', label: 'Records', icon: <IconRecords /> },
  ]
  const active: ListView = listViewOf(view) ?? from

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand__name">DCR Tracker</div>
          <div className="brand__sub">Deviations · Complaints · Recalls</div>
        </div>
        <nav className="nav" aria-label="Sections">
          {nav.map((n) => (
            <button key={n.id} className={`nav-item${active === n.id ? ' is-active' : ''}`} onClick={() => go(n.id)}>
              {n.icon}
              {n.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <p>
            Data source: SOP 5 DCR &amp; CAPA tracker ({meta?.tracker_file ?? '…'}). New and edited entries are written back to it.
          </p>
          <p>
            <a href={api.trackerUrl}>Download Excel tracker ↓</a>
          </p>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div>
            <div className="topbar__title">{titles[view][0]}</div>
            <div className="topbar__meta">{titles[view][1]}</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <button className="btn-secondary" onClick={() => go('wizard')} disabled={!meta} title="Read project emails and auto-fill">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 2.5v11M2.5 8h11" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
              </svg>
              From project
            </button>
            <button className="btn-primary" onClick={() => go('new')} disabled={!meta} title="Manual entry">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 2.5v11M2.5 8h11" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
              </svg>
              Manual entry
            </button>
            <div className="account" title={CURRENT_USER.email}>
              <div className="account__avatar">{CURRENT_USER.initials}</div>
              <div className="account__name">{CURRENT_USER.name}</div>
            </div>
          </div>
        </header>

        {offline && (
          <section className="view">
            <div className="notice is-critical">
              Backend not reachable ({offline}). Start it with <code>uvicorn app.main:app --reload</code> in{' '}
              <code>/backend</code>.
            </div>
          </section>
        )}

        {meta && view === 'dashboard' && (
          <Dashboard
            refreshKey={refreshKey}
            openDetail={openDetail}
            openRecords={(f) => {
              setFilters(f)
              go('records')
            }}
          />
        )}
        {meta && view === 'records' && (
          <Records meta={meta} filters={filters} setFilters={setFilters} refreshKey={refreshKey} openDetail={openDetail} />
        )}
        {meta && view === 'detail' && selected && (
          <Detail
            record={selected}
            meta={meta}
            backLabel={`Back to ${from === 'dashboard' ? 'dashboard' : 'records'}`}
            onBack={() => go(from)}
            onSaved={(r) => {
              setSelected(r)
              refresh()
            }}
          />
        )}
        {meta && view === 'new' && (
          <NewEntry
            meta={meta}
            onCancel={() => go(from)}
            onCreated={(r) => {
              refresh()
              openDetail(r)
            }}
          />
        )}
        {meta && view === 'wizard' && (
          <Wizard
            onCancel={() => go(from)}
            onCreated={(id) => {
              refresh()
              openById(id)
            }}
          />
        )}
        {meta && view === 'wizard-working' && wizardProject && (
          <WizardWorking
            project={wizardProject}
            onCancel={() => go(from)}
            onDone={(id) => {
              // leave #wizard/working/... so a reload doesn't re-open the progress page
              window.history.replaceState(null, '', '#' + from)
              refresh()
              openById(id)
            }}
            onNotADCR={() => {
              window.location.hash = `#wizard/not-a-dcr/${encodeURIComponent(wizardProject)}`
            }}
          />
        )}
        {meta && view === 'wizard-not-dcr' && wizardProject && (
          <WizardNotADCR
            project={wizardProject}
            onCancel={() => go(from)}
            onCreateAnyway={() => {
              api.wizardBlank(wizardProject).then((result) => {
                refresh()
                openById(result.id)
              })
            }}
          />
        )}
      </div>
    </div>
  )
}

function IconDashboard() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="1.5" width="6" height="6" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
      <rect x="8.5" y="1.5" width="6" height="9" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
      <rect x="1.5" y="9.5" width="6" height="5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  )
}

function IconRecords() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="2" width="13" height="12" rx="1.4" stroke="currentColor" strokeWidth="1.3" />
      <path d="M1.5 6h13" stroke="currentColor" strokeWidth="1.3" />
      <path d="M4.5 9h4M4.5 11.3h6.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

export default App
