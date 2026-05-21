import type { ReviewerSubmissionSnapshot } from '../../types/dashboard'
import { DetailField } from './DetailPrimitives'
import ParsedOutputSection from './ParsedOutputSection'
import RawSubmissionSection from './RawSubmissionSection'
import ResolvedOutputSection from './ResolvedOutputSection'
import WorkflowSection from './WorkflowSection'
import { formatSubmittedDate } from './detailUtils'

export default function InboxDetailPanel({
  submission
}: {
  submission: ReviewerSubmissionSnapshot | null
}) {
  if (submission === null) {
    return (
      <aside className="rounded-lg border border-dashed border-slate-300 bg-white px-5 py-8 text-sm text-slate-600">
        Select a submission to open its review details.
      </aside>
    )
  }

  const displayName = submission.raw.full_name.trim() || 'Unnamed submission'

  return (
    <aside className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
          Selected Submission
        </p>
        <h2 className="mt-1 text-xl font-semibold tracking-normal text-slate-950">
          {displayName}
        </h2>
      </div>

      <dl className="grid gap-4 border-b border-slate-200 px-5 py-5 text-sm">
        <DetailField label="Submission ID" value={submission.submission_id} />
        <DetailField
          label="Submitted"
          value={formatSubmittedDate(submission.raw.created_at)}
        />
      </dl>

      <WorkflowSection submission={submission} />
      <RawSubmissionSection submission={submission} />
      <ParsedOutputSection submission={submission} />
      <ResolvedOutputSection submission={submission} />
    </aside>
  )
}
