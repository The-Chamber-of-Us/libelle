import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AlertTriangle, Inbox as InboxIcon, RefreshCw, Search, X } from 'lucide-react'
import DashboardTabs from '../components/dashboard/DashboardTabs'
import InboxDetailPanel from '../components/inbox/InboxDetailPanel'
import InboxSubmissionRow from '../components/inbox/InboxSubmissionRow'
import {
  formatErrorState,
  formatParserResultState,
  formatResolverResultState,
  formatStatus,
  formatSubmissionHealthState,
  parseSnapshotList
} from '../components/inbox/detailUtils'
import type { StatusSaveState } from '../components/inbox/WorkflowSection'
import type {
  OpsDashboardUpdateResponse,
  OpsStatus,
  OpsStatusListResponse,
  ReviewerSubmissionSnapshot,
  SubmissionHealthState
} from '../types/dashboard'

type InboxState =
  | { status: 'loading' }
  | {
      status: 'ready'
      submissions: ReviewerSubmissionSnapshot[]
      statusOptions: OpsStatus[]
    }
  | { status: 'error'; message: string }

type PendingStatusUpdate = {
  submissionId: string
  status: OpsStatus
} | null

type RefreshState =
  | { status: 'idle' }
  | { status: 'refreshing' }
  | { status: 'error'; message: string }

