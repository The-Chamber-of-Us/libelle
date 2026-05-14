import { useEffect, useMemo, useState } from 'react'
import InboxSubmissionRow from '../components/inbox/InboxSubmissionRow'
import type { ReviewerSubmissionSnapshot } from '../types/dashboard'

type InboxState =
  | { status: 'loading' }
  | { status: 'ready'; submissions: ReviewerSubmissionSnapshot[] }
  | { status: 'error'; message: string }

export default function Inbox() {
  const [state, setState] = useState<InboxState>({ status: 'loading' })
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<string | null>(null)

  const selectedSubmission = useMemo(() => {
    if (state.status !== 'ready' || selectedSubmissionId === null) return null

    return (
      state.submissions.find(
        (submission) => submission.submission_id === selectedSubmissionId
      ) ?? null
    )
  }, [selectedSubmissionId, state])

  useEffect(() => {
    const controller = new AbortController()

    async function loadSnapshot() {
      try {
        const response = await fetch('/snapshot', { signal: controller.signal })

        if (!response.ok) {
          throw new Error(`Snapshot request failed with ${response.status}`)
        }

        const data = await response.json()

        if (!Array.isArray(data)) {
          throw new Error('Snapshot response must be an array')
        }

        setState({ status: 'ready', submissions: data as ReviewerSubmissionSnapshot[] })
      } catch (error) {
        if (controller.signal.aborted) return

        setState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Unable to load Inbox'
        })
      }
    }

    loadSnapshot()

    return () => controller.abort()
  }, [])

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-6 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <header className="flex flex-col gap-1">
          <p className="text-sm font-semibold uppercase tracking-[0.12em] text-libelle-indigo">
            Reviewer Inbox
          </p>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
            Submissions
          </h1>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
          <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="grid gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 sm:grid-cols-[minmax(0,1.5fr)_minmax(12rem,1fr)_auto] sm:px-5">
              <span>Applicant</span>
              <span>Top Signals</span>
              <span className="sm:text-right">Status</span>
            </div>

            {state.status === 'loading' && (
              <div className="px-5 py-10 text-sm text-slate-600">Loading submissions...</div>
            )}

            {state.status === 'error' && (
              <div className="px-5 py-10 text-sm text-rose-700">{state.message}</div>
            )}

            {state.status === 'ready' && state.submissions.length === 0 && (
              <div className="px-5 py-10 text-sm text-slate-600">No submissions yet.</div>
            )}

            {state.status === 'ready' &&
              state.submissions.map((submission) => (
                <InboxSubmissionRow
                  key={submission.submission_id}
                  submission={submission}
                  isSelected={submission.submission_id === selectedSubmissionId}
                  onSelect={() => setSelectedSubmissionId(submission.submission_id)}
                />
              ))}
          </section>

          <InboxDetailPanel submission={selectedSubmission} />
        </div>
      </div>
    </main>
  )
}

function InboxDetailPanel({
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
        <DetailField label="Status" value={formatStatus(submission.ops.status)} />
        <DetailField
          label="Submitted"
          value={formatSubmittedDate(submission.raw.created_at)}
        />
      </dl>

      <RawSubmissionSection submission={submission} />
      <ParsedOutputSection submission={submission} />
      <ResolvedOutputSection submission={submission} />
    </aside>
  )
}

function RawSubmissionSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  return (
    <section className="px-5 py-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-libelle-indigo">
          Raw Submission
        </h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Source-of-truth user-entered values from submissions.
        </p>
      </div>

      <dl className="grid gap-4 text-sm">
        <DetailField label="Full Name" value={submission.raw.full_name} />
        <DetailField label="Email" value={submission.raw.email} />
        <DetailField label="Location" value={submission.raw.location_raw} />
        <DetailField label="Timezone" value={submission.raw.timezone} />
        <DetailField label="Skills" value={submission.raw.skills_raw} multiline />
        <DetailField label="Interests" value={submission.raw.interests} multiline />
        <DetailField
          label="Experience Level"
          value={submission.raw.experience_level}
        />
        <DetailField label="Availability" value={submission.raw.availability} multiline />
        <DetailField label="Motivation" value={submission.raw.motivation} multiline />
        <LinkDetailField label="LinkedIn" value={submission.raw.linkedin_url} />
        <LinkDetailField label="GitHub" value={submission.raw.github_url} />
        <DetailField label="Consent Given" value={submission.raw.consent_given} />
        <DetailField label="Resume Filename" value={submission.raw.resume_filename} />
        <DetailField label="Resume Status" value={submission.raw.resume_status} />
      </dl>
    </section>
  )
}

function ParsedOutputSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  const parsed = submission.parsed
  const isParserComplete = parsed.parser_state === 'complete'
  const hasParserOutput = hasSnapshotValue([
    parsed.parser_run_id,
    parsed.created_at,
    parsed.parser_version,
    parsed.parsed_skills_raw,
    parsed.parsed_location_raw,
    parsed.parser_confidence
  ])

  return (
    <section className="border-t border-slate-200 px-5 py-5">
      <SectionHeader
        title="Raw Parsed Output"
        description="Parser-emitted values, kept separate from user-entered and resolved data."
        status={formatStatus(parsed.parser_state)}
        statusTone={isParserComplete ? 'success' : 'neutral'}
      />

      {!isParserComplete && !hasParserOutput ? (
        <StateCallout tone="neutral">
          No parser results yet. The parser has not produced a row for this submission.
        </StateCallout>
      ) : (
        <dl className="grid gap-4 text-sm">
          <DetailField label="Parser Run ID" value={parsed.parser_run_id} />
          <DetailField
            label="Parser Created"
            value={formatSubmittedDate(parsed.created_at)}
          />
          <DetailField label="Parser Version" value={parsed.parser_version} />
          <DetailField
            label="Parsed Skills Raw"
            value={parsed.parsed_skills_raw}
            multiline
          />
          <DetailField
            label="Parsed Location Raw"
            value={parsed.parsed_location_raw}
            multiline
          />
          <DetailField label="Parser Confidence" value={parsed.parser_confidence} />
        </dl>
      )}
    </section>
  )
}

function ResolvedOutputSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  const resolved = submission.resolved
  const resolvedSkillIds = parseSnapshotList(resolved.resolved_skill_ids)
  const unknownSkills = parseSnapshotList(resolved.unknown_skills)
  const hasUnknowns = unknownSkills.length > 0
  const hasResolverRun = resolved.resolver_state !== 'not_run'

  return (
    <section className="border-t border-slate-200 px-5 py-5">
      <SectionHeader
        title="Resolved Canonical Output"
        description="Resolver/canonical values derived from parser output. Raw parsed values are not replaced here."
        status={formatStatus(resolved.resolver_state)}
        statusTone={getResolverStatusTone(resolved.resolver_state)}
      />

      {!hasResolverRun ? (
        <StateCallout tone="neutral">
          Resolver has not run for this parser result yet.
        </StateCallout>
      ) : (
        <div className="grid gap-4">
          {resolved.resolver_state === 'zero_matches' && (
            <StateCallout tone="warning">
              Resolver ran but found zero canonical skill matches.
            </StateCallout>
          )}

          {resolved.resolver_state === 'resolved' && hasUnknowns && (
            <StateCallout tone="warning">
              Partial resolution: some parsed values resolved, while unknown fields remain.
            </StateCallout>
          )}

          <dl className="grid gap-4 text-sm">
            <DetailField label="Resolver Version" value={resolved.resolver_version} />
            <DetailField label="Aliases Version" value={resolved.aliases_version} />
            <ListDetailField
              label="Resolved Skill IDs"
              values={resolvedSkillIds}
              emptyLabel="No resolved skill IDs"
            />
            <ListDetailField
              label="Unknown Skills"
              values={unknownSkills}
              emptyLabel="No unknown skills"
              tone={hasUnknowns ? 'warning' : 'neutral'}
            />
            <DetailField
              label="Resolver Coverage"
              value={resolved.resolver_coverage}
            />
          </dl>
        </div>
      )}
    </section>
  )
}

