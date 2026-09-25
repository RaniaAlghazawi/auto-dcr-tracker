export type DcrStatus = 'Draft' | 'Open' | 'Closed'

export interface SourceEmail {
  message_id: string
  sender: string
  subject: string
  date: string | null
  body: string
  attachments: string[]
}

/** One row of the SOP 5-A1 tracker (+ app fields). Field names follow the backend. */
export interface DCR {
  id: string
  tracking_number: string | null
  type: string | null
  critical: string | null
  occurred_on: string | null
  entered_by: string | null
  amex_office: string | null
  pharma: string | null
  supplier: string | null
  customer: string | null
  project: string | null
  responsible_party: string | null
  responsible_party_name: string | null
  category: string | null
  description: string | null
  root_cause: string | null
  financial_impact: string | null
  actions_taken: string | null
  capa_needed: string | null
  capa_plan: string | null
  actions: string | null
  closure_date: string | null
  excel_row: number | null
  status: DcrStatus
  source: 'tracker' | 'email'
  freight_forwarder: string | null
  reported_by_party: string | null
  source_emails: SourceEmail[]
  requested_actions: string | null
  extraction_method: string | null
  issues: string[]
}

export type EditableField =
  | 'type' | 'critical' | 'occurred_on' | 'entered_by' | 'amex_office' | 'pharma' | 'supplier'
  | 'customer' | 'project' | 'responsible_party' | 'responsible_party_name' | 'category'
  | 'description' | 'root_cause' | 'financial_impact' | 'actions_taken' | 'capa_needed'
  | 'capa_plan' | 'actions' | 'closure_date' | 'freight_forwarder'

export type DcrPatch = Partial<Record<EditableField, string | null>>

export interface Meta {
  types: string[]
  categories: string[]
  responsible_parties: string[]
  offices: string[]
  customers: string[]
  record_count: number
  next_tracking_number: string
  tracker_file: string
  extractor: 'claude' | 'rules'
  model: string | null
  today: string
}

export interface NamedCount {
  name: string
  count: number
}

export interface Dashboard {
  year: number
  filter_year: number | null
  years: number[]
  kpis: {
    total: number
    open: number
    overdue: number
    financial_ytd_eur: number
    critical_open: number
    capa_pending: number
  }
  by_type: NamedCount[]
  by_category: NamedCount[]
  open_by_supplier: NamedCount[]
  open_by_customer: NamedCount[]
  attention: DCR[]
}

export interface RecordFilters {
  search?: string
  type?: string
  status?: string
  critical?: string
  office?: string
  customer?: string
  /** "true": open more than 60 days — same rule as the dashboard's Overdue tile */
  overdue?: string
  /** cases occurred in this year with a EUR financial impact — the dashboard's financial tile */
  financial_year?: string
}

// ---- "From project" wizard (backend/app/routers/wizard.py)
export interface WizardProject {
  number: string
  status: 'new' | 'draft' | 'recorded'
  dcr_number: string | null
}
export interface WizardStart {
  suggestions: WizardProject[]
  engine: string
  pending_drafts: number
}
export interface WizardSubmitResult {
  result: 'started' | 'created' | 'drafted' | 'existing_draft' | 'existing_record'
  id?: string
  dcr_id?: string
  message?: string
  project?: string
}
export interface WizardWorkingInfo {
  project: string
  info: { email_count: number; thread_count: number; parties: { name: string; count: number }[] }
  engine: string
  pending_drafts: number
}
export interface WizardStatus {
  running: boolean
  done: number
  total: number
  current: string
  engine: string
  percent: number
  outcome?: string | null
  reason?: string | null
  next_url?: string
}
export interface WizardNotADCRInfo {
  project: string
  reason: string
  summary: string
  emails: number
  pending_drafts: number
}

function query(params: Record<string, string | boolean | undefined>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* not JSON */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const post = (url: string, body?: unknown) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export const api = {
  meta: () => fetch('/api/meta').then((r) => json<Meta>(r)),
  dashboard: (year?: number | null) => fetch(`/api/dashboard${query({ year: year ? String(year) : undefined })}`).then((r) => json<Dashboard>(r)),
  list: (f: RecordFilters) => fetch(`/api/dcrs${query({ ...f })}`).then((r) => json<DCR[]>(r)),
  get: (id: string) => fetch(`/api/dcrs/${encodeURIComponent(id)}`).then((r) => json<DCR>(r)),
  create: (values: DcrPatch) => post('/api/dcrs', values).then((r) => json<DCR>(r)),
  update: (id: string, patch: DcrPatch) =>
    fetch(`/api/dcrs/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).then((r) => json<DCR>(r)),
  /** Accept a draft (e.g. from the wizard): next DCR number + new row in the Excel tracker. */
  confirm: (id: string, entered_by: string) =>
    post(`/api/dcrs/${encodeURIComponent(id)}/confirm`, { entered_by }).then((r) => json<DCR>(r)),
  trackerUrl: '/api/tracker.xlsx',

  reload: () => post('/api/admin/reload').then((r) => json<{ records: number }>(r)),
  reset: () => post('/api/admin/reset').then((r) => json<{ records: number }>(r)),

  // Wizard API
  wizardStart: () => fetch('/api/wizard/').then((r) => json<WizardStart>(r)),
  wizardSubmit: (project: string, force: boolean) => post('/api/wizard/', { project, force }).then((r) => json<WizardSubmitResult>(r)),
  wizardWorking: (project: string) => fetch(`/api/wizard/working/${encodeURIComponent(project)}`).then((r) => json<WizardWorkingInfo>(r)),
  wizardWorkingStatus: (project: string) =>
    fetch(`/api/wizard/working/${encodeURIComponent(project)}/status`).then((r) => json<WizardStatus>(r)),
  wizardNotADCR: (project: string) => fetch(`/api/wizard/not-a-dcr/${encodeURIComponent(project)}`).then((r) => json<WizardNotADCRInfo>(r)),
  wizardBlank: (project: string) => post(`/api/wizard/blank/${encodeURIComponent(project)}`).then((r) => json<{ result: string; id: string; message: string }>(r)),
}
