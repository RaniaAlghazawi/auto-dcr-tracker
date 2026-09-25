import { useCallback, useEffect, useState } from 'react'
import amexLogo from './assets/amex-logo.png'
import { api, type DCR, type Filters, type Meta } from './api'
import { DcrDrawer } from './components/DcrDrawer'
import { Select } from './components/ui'
import { DashboardPage } from './pages/DashboardPage'
import { InboxPage } from './pages/InboxPage'
import { RegisterPage } from './pages/RegisterPage'

type Tab = 'dashboard' | 'register' | 'inbox'

const TABS: { id: Tab; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'register', label: 'DCR register' },
  { id: 'inbox', label: 'E-mail inbox' },
]

function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [offline, setOffline] = useState(false)
  const [tab, setTab] = useState<Tab>('dashboard')
  // Filters shared by the dashboard and the register
  const [filters, setFilters] = useState<Filters>({})
  const [selected, setSelected] = useState<DCR | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const refresh = useCallback(() => {
    setRefreshKey((k) => k + 1)
    api.meta().then(setMeta).catch(() => undefined)
  }, [])

  useEffect(() => {
    api
      .meta()
      .then(setMeta)
      .catch(() => setOffline(true))
  }, [])

  const openRegister = (f: Filters) => {
    setFilters({ year: filters.year, office: filters.office, pharma: filters.pharma, ...f })
    setTab('register')
  }
  const openDcrById = (id: string) => api.get(id).then(setSelected).catch(() => undefined)

  return (
    <div className="min-h-screen bg-[#f7f7f6] text-charcoal">
      <header className="border-b border-cool-steel/40 bg-brand-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-6 py-4">
          <img src={amexLogo} alt="AMEX Healthcare" className="h-7 w-auto" />
          <div>
            <h1 className="text-lg font-normal leading-tight text-charcoal">DCR Tracker</h1>
            <p className="text-[11px] text-charcoal/60">Deviations · Complaints · Recalls — SOP 5</p>
          </div>
          <nav className="ml-auto flex gap-1" aria-label="Sections">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  tab === t.id ? 'bg-oxblood text-white' : 'text-charcoal hover:bg-cool-steel/20'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {offline && (
          <p className="rounded-md border border-oxblood/40 bg-oxblood/5 px-4 py-3 text-sm">
            Backend not reachable. Start it with <code>uvicorn app.main:app --reload</code> in <code>/backend</code>.
          </p>
        )}
        {meta && (
          <>
            {tab !== 'inbox' && (
              <div className="mb-6 flex flex-wrap items-end gap-3">
                <Select
                  label="Year occurred"
                  value={filters.year}
                  onChange={(v) => setFilters({ ...filters, year: v })}
                  options={[...meta.years].reverse().map(String)}
                  allLabel="All years"
                />
                <Select label="AMEX office" value={filters.office} onChange={(v) => setFilters({ ...filters, office: v })} options={meta.offices} />
                <Select
                  label="Pharma"
                  value={filters.pharma}
                  onChange={(v) => setFilters({ ...filters, pharma: v })}
                  options={[
                    { value: 'Y', label: 'Pharma' },
                    { value: 'N', label: 'Non-pharma' },
                  ]}
                />
                {tab === 'dashboard' && (
                  <Select label="Type" value={filters.type} onChange={(v) => setFilters({ ...filters, type: v })} options={meta.types} />
                )}
                {Object.values(filters).some(Boolean) && (
                  <button className="pb-1.5 text-xs font-medium text-oxblood hover:underline" onClick={() => setFilters({})}>
                    Clear filters
                  </button>
                )}
              </div>
            )}

            {tab === 'dashboard' && (
              <DashboardPage meta={meta} filters={filters} refreshKey={refreshKey} openRegister={openRegister} openDcr={setSelected} />
            )}
            {tab === 'register' && (
              <RegisterPage meta={meta} filters={filters} setFilters={setFilters} refreshKey={refreshKey} openDcr={setSelected} />
            )}
            {tab === 'inbox' && <InboxPage meta={meta} onIngested={refresh} openDcrById={openDcrById} />}
          </>
        )}
      </main>

      {selected && meta && (
        <DcrDrawer
          dcr={selected}
          meta={meta}
          onClose={() => setSelected(null)}
          onSaved={(d) => {
            setSelected(d)
            refresh()
          }}
        />
      )}
    </div>
  )
}

export default App
