import type { ReviewerSubmissionSnapshot } from '../../types/dashboard'
import { DetailField, SectionHeader } from './DetailPrimitives'
import {
  formatStatus,
  formatSubmittedDate,
  getOpsStatusTone,
  hasSnapshotValue
} from './detailUtils'

export default function WorkflowSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  const ops = submission.ops
  const errors = submission.errors
  const hasOpsMetadata = hasSnapshotValue([
    ops.tags,
    ops.contact_tracking,
    ops.updated_at,
    ops.updated_by
  ])

  return (
    <section className="border-b border-slate-200 bg-slate-50/60 px-5 py-5">
      <SectionHeader
        title="Workflow"
        description="Reviewer-facing state and lightweight diagnostics from the snapshot."
        status={formatStatus(ops.status)}
        statusTone={getOpsStatusTone(ops.status)}
      />

      <div className="grid gap-4 text-sm">
        <DetailField label="Notes Preview" value={ops.notes} multiline />

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
                errors.has_error
                  ? 'border-rose-200 bg-rose-50 text-rose-700'
                  : 'border-slate-200 bg-white text-slate-600'
              ].join(' ')}
            >
              {errors.has_error ? 'Error' : 'Clear'}
            </span>
          </div>

          {errors.has_error ? (
            <div className="rounded-md border border-rose-100 bg-white px-3 py-3">
              <p className="break-words text-sm leading-5 text-slate-900">
                {errors.latest_error_summary.trim() || 'Latest error summary not provided'}
              </p>
              <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                <DetailField label="Stage" value={errors.latest_error_stage} />
                <DetailField label="Code" value={errors.latest_error_code} />
              </dl>
            </div>
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
