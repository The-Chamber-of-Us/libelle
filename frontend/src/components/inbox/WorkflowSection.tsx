import { useEffect, useState } from 'react'
import type { OpsStatus, ReviewerSubmissionSnapshot } from '../../types/dashboard'
import { DetailField, SectionHeader, StateCallout } from './DetailPrimitives'
import {
  formatErrorState,
  formatParserResultState,
  formatResolverResultState,
  formatSubmissionHealthState,
  formatStatus,
  formatSubmittedDate,
  getErrorStateTone,
  getOpsStatusTone,
  getParserResultTone,
  getResolverResultTone,
  getSubmissionHealthTone,
  hasSnapshotValue
} from './detailUtils'

export default function WorkflowSection({
  submission,
  statusOptions,
  pendingStatus,
  statusSaveState,
  notesSaveState,
  onStatusChange,
  onNotesSave
}: {
  submission: ReviewerSubmissionSnapshot
  statusOptions: OpsStatus[]
  pendingStatus: OpsStatus | null
  statusSaveState: StatusSaveState
  notesSaveState: StatusSaveState
  onStatusChange: (status: OpsStatus) => void
  onNotesSave: (notes: string) => void
}) {
  const ops = submission.ops
  const parsed = submission.parsed
  const resolved = submission.resolved
  const errors = submission.errors
  const [notesDraft, setNotesDraft] = useState(ops.notes)
  const selectedStatus = pendingStatus ?? ops.status
  const isStatusSaving = statusSaveState.status === 'saving'
  const isNotesSaving = notesSaveState.status === 'saving'
  const hasNotesChanges = notesDraft !== ops.notes
  const hasOpsMetadata = hasSnapshotValue([
    ops.tags,
    ops.contact_tracking,
    ops.updated_at,
    ops.updated_by
  ])

  useEffect(() => {
    setNotesDraft(ops.notes)
  }, [ops.notes, submission.submission_id])

  return (
    <section className="border-b border-slate-200 bg-slate-50/60 px-5 py-5">
      <SectionHeader
        title="Workflow"
        description="Reviewer-facing state and lightweight diagnostics from the snapshot."
        status={formatSubmissionHealthState(submission.submission_health_state)}
        statusTone={getSubmissionHealthTone(submission.submission_health_state)}
      />

      <div className="grid gap-4 text-sm">
        <div className="rounded-md border border-slate-200 bg-white px-3 py-3">
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                Snapshot Health
              </p>
              <p className="text-sm leading-5 text-slate-700">
                {formatSubmissionHealthState(submission.submission_health_state)}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <SnapshotStateBadge
                label={formatParserResultState(parsed.parser_result_state)}
                tone={getParserResultTone(parsed.parser_result_state)}
              />
              <SnapshotStateBadge
                label={formatResolverResultState(resolved.resolver_result_state)}
                tone={getResolverResultTone(resolved.resolver_result_state)}
              />
              <SnapshotStateBadge
                label={formatErrorState(errors.error_state)}
                tone={getErrorStateTone(errors.error_state)}
              />
              <SnapshotStateBadge
                label={`Workflow ${formatStatus(ops.status)}`}
                tone={getOpsStatusTone(ops.status)}
              />
            </div>
          </div>
        </div>

        <label className="grid gap-2 text-sm font-medium text-slate-700">
          Workflow Status
          <select
            className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20 disabled:cursor-wait disabled:bg-slate-100 disabled:text-slate-500"
            value={selectedStatus}
            onChange={(event) => onStatusChange(event.target.value as OpsStatus)}
            disabled={isStatusSaving}
          >
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {formatStatus(status)}
              </option>
            ))}
          </select>
        </label>

        {statusSaveState.status !== 'idle' && (
          <p
            className={[
              'rounded-md border px-3 py-2 text-sm leading-5',
              statusSaveState.status === 'error'
                ? 'border-rose-200 bg-rose-50 text-rose-700'
                : 'border-slate-200 bg-white text-slate-600'
            ].join(' ')}
          >
            {statusSaveState.message}
          </p>
        )}

        <div className="grid gap-2">
          <label
            className="grid gap-2 text-sm font-medium text-slate-700"
            htmlFor={`ops-notes-${submission.submission_id}`}
          >
            Notes
            <textarea
              id={`ops-notes-${submission.submission_id}`}
              className="min-h-[9rem] rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-normal leading-5 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20 disabled:cursor-wait disabled:bg-slate-100 disabled:text-slate-500"
              value={notesDraft}
              onChange={(event) => setNotesDraft(event.target.value)}
              placeholder="Add internal context, follow-up tasks, or reviewer notes."
              disabled={isNotesSaving}
            />
          </label>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-slate-500">
              Saves internal notes only. Workflow status is unchanged.
            </p>
            <button
              type="button"
              className="inline-flex h-10 items-center justify-center rounded-md bg-libelle-indigo px-4 text-sm font-semibold text-white transition hover:bg-libelle-indigo/90 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
              onClick={() => onNotesSave(notesDraft)}
              disabled={!hasNotesChanges || isNotesSaving}
            >
              {isNotesSaving ? 'Saving...' : 'Save Notes'}
            </button>
          </div>

          {notesSaveState.status !== 'idle' && (
            <p
              className={[
                'rounded-md border px-3 py-2 text-sm leading-5',
                notesSaveState.status === 'error'
                  ? 'border-rose-200 bg-rose-50 text-rose-700'
                  : 'border-slate-200 bg-white text-slate-600'
              ].join(' ')}
            >
              {notesSaveState.message}
            </p>
          )}
        </div>

        {hasOpsMetadata && (
          <dl className="grid gap-4 border-t border-slate-200 pt-4 text-sm">
            <DetailField label="Tags" value={ops.tags} />
            <DetailField label="Contact Tracking" value={ops.contact_tracking} />
            <DetailField
              label="Workflow Updated"
              value={formatSubmittedDate(ops.updated_at)}
            />
            <DetailField label="Updated By" value={ops.updated_by} />
          </dl>
        )}

        <div className="border-t border-slate-200 pt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
              Error Visibility
            </h4>
            <span
              className={[
                'inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
                errors.error_state === 'present'
                  ? 'border-rose-200 bg-rose-50 text-rose-700'
                  : errors.error_state === 'unavailable'
                    ? 'border-amber-200 bg-amber-50 text-amber-700'
                  : 'border-slate-200 bg-white text-slate-600'
              ].join(' ')}
            >
              {formatErrorState(errors.error_state)}
            </span>
          </div>

          {errors.error_state === 'present' ? (
            <div className="rounded-md border border-rose-100 bg-white px-3 py-3">
              <p className="break-words text-sm leading-5 text-slate-900">
                {errors.latest_error_summary.trim() || 'Latest error summary not provided'}
              </p>
              <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                <DetailField label="Stage" value={errors.latest_error_stage} />
                <DetailField label="Code" value={errors.latest_error_code} />
              </dl>
            </div>
          ) : errors.error_state === 'unavailable' ? (
            <StateCallout tone="warning">
              Error source is unavailable for this snapshot.
            </StateCallout>
          ) : (
            <p className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm leading-5 text-slate-600">
              No current error signal.
            </p>
          )}
        </div>
      </div>
    </section>
  )
}

function SnapshotStateBadge({ label, tone }: { label: string; tone: 'neutral' | 'success' | 'warning' | 'danger' }) {
  return (
    <span
      className={[
        'inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
        tone === 'success'
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : tone === 'warning'
            ? 'border-amber-200 bg-amber-50 text-amber-700'
            : tone === 'danger'
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-slate-200 bg-slate-50 text-slate-600'
      ].join(' ')}
    >
      {label}
    </span>
  )
}

export type StatusSaveState =
  | { status: 'idle'; message?: undefined }
  | { status: 'saving'; message: string }
  | { status: 'saved'; message: string }
  | { status: 'error'; message: string }