export default function Inbox() {
  const [state, setState] = useState<InboxState>({ status: 'loading' })
  const [refreshState, setRefreshState] = useState<RefreshState>({ status: 'idle' })
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<OpsStatus | 'all'>('all')
  const [healthFilter, setHealthFilter] = useState<SubmissionHealthState | 'all'>(
    'all'
  )
  const [locationFilter, setLocationFilter] = useState('')
  const [statusSaveState, setStatusSaveState] = useState<StatusSaveState>({
    status: 'idle'
  })
  const [statusSaveSubmissionId, setStatusSaveSubmissionId] = useState<string | null>(
    null
  )
  const [notesSaveState, setNotesSaveState] = useState<StatusSaveState>({
    status: 'idle'
  })
  const [notesSaveSubmissionId, setNotesSaveSubmissionId] = useState<string | null>(
    null
  )
  const [pendingStatusUpdate, setPendingStatusUpdate] =
    useState<PendingStatusUpdate>(null)

  const filteredSubmissions = useMemo(() => {
    if (state.status !== 'ready') return []

    return state.submissions
      .filter((submission) =>
        matchesInboxFilters(submission, {
          searchQuery,
          statusFilter,
          healthFilter,
          locationFilter
        })
      )
      .sort(compareInboxSubmissions)
  }, [healthFilter, locationFilter, searchQuery, state, statusFilter])

  const healthOptions = useMemo(() => {
    if (state.status !== 'ready') return []

    return Array.from(
      new Set(
        state.submissions
          .map((submission) => submission.submission_health_state)
          .filter(Boolean)
      )
    ).sort((first, second) =>
      formatSubmissionHealthState(first).localeCompare(formatSubmissionHealthState(second))
    )
  }, [state])

  const selectedSubmission = useMemo(() => {
    if (state.status !== 'ready' || selectedSubmissionId === null) return null

    return (
      filteredSubmissions.find(
        (submission) => submission.submission_id === selectedSubmissionId
      ) ?? null
    )
  }, [filteredSubmissions, selectedSubmissionId, state.status])

  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    statusFilter !== 'all' ||
    healthFilter !== 'all' ||
    locationFilter.trim() !== ''

  const statusOptions = state.status === 'ready' ? state.statusOptions : []
  const selectedStatusSaveState =
    statusSaveSubmissionId === selectedSubmissionId
      ? statusSaveState
      : { status: 'idle' as const }
  const selectedNotesSaveState =
    notesSaveSubmissionId === selectedSubmissionId
      ? notesSaveState
      : { status: 'idle' as const }
  const selectedPendingStatus =
    pendingStatusUpdate?.submissionId === selectedSubmissionId
      ? pendingStatusUpdate.status
      : null
  const isRefreshing = refreshState.status === 'refreshing'

  const clearFilters = () => {
    setSearchQuery('')
    setStatusFilter('all')
    setHealthFilter('all')
    setLocationFilter('')
  }

  useEffect(() => {
    const controller = new AbortController()

    async function loadSnapshot() {
      try {
        setState(await fetchInboxState(controller.signal))
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

  async function handleRefresh() {
    const controller = new AbortController()
    setRefreshState({ status: 'refreshing' })

    try {
      setState(await fetchInboxState(controller.signal))
      setRefreshState({ status: 'idle' })
    } catch (error) {
      setRefreshState({
        status: 'error',
        message:
          error instanceof Error ? error.message : 'Unable to refresh submissions.'
      })
    }
  }

  async function handleStatusChange(nextStatus: OpsStatus) {
    if (
      state.status !== 'ready' ||
      selectedSubmission === null ||
      nextStatus === selectedSubmission.ops.status
    ) {
      return
    }

    const submissionId = selectedSubmission.submission_id
    setPendingStatusUpdate({ submissionId, status: nextStatus })
    setStatusSaveSubmissionId(submissionId)
    setStatusSaveState({ status: 'saving', message: 'Saving status...' })

    try {
      const response = await fetch('/ops/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          submission_id: submissionId,
          status: nextStatus
        })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(getOpsUpdateErrorMessage(data, response.status))
      }

      const updateResponse = data as OpsDashboardUpdateResponse
      if (updateResponse.status !== 'updated' || updateResponse.submission_id !== submissionId) {
        throw new Error('Status update returned an unexpected response')
      }

      applyConfirmedOpsUpdate(submissionId, updateResponse)
      setStatusSaveState({ status: 'saved', message: 'Status saved.' })
    } catch (error) {
      setStatusSaveState({
        status: 'error',
        message:
          error instanceof Error ? error.message : 'Unable to save workflow status.'
      })
    } finally {
      setPendingStatusUpdate(null)
    }
  }

  async function handleNotesSave(nextNotes: string) {
    if (state.status !== 'ready' || selectedSubmission === null) {
      return
    }

    const submissionId = selectedSubmission.submission_id
    setNotesSaveSubmissionId(submissionId)
    setNotesSaveState({ status: 'saving', message: 'Saving notes...' })

    try {
      const response = await fetch('/ops/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          submission_id: submissionId,
          notes: nextNotes
        })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(getOpsUpdateErrorMessage(data, response.status, 'Notes save'))
      }

      const updateResponse = data as OpsDashboardUpdateResponse
      if (updateResponse.status !== 'updated' || updateResponse.submission_id !== submissionId) {
        throw new Error('Notes update returned an unexpected response')
      }

      applyConfirmedOpsUpdate(submissionId, updateResponse)
      setNotesSaveState({ status: 'saved', message: 'Notes saved.' })
    } catch (error) {
      setNotesSaveState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Unable to save notes.'
      })
    }
  }

  function applyConfirmedOpsUpdate(
    submissionId: string,
    updateResponse: OpsDashboardUpdateResponse
  ) {
    setState((currentState) => {
      if (currentState.status !== 'ready') return currentState

      return {
        ...currentState,
        submissions: currentState.submissions.map((submission) =>
          submission.submission_id === submissionId
            ? { ...submission, ops: updateResponse.ops }
            : submission
        )
      }
    })
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-6 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <header className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-semibold uppercase tracking-[0.12em] text-libelle-indigo">
              Reviewer Inbox
            </p>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <h1 className="text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
                Submissions
              </h1>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-libelle-indigo bg-libelle-indigo px-3 text-sm font-semibold text-white transition hover:bg-libelle-indigo/90 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                onClick={handleRefresh}
                disabled={isRefreshing || state.status === 'loading'}
                title="Refresh submissions"
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

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
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
                      placeholder="Name, email, skills, tags, notes"
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

                <label className="grid gap-1 text-sm font-medium text-slate-700 lg:w-48">
                  Health
                  <select
                    className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20"
                    value={healthFilter}
                    onChange={(event) =>
                      setHealthFilter(
                        event.target.value as SubmissionHealthState | 'all'
                      )
                    }
                  >
                    <option value="all">All health states</option>
                    {healthOptions.map((healthState) => (
                      <option key={healthState} value={healthState}>
                        {formatSubmissionHealthState(healthState)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="grid gap-1 text-sm font-medium text-slate-700 lg:w-52">
                  Location
                  <input
                    className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20"
                    type="search"
                    value={locationFilter}
                    onChange={(event) => setLocationFilter(event.target.value)}
                    placeholder="City, state, region"
                  />
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

            <div className="grid gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 sm:grid-cols-[minmax(0,1.5fr)_minmax(12rem,1fr)_auto] sm:px-5">
              <span>Applicant</span>
              <span>Top Signals</span>
              <span className="sm:text-right">Status</span>
            </div>

            {state.status === 'loading' && (
              <InboxListState
                icon={<RefreshCw className="h-5 w-5 animate-spin" aria-hidden="true" />}
                title="Loading submissions"
                message="Checking the current reviewer snapshot."
              />
            )}

            {state.status === 'error' && (
              <InboxListState
                icon={<AlertTriangle className="h-5 w-5" aria-hidden="true" />}
                title="Snapshot could not load"
                message={`The reviewer snapshot could not be loaded. ${state.message}`}
                tone="error"
              />
            )}

            {state.status === 'ready' && state.submissions.length === 0 && (
              <InboxListState
                icon={<InboxIcon className="h-5 w-5" aria-hidden="true" />}
                title="No submissions yet"
                message="The reviewer inbox is empty because no submissions are in the snapshot."
              />
            )}

            {state.status === 'ready' &&
              state.submissions.length > 0 &&
              filteredSubmissions.length === 0 && (
                <InboxListState
                  icon={<Search className="h-5 w-5" aria-hidden="true" />}
                  title="No submissions match these filters"
                  message="Submissions still exist in the snapshot. Clear the local filters to show every record again."
                  action={
                    <button
                      type="button"
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-libelle-indigo bg-libelle-indigo px-3 text-sm font-semibold text-white transition hover:bg-libelle-indigo/90"
                      onClick={clearFilters}
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
                      Clear filters
                    </button>
                  }
                />
              )}

            {state.status === 'ready' &&
              filteredSubmissions.map((submission) => (
                <InboxSubmissionRow
                  key={submission.submission_id}
                  submission={submission}
                  isSelected={submission.submission_id === selectedSubmissionId}
                  onSelect={() => setSelectedSubmissionId(submission.submission_id)}
                />
              ))}
          </section>

          <InboxDetailPanel
            submission={selectedSubmission}
            statusOptions={statusOptions}
            pendingStatus={selectedPendingStatus}
            statusSaveState={selectedStatusSaveState}
            notesSaveState={selectedNotesSaveState}
            onStatusChange={handleStatusChange}
            onNotesSave={handleNotesSave}
          />
        </div>
      </div>
    </main>
  )
}

function InboxListState({
  icon,
  title,
  message,
  action,
  tone = 'neutral'
}: {
  icon: ReactNode
  title: string
  message: string
  action?: ReactNode
  tone?: 'neutral' | 'error'
}) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center px-5 py-10 text-center">
      <div
        className={[
          'mb-3 inline-flex h-11 w-11 items-center justify-center rounded-full border',
          tone === 'error'
            ? 'border-rose-200 bg-rose-50 text-rose-700'
            : 'border-slate-200 bg-slate-50 text-slate-600'
        ].join(' ')}
      >
        {icon}
      </div>
      <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      <p
        className={[
          'mt-1 max-w-md text-sm leading-6',
          tone === 'error' ? 'text-rose-700' : 'text-slate-600'
        ].join(' ')}
      >
        {message}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

const actionableStatusRank: Record<OpsStatus, number> = {
  new: 2,
  paused: 3,
  in_progress: 4,
  contacted: 5,
  reviewed: 6,
  closed: 7
}

async function fetchInboxState(signal: AbortSignal): Promise<InboxState> {
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

function compareInboxSubmissions(
  first: ReviewerSubmissionSnapshot,
  second: ReviewerSubmissionSnapshot
) {
  const firstRank = getInboxActionableRank(first)
  const secondRank = getInboxActionableRank(second)

  if (firstRank !== secondRank) return firstRank - secondRank

  const firstCreatedAt = getSortableDateValue(first.raw?.created_at)
  const secondCreatedAt = getSortableDateValue(second.raw?.created_at)

  if (firstCreatedAt !== secondCreatedAt) return secondCreatedAt - firstCreatedAt

  return first.submission_id.localeCompare(second.submission_id)
}

function getInboxActionableRank(submission: ReviewerSubmissionSnapshot) {
  if (submission.errors?.has_error) return 0
  if (hasResolverAttentionSignal(submission)) return 1

  const status = submission.ops?.status
  return actionableStatusRank[status] ?? actionableStatusRank.new
}

function hasResolverAttentionSignal(submission: ReviewerSubmissionSnapshot) {
  return (
    submission.resolved?.resolver_state === 'zero_matches' ||
    parseSnapshotList(safeText(submission.resolved?.unknown_skills)).length > 0
  )
}

function getSortableDateValue(value: unknown) {
  if (typeof value !== 'string') return 0

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

function getOpsUpdateErrorMessage(data: unknown, status: number, label = 'Status update') {
  if (isErrorPayload(data)) {
    return data.detail.message ?? `${label} failed with ${status}`
  }

  return `${label} failed with ${status}`
}

function isErrorPayload(data: unknown): data is { detail: { message?: string } } {
  if (typeof data !== 'object' || data === null || !('detail' in data)) return false

  const detail = (data as { detail: unknown }).detail
  return typeof detail === 'object' && detail !== null
}

function matchesInboxFilters(
  submission: ReviewerSubmissionSnapshot,
  filters: {
    searchQuery: string
    statusFilter: OpsStatus | 'all'
    healthFilter: SubmissionHealthState | 'all'
    locationFilter: string
  }
) {
  const submissionStatus = safeText(submission.ops?.status)

  if (filters.statusFilter !== 'all' && submissionStatus !== filters.statusFilter) {
    return false
  }

  if (
    filters.healthFilter !== 'all' &&
    submission.submission_health_state !== filters.healthFilter
  ) {
    return false
  }

  const normalizedLocationFilter = normalizeFilterText(filters.locationFilter)
  if (
    normalizedLocationFilter &&
    !normalizeFilterText(getPreferredLocation(submission)).includes(
      normalizedLocationFilter
    )
  ) {
    return false
  }

  const normalizedSearchQuery = normalizeFilterText(filters.searchQuery)
  if (
    normalizedSearchQuery &&
    !getInboxSearchText(submission).includes(normalizedSearchQuery)
  ) {
    return false
  }

  return true
}

function getInboxSearchText(submission: ReviewerSubmissionSnapshot) {
  return normalizeFilterText(
    [
      submission.submission_id,
      submission.raw?.full_name,
      submission.raw?.email,
      submission.raw?.location_raw,
      submission.raw?.timezone,
      submission.raw?.skills_raw,
      submission.raw?.interests,
      submission.raw?.experience_level,
      submission.raw?.availability,
      submission.raw?.motivation,
      submission.raw?.resume_filename,
      submission.raw?.resume_status,
      submission.submission_health_state,
      formatSubmissionHealthState(submission.submission_health_state),
      submission.parsed?.parser_state,
      submission.parsed?.parser_result_state,
      submission.parsed
        ? formatParserResultState(submission.parsed.parser_result_state)
        : '',
      submission.parsed?.parsed_skills_raw,
      submission.parsed?.parsed_location_raw,
      submission.resolved?.resolver_state,
      submission.resolved?.resolver_result_state,
      submission.resolved
        ? formatResolverResultState(submission.resolved.resolver_result_state)
        : '',
      submission.resolved?.resolved_skill_ids,
      submission.resolved?.unknown_skills,
      submission.ops?.status,
      submission.ops?.notes,
      submission.ops?.tags,
      submission.ops?.contact_tracking,
      submission.errors?.error_state,
      submission.errors ? formatErrorState(submission.errors.error_state) : '',
      submission.errors?.latest_error_summary,
      submission.errors?.latest_error_stage,
      submission.errors?.latest_error_code
    ]
      .map(safeText)
      .join(' ')
  )
}

function getPreferredLocation(submission: ReviewerSubmissionSnapshot) {
  return (
    safeText(submission.parsed?.parsed_location_raw).trim() ||
    safeText(submission.raw?.location_raw).trim()
  )
}

function normalizeFilterText(value: unknown) {
  return safeText(value).trim().toLowerCase()
}

function safeText(value: unknown) {
  return typeof value === 'string' ? value : ''
}
