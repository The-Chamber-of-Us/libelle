import { useEffect, useState } from 'react'
import type { CoordinationRecord, ReviewerSubmissionSnapshot } from '../../types/dashboard'

const fields = [
  ['purpose', 'Coordination purpose', 500],
  ['display_name', 'Display name', 200],
  ['contact', 'Contact needed for coordination', 300],
  ['takeaway', 'Reviewer takeaway', 1000],
  ['why', 'Why', 500],
  ['next_action', 'Next action', 500]
] as const

function draftFrom(record: CoordinationRecord | null) {
  return {
    purpose: record?.purpose ?? '', display_name: record?.display_name ?? '',
    contact: record?.contact ?? '', takeaway: record?.takeaway ?? '',
    why: record?.why ?? '', next_action: record?.next_action ?? '', revisit: record?.revisit ?? ''
  }
}

export default function CoordinationSection({ submission, onSaved }: {
  submission: ReviewerSubmissionSnapshot
  onSaved?: (id: string, record: CoordinationRecord) => void
}) {
  const [record, setRecord] = useState<CoordinationRecord | null>(submission.coordination ?? null)
  const [draft, setDraft] = useState(() => draftFrom(record))
  const serverRecord = JSON.stringify(submission.coordination ?? null)
  const [reviewed, setReviewed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const malformed = submission.coordination_state === 'malformed'

  useEffect(() => {
    const current: CoordinationRecord | null = JSON.parse(serverRecord)
    setRecord(current)
    setDraft(draftFrom(current))
    setReviewed(false)
    setMessage('')
  }, [submission.submission_id, serverRecord])

  async function save(action: 'preserve' | 'end') {
    setSaving(true)
    setMessage('')
    try {
      const response = await fetch(`/submissions/${encodeURIComponent(submission.submission_id)}/coordination`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...draft, revisit: draft.revisit || null, action, context_reviewed: reviewed })
      })
      if (!response.ok) throw new Error('Coordination could not be saved. Review the fields and try again.')
      const saved: CoordinationRecord = await response.json()
      setRecord(saved)
      setDraft(draftFrom(saved))
      onSaved?.(submission.submission_id, saved)
      setReviewed(false)
      setMessage(action === 'end' ? 'Coordination purpose ended.' : 'Coordination purpose preserved.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Coordination could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  return <section className="grid gap-3 border-b border-slate-200 px-5 py-5 text-sm">
    <h3 className="font-semibold text-libelle-indigo">Coordination continuity</h3>
    <p>Purpose: {malformed ? 'Requires operator review' : record?.state ?? 'Not yet assessed'}</p>
    <p>Keep only context needed to coordinate. Do not copy resumes, employment or education histories into these fields or notes. Workflow status above is STATE; it does not start or end retention.</p>
    {fields.map(([field, label, maxLength]) => <label key={field} className="grid gap-1">
      {label}
      <textarea className="rounded border border-slate-300 p-2" maxLength={maxLength}
        value={draft[field]} disabled={saving || malformed}
        onChange={event => setDraft({ ...draft, [field]: event.target.value })} />
    </label>)}
    <label className="grid gap-1">Revisit
      <input type="date" className="rounded border border-slate-300 p-2" value={draft.revisit}
        disabled={saving || malformed} onChange={event => setDraft({ ...draft, revisit: event.target.value })} />
    </label>
    <label className="flex items-start gap-2">
      <input type="checkbox" checked={reviewed} disabled={saving || malformed}
        onChange={event => setReviewed(event.target.checked)} />
      I reviewed the coordination fields, notes, tags and contact tracking. They contain only context intentionally needed for coordination, with a defined purpose.
    </label>
    <div className="flex gap-3">
      <button type="button" className="rounded border px-3 py-2 disabled:opacity-50"
        disabled={saving || malformed || !reviewed || !draft.purpose.trim()} onClick={() => save('preserve')}>
        {record?.state === 'ended' ? 'Start new purpose' : 'Preserve purpose'}
      </button>
      <button type="button" className="rounded border px-3 py-2 disabled:opacity-50"
        disabled={saving || malformed || !record || !reviewed || !draft.purpose.trim()} onClick={() => save('end')}>
        End purpose
      </button>
    </div>
    {record?.purpose_ended_at && <p>Purpose ended: {record.purpose_ended_at}. Later edits do not restart this retention clock.</p>}
    {message && <p role="status">{message}</p>}
  </section>
}
