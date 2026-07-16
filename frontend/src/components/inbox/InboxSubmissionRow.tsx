import { AlertTriangle, CalendarDays, MapPin } from 'lucide-react'
import type { ReviewerSubmissionSnapshot } from '../../types/dashboard'
import {
  formatStatus,
  formatSubmittedDate,
  formatSubmissionHealthState,
  getSubmissionHealthTone,
  type SnapshotTone
} from './detailUtils'

const statusStyles: Record<string, string> = {
  new: 'border-sky-200 bg-sky-50 text-sky-700',
  reviewed: 'border-violet-200 bg-violet-50 text-violet-700',
  contacted: 'border-amber-200 bg-amber-50 text-amber-700',
  in_progress: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  paused: 'border-orange-200 bg-orange-50 text-orange-700',
  closed: 'border-slate-200 bg-slate-50 text-slate-600'
}

const healthToneStyles: Record<SnapshotTone, string> = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  danger: 'border-rose-200 bg-rose-50 text-rose-700',
  neutral: 'border-slate-200 bg-slate-50 text-slate-600'
}

export default function InboxSubmissionRow({
  submission,
  isSelected,
  onSelect
}: {
  submission: ReviewerSubmissionSnapshot
  isSelected: boolean
  onSelect: () => void
}) {
  const skills = getListSignals(submission)
  const submittedDate = formatSubmittedDate(submission.raw.created_at)
  const location =
    submission.parsed.parsed_location_raw.trim() || submission.raw.location_raw.trim()
  const healthTone = getSubmissionHealthTone(submission.submission_health_state)

  return (
    <button
      type="button"
      aria-pressed={isSelected}
      onClick={onSelect}
      className={[
        'grid w-full gap-4 border-b px-4 py-4 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-libelle-indigo sm:grid-cols-[minmax(0,1.5fr)_minmax(12rem,1fr)_auto] sm:items-center sm:px-5',
        isSelected
          ? 'border-libelle-indigo/30 bg-indigo-50'
          : 'border-slate-200 bg-white hover:bg-slate-50'
      ].join(' ')}
    >
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate text-base font-semibold leading-6 text-slate-950">
            {submission.raw.full_name || 'Unnamed submission'}
          </h2>
          {submission.errors.has_error && (
            <span
              className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-50 text-rose-600"
              title={submission.errors.latest_error_summary || 'Attention needed'}
            >
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">Attention needed</span>
            </span>
          )}
        </div>

        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600">
          <span className="inline-flex min-w-0 items-center gap-1.5">
            <MapPin className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="truncate">{location || 'Location not provided'}</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <CalendarDays className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            <span>{submittedDate}</span>
          </span>
        </div>
      </div>

      <div className="flex min-w-0 flex-wrap gap-2">
        {skills.length > 0 ? (
          skills.map((skill, index) => (
            <span
              key={`${submission.submission_id}-${skill}-${index}`}
              className={[
                'max-w-full truncate rounded-full border px-3 py-1 text-sm leading-5 text-slate-700',
                isSelected ? 'border-indigo-200 bg-white' : 'border-slate-200 bg-white'
              ].join(' ')}
            >
              {skill}
            </span>
          ))
        ) : (
          <span className="text-sm text-slate-500">No skills listed</span>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 sm:justify-end">
        <span
          className={[
            'inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
            healthToneStyles[healthTone]
          ].join(' ')}
        >
          {formatSubmissionHealthState(submission.submission_health_state)}
        </span>
        <span
          className={[
            'inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
            statusStyles[submission.ops.status] ?? statusStyles.new
          ].join(' ')}
        >
          {formatStatus(submission.ops.status)}
        </span>
      </div>
    </button>
  )
}

function getListSignals(submission: ReviewerSubmissionSnapshot) {
  const source =
    submission.parsed.parsed_skills_raw.trim() || submission.raw.skills_raw.trim()

  return source
    .split(/[,;\n]/)
    .map((skill) => skill.trim())
    .filter(Boolean)
    .slice(0, 3)
}
