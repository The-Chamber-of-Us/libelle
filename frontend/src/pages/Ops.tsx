import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, Search, X } from 'lucide-react'
import DashboardTabs from '../components/dashboard/DashboardTabs'
import {
  formatStatus,
  formatSubmissionHealthState,
  formatSubmittedDate,
  getOpsStatusTone,
  getSubmissionHealthTone,
  parseSnapshotList
} from '../components/inbox/detailUtils'
import type {
  OpsStatus,
  OpsStatusListResponse,
  ReviewerSubmissionSnapshot,
  SnapshotOpsData,
  SubmissionHealthState
} from '../types/dashboard'

type OpsState =
  | { status: 'loading' }
  | {
      status: 'ready'
      submissions: ReviewerSubmissionSnapshot[]
      statusOptions: OpsStatus[]
    }
  | { status: 'error'; message: string }

type RefreshState =
  | { status: 'idle' }
  | { status: 'refreshing' }
  | { status: 'error'; message: string }

const SUBMISSION_HEALTH_OPTIONS: SubmissionHealthState[] = [
  'complete',
  'partial_success',
  'no_resume_ok',
  'parser_failed',
  'resolver_failed',
  'pending_processing',
  'broken_pipeline'
]

export default function Ops() {
  const [state, setState] = useState<OpsState>({ status: 'loading' })
  const [refreshState, setRefreshState] = useState<RefreshState>({ status: 'idle' })
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<OpsStatus | 'all'>('all')
  const [healthFilter, setHealthFilter] = useState<SubmissionHealthState | 'all'>(
    'all'
  )

  const filteredSubmissions = useMemo(() => {
    if (state.status !== 'ready') return []

    return state.submissions
      .filter((submission) =>
        matchesOpsFilters(submission, {
          searchQuery,
          statusFilter,
          healthFilter
        })
      )
      .sort(compareOpsSubmissions)
  }, [healthFilter, searchQuery, state, statusFilter])

  const hasActiveFilters =
    searchQuery.trim() !== '' || statusFilter !== 'all' || healthFilter !== 'all'
  const statusOptions = state.status === 'ready' ? state.statusOptions : []
  const isRefreshing = refreshState.status === 'refreshing'

  useEffect(() => {
    const controller = new AbortController()

    async function loadOpsSnapshot() {
      try {
        setState(await fetchOpsState(controller.signal))
      } catch (error) {
        if (controller.signal.aborted) return

        setState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Unable to load Ops'
        })
      }
    }

    loadOpsSnapshot()

    return () => controller.abort()
  }, [])

  async function handleRefresh() {
    const controller = new AbortController()
    setRefreshState({ status: 'refreshing' })

    try {
      setState(await fetchOpsState(controller.signal))
      setRefreshState({ status: 'idle' })
    } catch (error) {
      setRefreshState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Unable to refresh Ops.'
      })
    }
  }

  function clearFilters() {
    setSearchQuery('')
    setStatusFilter('all')
    setHealthFilter('all')
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-6 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <header className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-semibold uppercase tracking-[0.12em] text-libelle-indigo">
              Dashboard
            </p>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
                  Ops
                </h1>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  Read-only workflow-state snapshot for reviewer inspection.
                </p>
              </div>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                onClick={handleRefresh}
                disabled={isRefreshing || state.status === 'loading'}
                title="Refresh Ops"
              >
                <RefreshCw
                  className={['h-4 w-4', isRefreshing ? 'animate-spin' : ''].join(' ')}
                  aria-hidden="true"
                />
                {isRefreshing ? 'Refreshing' : 'Refresh'}
              </button>
            </div>
          </div>
          <DashboardTabs />
        </header>

        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 bg-white px-4 py-4 sm:px-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
              <label className="grid gap-1 text-sm font-medium text-slate-700 lg:flex-1">
                Search
                <span className="relative">
                  <Search
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                    aria-hidden="true"
                  />
                  <input
                    className="h-10 w-full rounded-md border border-slate-300 bg-white pl-9 pr-3 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20"
                    type="search"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    placeholder="Name, submission ID, notes, tags, contact"
                  />
                </span>
              </label>

              <label className="grid gap-1 text-sm font-medium text-slate-700 lg:w-44">
                Status
                <select
                  className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20"
                  value={statusFilter}
                  onChange={(event) =>
                    setStatusFilter(event.target.value as OpsStatus | 'all')
                  }
                >
                  <option value="all">All statuses</option>
                  {statusOptions.map((status) => (
                    <option key={status} value={status}>
                      {formatStatus(status)}
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-1 text-sm font-medium text-slate-700 lg:w-52">
                Health
                <select
                  className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20"
                  value={healthFilter}
                  onChange={(event) =>
                    setHealthFilter(event.target.value as SubmissionHealthState | 'all')
                  }
                >
                  <option value="all">All health states</option>
                  {SUBMISSION_HEALTH_OPTIONS.map((healthState) => (
                    <option key={healthState} value={healthState}>
                      {formatSubmissionHealthState(healthState)}
                    </option>
                  ))}
                </select>
              </label>

              <button
                type="button"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={clearFilters}
                disabled={!hasActiveFilters}
                title="Clear filters"
              >
                <X className="h-4 w-4" aria-hidden="true" />
                Clear
              </button>
            </div>

            {state.status === 'ready' && (
              <p className="mt-3 text-sm text-slate-500">
                Showing {filteredSubmissions.length} of {state.submissions.length}{' '}
                submissions
              </p>
            )}

            {refreshState.status === 'error' && (
              <p className="mt-3 text-sm font-medium text-rose-700">
                Refresh failed: {refreshState.message}
              </p>
            )}
          </div>

          {state.status === 'loading' && (
            <div className="px-5 py-10 text-sm text-slate-600">
              Loading workflow state...
            </div>
          )}

          {state.status === 'error' && (
            <div className="px-5 py-10 text-sm text-rose-700">{state.message}</div>
          )}

          {state.status === 'ready' && state.submissions.length === 0 && (
            <div className="px-5 py-10 text-sm text-slate-600">No submissions yet.</div>
          )}

          {state.status === 'ready' &&
            state.submissions.length > 0 &&
            filteredSubmissions.length === 0 && (
              <div className="px-5 py-10 text-sm text-slate-600">
                No workflow states match the current filters.
              </div>
            )}

          {state.status === 'ready' && filteredSubmissions.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                  <tr>
                    <th scope="col" className="px-4 py-3 sm:px-5">
                      Name
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Submission ID
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Status
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Health
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Notes
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Tags
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Contact
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Updated
                    </th>
                    <th scope="col" className="px-4 py-3 sm:px-5">
                      Updated By
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {filteredSubmissions.map((submission) => (
                    <OpsRow key={submission.submission_id} submission={submission} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}

function OpsRow({ submission }: { submission: ReviewerSubmissionSnapshot }) {
  const ops = submission.ops
  const displayName = submission.raw.full_name.trim() || 'Unnamed submission'
  const tags = parseSnapshotList(ops.tags)
  const hasOpsState = hasTouchedOpsState(ops)

  return (
    <tr className={hasOpsState ? 'bg-white' : 'bg-slate-50/60'}>
      <td className="max-w-[14rem] px-4 py-4 align-top sm:px-5">
        <div className="font-medium text-slate-950">{displayName}</div>
        <div className="mt-1 text-xs text-slate-500">
          {formatSubmittedDate(submission.raw.created_at)}
        </div>
      </td>
      <td className="max-w-[10rem] px-4 py-4 align-top">
        <span className="break-all font-mono text-xs text-slate-700">
          {submission.submission_id}
        </span>
      </td>
      <td className="px-4 py-4 align-top">
        <StatusBadge
          label={formatStatus(ops.status)}
          tone={getOpsStatusTone(ops.status)}
        />
        {!hasOpsState && (
          <div className="mt-2 text-xs font-medium text-slate-500">
            No ops state yet
          </div>
        )}
      </td>
      <td className="px-4 py-4 align-top">
        <StatusBadge
          label={formatSubmissionHealthState(submission.submission_health_state)}
          tone={getSubmissionHealthTone(submission.submission_health_state)}
        />
      </td>
      <td className="max-w-[18rem] px-4 py-4 align-top text-slate-700">
        <PreviewText value={ops.notes} emptyLabel="No notes" />
      </td>
      <td className="max-w-[16rem] px-4 py-4 align-top">
        <TagList tags={tags} />
      </td>
      <td className="max-w-[12rem] px-4 py-4 align-top text-slate-700">
        <PreviewText value={ops.contact_tracking} emptyLabel="Not contacted" />
      </td>
      <td className="max-w-[12rem] px-4 py-4 align-top text-slate-700">
        {ops.updated_at.trim() ? (
          formatSubmittedDate(ops.updated_at)
        ) : (
          <span className="text-slate-500">Not updated yet</span>
        )}
      </td>
      <td className="max-w-[14rem] px-4 py-4 align-top text-slate-700 sm:px-5">
        {ops.updated_by.trim() ? (
          <span className="break-words">{ops.updated_by}</span>
        ) : (
          <span className="text-slate-500">Not updated yet</span>
        )}
      </td>
    </tr>
  )
}

function StatusBadge({
  label,
  tone
}: {
  label: string
  tone: 'neutral' | 'success' | 'warning' | 'danger'
}) {
  return (
    <span
      className={[
        'inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
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

function PreviewText({
  value,
  emptyLabel
}: {
  value: string
  emptyLabel: string
}) {
  const text = value.trim()

  if (!text) return <span className="text-slate-500">{emptyLabel}</span>

  return <span className="line-clamp-3 break-words">{text}</span>
}

function TagList({ tags }: { tags: string[] }) {
  if (tags.length === 0) {
    return <span className="text-slate-500">No tags</span>
  }

  return (
    <ul className="flex max-w-full flex-wrap gap-2">
      {tags.map((tag, index) => (
        <li
          key={`${tag}-${index}`}
          className="max-w-full break-words rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700"
        >
          {tag}
        </li>
      ))}
    </ul>
  )
}

async function fetchOpsState(signal: AbortSignal): Promise<OpsState> {
  const [snapshotResponse, statusesResponse] = await Promise.all([
    fetch('/snapshot', { signal }),
    fetch('/ops/statuses', { signal })
  ])

  if (!snapshotResponse.ok) {
    throw new Error(`Snapshot request failed with ${snapshotResponse.status}`)
  }

  if (!statusesResponse.ok) {
    throw new Error(`Status list request failed with ${statusesResponse.status}`)
  }

  const data = await snapshotResponse.json()
  const statusesData = (await statusesResponse.json()) as OpsStatusListResponse

  if (!Array.isArray(data)) {
    throw new Error('Snapshot response must be an array')
  }

  if (!Array.isArray(statusesData.statuses) || statusesData.statuses.length === 0) {
    throw new Error('Status list response must include statuses')
  }

  return {
    status: 'ready',
    submissions: data as ReviewerSubmissionSnapshot[],
    statusOptions: statusesData.statuses
  }
}

function compareOpsSubmissions(
  first: ReviewerSubmissionSnapshot,
  second: ReviewerSubmissionSnapshot
) {
  const firstRank = getOpsStateRank(first)
  const secondRank = getOpsStateRank(second)

  if (firstRank !== secondRank) return firstRank - secondRank

  const firstUpdatedAt = getSortableDateValue(first.ops.updated_at)
  const secondUpdatedAt = getSortableDateValue(second.ops.updated_at)

  if (firstUpdatedAt !== secondUpdatedAt) return secondUpdatedAt - firstUpdatedAt

  const firstCreatedAt = getSortableDateValue(first.raw.created_at)
  const secondCreatedAt = getSortableDateValue(second.raw.created_at)

  if (firstCreatedAt !== secondCreatedAt) return secondCreatedAt - firstCreatedAt

  return first.submission_id.localeCompare(second.submission_id)
}

function getOpsStateRank(submission: ReviewerSubmissionSnapshot) {
  if (!hasTouchedOpsState(submission.ops)) return 0
  if (submission.ops.status === 'new') return 1
  if (submission.ops.status === 'in_progress') return 2
  if (submission.ops.status === 'contacted') return 3
  if (submission.ops.status === 'paused') return 4
  if (submission.ops.status === 'reviewed') return 5
  if (submission.ops.status === 'closed') return 6
  return 7
}

function hasTouchedOpsState(ops: SnapshotOpsData) {
  return (
    ops.status !== 'new' ||
    parseSnapshotList(ops.tags).length > 0 ||
    [
      ops.notes,
      ops.contact_tracking,
      ops.updated_at,
      ops.updated_by
    ].some((value) => value.trim() !== '')
  )
}

function matchesOpsFilters(
  submission: ReviewerSubmissionSnapshot,
  filters: {
    searchQuery: string
    statusFilter: OpsStatus | 'all'
    healthFilter: SubmissionHealthState | 'all'
  }
) {
  if (
    filters.statusFilter !== 'all' &&
    submission.ops.status !== filters.statusFilter
  ) {
    return false
  }

  if (
    filters.healthFilter !== 'all' &&
    submission.submission_health_state !== filters.healthFilter
  ) {
    return false
  }

  const normalizedSearchQuery = normalizeFilterText(filters.searchQuery)
  if (normalizedSearchQuery && !getOpsSearchText(submission).includes(normalizedSearchQuery)) {
    return false
  }

  return true
}

function getOpsSearchText(submission: ReviewerSubmissionSnapshot) {
  return normalizeFilterText(
    [
      submission.submission_id,
      submission.raw.full_name,
      submission.raw.email,
      submission.submission_health_state,
      submission.ops.status,
      submission.ops.notes,
      submission.ops.tags,
      submission.ops.contact_tracking,
      submission.ops.updated_at,
      submission.ops.updated_by
    ].join(' ')
  )
}

function getSortableDateValue(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

function normalizeFilterText(value: string) {
  return value.trim().toLowerCase()
}
