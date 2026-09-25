import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, type DCR, type Meta, type RecordFilters } from './api'
import { Dashboard } from './pages/Dashboard'
import { Detail } from './pages/Detail'
import { Inbox } from './pages/Inbox'
import { NewEntry } from './pages/NewEntry'
import { Records } from './pages/Records'
import { CURRENT_USER } from './ui'

type View = 'dashboard' | 'records' | 'inbox' | 'detail' | 'new'
type ListView = 'dashboard' | 'records' | 'inbox'
const LIST_VIEWS: ListView[] = ['dashboard', 'records', 'inbox']

/** Section from the URL hash (#records, #inbox), so reloads and browser back keep the section. */
const viewFromHash = (): ListView => {
  const h = window.location.hash.slice(1) as ListView
  return LIST_VIEWS.includes(h) ? h : 'dashboard'
}

function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [offline, setOffline] = useState<string | null>(null)
  const [view, setView] = useState<View>(viewFromHash)
  const [from, setFrom] = useState<ListView>(viewFromHash) // where "back" goes from detail
  const [selected, setSelected] = useState<DCR | null>(null)
  const [filters, setFilters] = useState<RecordFilters>({})
  const [refreshKey, setRefreshKey] = useState(0)

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
      setFrom(v)
      setView(v)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (v: View) => {
    if (v === 'dashboard' || v === 'records' || v === 'inbox') {
      setFrom(v)
      if (window.location.hash !== '#' + v) window.history.pushState(null, '', '#' + v)
    }
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
    inbox: ['E-mail inbox', 'AI reads incoming e-mails and fills new rows of the DCR tracker'],
    detail: [selected?.status === 'Draft' ? 'Review draft' : 'Record detail', 'Full record view'],
    new: ['New DCR entry', 'Fill in the fields below, then save'],
  }
  const nav: { id: ListView; label: string; icon: ReactNode; count?: number }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <IconDashboard /> },
    { id: 'records', label: 'Records', icon: <IconRecords /> },
    { id: 'inbox', label: 'E-mail inbox', icon: <IconMail />, count: meta?.draft_count || undefined },
  ]
  const active: ListView = view === 'detail' || view === 'new' ? from : view

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
              {n.count ? <span className="nav-count">{n.count}</span> : null}
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
            <button className="btn-primary" onClick={() => go('new')} disabled={!meta}>
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 2.5v11M2.5 8h11" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
              </svg>
              New entry
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
          <Dashboard refreshKey={refreshKey} openDetail={openDetail} openDrafts={() => go('inbox')} />
        )}
        {meta && view === 'records' && (
          <Records meta={meta} filters={filters} setFilters={setFilters} refreshKey={refreshKey} openDetail={openDetail} />
        )}
        {meta && view === 'inbox' && (
          <Inbox meta={meta} refreshKey={refreshKey} onChanged={refresh} openDetail={openDetail} openById={openById} />
        )}
        {meta && view === 'detail' && selected && (
          <Detail
            record={selected}
            meta={meta}
            backLabel={`Back to ${from === 'dashboard' ? 'dashboard' : from === 'inbox' ? 'inbox' : 'records'}`}
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

function IconMail() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="3" width="13" height="10" rx="1.4" stroke="currentColor" strokeWidth="1.3" />
      <path d="m2 4 6 4.5L14 4" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  )
}

export default App