function SectionHeader({
  title,
  description,
  status,
  statusTone
}: {
  title: string
  description: string
  status: string
  statusTone: 'neutral' | 'success' | 'warning'
}) {
  return (
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-libelle-indigo">
          {title}
        </h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
      </div>
      <span
        className={[
          'inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
          statusTone === 'success'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
            : statusTone === 'warning'
              ? 'border-amber-200 bg-amber-50 text-amber-700'
              : 'border-slate-200 bg-slate-50 text-slate-600'
        ].join(' ')}
      >
        {status}
      </span>
    </div>
  )
}

function StateCallout({
  tone,
  children
}: {
  tone: 'neutral' | 'warning'
  children: string
}) {
  return (
    <p
      className={[
        'rounded-md border px-3 py-2 text-sm leading-5',
        tone === 'warning'
          ? 'border-amber-200 bg-amber-50 text-amber-800'
          : 'border-slate-200 bg-slate-50 text-slate-600'
      ].join(' ')}
    >
      {children}
    </p>
  )
}

function DetailField({
  label,
  value,
  multiline = false
}: {
  label: string
  value: string
  multiline?: boolean
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </dt>
      <dd
        className={[
          'mt-1 break-words text-slate-900',
          multiline ? 'whitespace-pre-wrap' : ''
        ].join(' ')}
      >
        {value.trim() || 'Not provided'}
      </dd>
    </div>
  )
}

function ListDetailField({
  label,
  values,
  emptyLabel,
  tone = 'neutral'
}: {
  label: string
  values: string[]
  emptyLabel: string
  tone?: 'neutral' | 'warning'
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </dt>
      <dd className="mt-2">
        {values.length > 0 ? (
          <ul className="flex flex-wrap gap-2">
            {values.map((value, index) => (
              <li
                key={`${label}-${value}-${index}`}
                className={[
                  'max-w-full break-words rounded-md border px-2.5 py-1 text-sm',
                  tone === 'warning'
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : 'border-slate-200 bg-slate-50 text-slate-800'
                ].join(' ')}
              >
                {value}
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-sm text-slate-500">{emptyLabel}</span>
        )}
      </dd>
    </div>
  )
}

function LinkDetailField({ label, value }: { label: string; value: string }) {
  const href = value.trim()

  if (!href) {
    return <DetailField label={label} value="" />
  }

  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 break-words">
        <a
          className="text-libelle-indigo underline decoration-libelle-indigo/30 underline-offset-2 hover:decoration-libelle-indigo"
          href={href}
          rel="noreferrer"
          target="_blank"
        >
          {href}
        </a>
      </dd>
    </div>
  )
}

function formatSubmittedDate(value: string) {
  if (!value.trim()) return 'No date'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  }).format(date)
}

function formatStatus(status: string) {
  return status.replace(/_/g, ' ')
}

function hasSnapshotValue(values: string[]) {
  return values.some((value) => value.trim() !== '')
}

function getResolverStatusTone(status: string) {
  if (status === 'resolved') return 'success'
  if (status === 'zero_matches') return 'warning'
  return 'neutral'
}

function parseSnapshotList(value: string) {
  const text = value.trim()

  if (!text) return []

  try {
    const parsed = JSON.parse(text)

    if (Array.isArray(parsed)) {
      return parsed.map(String).map((item) => item.trim()).filter(Boolean)
    }
  } catch {
    return splitSnapshotList(text)
  }

  return splitSnapshotList(text)
}

function splitSnapshotList(value: string) {
  return value
    .split(/[,;\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}
