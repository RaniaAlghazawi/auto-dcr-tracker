export type DcrStatus = 'Draft' | 'Open' | 'Closed'

export interface SourceEmail {
  message_id: string
  sender: string
  subject: string
  date: string | null
  body: string
}

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
  status: DcrStatus
  source: 'tracker' | 'email'
  freight_forwarder: string | null
  reported_by_party: string | null
  source_emails: SourceEmail[]
  requested_actions: string | null
  extraction_method: string | null
  issues: string[]
}

export interface Meta {
  types: string[]
  categories: string[]
  responsible_parties: string[]
  offices: string[]
  years: number[]
  extractor: 'claude' | 'rules'
  model: string | null
}

export interface NamedCount {
  name: string
  count: number
}

export interface RankedParty {
  name: string
  total: number
  by_type: Record<string, number>
}

export interface Dashboard {
  kpis: {
    total: number
    open: number
    closed: number
    drafts: number
    critical: number
    capa_needed: number
    projects: number
    customers: number
    suppliers: number
    with_issues: number
  }
  by_type: NamedCount[]
  by_category: NamedCount[]
  by_responsible: NamedCount[]
  top_customers: RankedParty[]
  top_suppliers: RankedParty[]
  trend: { month: string; total: number; by_type: Record<string, number> }[]
  matrix: Record<string, Record<string, number>>
  quality_issues: { issue: string; count: number }[]
}

export interface Filters {
  year?: string
  office?: string
  pharma?: string
  type?: string
  status?: string
  search?: string
  has_issues?: string
}

export interface IngestResult {
  file?: string
  result: 'created' | 'updated' | 'attached' | 'not_dcr' | 'duplicate'
  id?: string
  subject?: string
  method?: string
}

function query(filters: Filters): string {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v)
  const s = params.toString()
  return s ? `?${s}` : ''
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  meta: () => fetch('/api/meta').then((r) => json<Meta>(r)),
  dashboard: (f: Filters) => fetch(`/api/dashboard${query(f)}`).then((r) => json<Dashboard>(r)),
  list: (f: Filters) => fetch(`/api/dcrs${query(f)}`).then((r) => json<DCR[]>(r)),
  get: (id: string) => fetch(`/api/dcrs/${encodeURIComponent(id)}`).then((r) => json<DCR>(r)),
  exportUrl: (f: Filters) => `/api/dcrs/export.xlsx${query(f)}`,
  update: (id: string, patch: Partial<DCR>) =>
    fetch(`/api/dcrs/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).then((r) => json<DCR>(r)),
  confirm: (id: string, entered_by: string) =>
    fetch(`/api/dcrs/${id}/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entered_by }),
    }).then((r) => json<DCR>(r)),
  ingestText: (raw: string) =>
    fetch('/api/emails', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw }),
    }).then((r) => json<IngestResult>(r)),
  ingestFiles: (files: FileList) => {
    const body = new FormData()
    for (const f of Array.from(files)) body.append('files', f)
    return fetch('/api/emails/upload', { method: 'POST', body }).then((r) => json<IngestResult[]>(r))
  },
  ignored: () =>
    fetch('/api/emails/ignored').then((r) =>
      json<{ message_id: string; sender: string; subject: string; date: string | null }[]>(r),
    ),
}
