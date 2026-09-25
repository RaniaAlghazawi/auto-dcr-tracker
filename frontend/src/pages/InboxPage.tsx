import { useEffect, useState } from 'react'
import { api, type IngestResult, type Meta } from '../api'
import { Card, formatDate } from '../components/ui'

interface Props {
  meta: Meta
  onIngested: () => void
  openDcrById: (id: string) => void
}

const RESULT_TEXT: Record<IngestResult['result'], string> = {
  created: 'New DCR draft created',
  updated: 'Added to an existing draft thread',
  attached: 'Attached to a confirmed DCR',
  not_dcr: 'Not a DCR — ignored',
  duplicate: 'Already processed',
}

export function InboxPage({ meta, onIngested, openDcrById }: Props) {
  const [raw, setRaw] = useState('')
  const [busy, setBusy] = useState(false)
  const [results, setResults] = useState<IngestResult[]>([])
  const [ignored, setIgnored] = useState<Awaited<ReturnType<typeof api.ignored>>>([])
  const [error, setError] = useState<string | null>(null)

  const loadIgnored = () => api.ignored().then(setIgnored).catch(() => setIgnored([]))
  useEffect(() => {
    loadIgnored()
  }, [])

  async function run(p: Promise<IngestResult | IngestResult[]>) {
    setBusy(true)
    setError(null)
    try {
      const r = await p
      setResults((prev) => [...(Array.isArray(r) ? r : [r]), ...prev])
      onIngested()
      loadIgnored()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card title="Read an e-mail">
          <p className="mb-3 text-sm text-charcoal/80">
            Paste a full e-mail (headers included if you have them) or upload <code>.eml</code> files. The tool picks out
            type, project, customer, supplier, category and description, and creates a draft for QA review. Replies are
            linked to the same case.
          </p>
          <textarea
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            rows={12}
            placeholder={'From: someone@customer.org\nSubject: Complaint – damaged goods, project 20260412\n\nDear team, …'}
            className="w-full rounded-md border border-cool-steel/60 px-3 py-2 font-mono text-xs text-charcoal focus:border-oxblood focus:outline-none"
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              disabled={busy || !raw.trim()}
              onClick={() => run(api.ingestText(raw)).then(() => setRaw(''))}
              className="rounded-md bg-oxblood px-4 py-1.5 text-sm font-medium text-white hover:bg-oxblood-dark disabled:opacity-40"
            >
              {busy ? 'Reading…' : 'Extract DCR'}
            </button>
            <label className="cursor-pointer rounded-md border border-oxblood px-4 py-1.5 text-sm font-medium text-oxblood hover:bg-oxblood hover:text-white">
              Upload .eml files
              <input
                type="file"
                accept=".eml,.txt,message/rfc822"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.length) run(api.ingestFiles(e.target.files))
                  e.target.value = ''
                }}
              />
            </label>
            <span className="ml-auto text-xs text-charcoal/60">
              Extraction: {meta.extractor === 'claude' ? `Claude (${meta.model})` : 'keyword rules (set CLAUDE_API_KEY to use Claude)'}
            </span>
          </div>
          {error && <p className="mt-2 text-xs text-oxblood">{error}</p>}
        </Card>

        {results.length > 0 && (
          <Card title="Processed in this session">
            <ul className="divide-y divide-cool-steel/30">
              {results.map((r, i) => (
                <li key={i} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span>
                    <span className={r.result === 'not_dcr' || r.result === 'duplicate' ? 'text-charcoal/60' : 'text-charcoal'}>
                      {RESULT_TEXT[r.result]}
                    </span>
                    {(r.file || r.subject) && <span className="ml-2 text-xs text-charcoal/60">{r.file ?? r.subject}</span>}
                  </span>
                  {r.id && (
                    <button className="text-xs font-medium text-oxblood hover:underline" onClick={() => openDcrById(r.id!)}>
                      Open →
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      <Card title="Ignored e-mails (not a DCR)">
        {ignored.length === 0 ? (
          <p className="text-sm text-charcoal/60">None yet.</p>
        ) : (
          <ul className="space-y-2">
            {ignored.map((m) => (
              <li key={m.message_id} className="text-sm">
                <div className="text-charcoal">{m.subject}</div>
                <div className="text-xs text-charcoal/60">
                  {m.sender} · {formatDate(m.date)}
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-4 text-xs text-charcoal/60">
          Later this inbox will be fed automatically from the shared mailbox tool instead of manual uploads.
        </p>
      </Card>
    </div>
  )
}
