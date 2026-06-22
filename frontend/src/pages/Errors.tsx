import { useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import DashboardTabs from '../components/dashboard/DashboardTabs'
import { formatStatus, formatSubmittedDate } from '../components/inbox/detailUtils'
import type { ReviewerSubmissionSnapshot } from '../types/dashboard'

type ErrorsState =
  | { status: 'loading' }
  | { status: 'ready'; submissions: ReviewerSubmissionSnapshot[] }
  | { status: 'error'; message: string }

type RefreshState =
  | { status: 'idle' }
  | { status: 'refreshing' }
  | { status: 'error'; message: string }

export default function Errors() {
  const [state, setState] = useState<ErrorsState>({ status: 'loading' })
  const [refreshState, setRefreshState] = useState<RefreshState>({ status: 'idle' })

  const errorSubmissions = useMemo(() => {
    if (state.status !== 'ready') return []

    return state.submissions
      .filter((submission) => submission.errors.has_error)
      .sort(compareErrorSubmissions)
  }, [state])

  useEffect(() => {
    const controller = new AbortController()

    async function loadSnapshot() {
      try {
        setState(await fetchErrorsState(controller.signal))
      } catch (error) {
        if (controller.signal.aborted) return

        setState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Unable to load errors'
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
      setState(await fetchErrorsState(controller.signal))
      setRefreshState({ status: 'idle' })
    } catch (error) {
      setRefreshState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Unable to refresh errors.'
      })
    }
  }

  const isRefreshing = refreshState.status === 'refreshing'

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
                  Errors
                </h1>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  Latest submission-level failures reported by the backend snapshot.
                </p>
              </div>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                onClick={handleRefresh}
                disabled={isRefreshing || state.status === 'loading'}
                title="Refresh errors"
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
          <div className="border-b border-slate-200 px-4 py-4 sm:px-5">
            <h2 className="font-semibold text-slate-950">Reported errors</h2>
            {state.status === 'ready' && (
              <p className="mt-1 text-sm text-slate-500">
                {errorSubmissions.length} of {state.submissions.length} submissions have
                an error
              </p>
            )}
            {refreshState.status === 'error' && (
              <p className="mt-3 text-sm font-medium text-rose-700">
                Refresh failed: {refreshState.message}
              </p>
            )}
          </div>

          {state.status === 'loading' && (
            <div className="px-5 py-10 text-sm text-slate-600">Loading errors...</div>
          )}

          {state.status === 'error' && (
            <div className="px-5 py-10 text-sm text-rose-700">{state.message}</div>
          )}

          {state.status === 'ready' && errorSubmissions.length === 0 && (
            <div className="px-5 py-10 text-sm text-slate-600">No errors reported</div>
          )}

          {state.status === 'ready' && errorSubmissions.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                  <tr>
                    <th scope="col" className="px-4 py-3 sm:px-5">
                      Submitted
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Submission
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Stage
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Error code
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Summary
                    </th>
                    <th scope="col" className="px-4 py-3 sm:px-5">
                      Context
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {errorSubmissions.map((submission) => (
                    <ErrorRow key={submission.submission_id} submission={submission} />
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

function ErrorRow({ submission }: { submission: ReviewerSubmissionSnapshot }) {
  const stage = submission.errors.latest_error_stage.trim()
  const errorCode = submission.errors.latest_error_code.trim()
  const summary = submission.errors.latest_error_summary.trim()
  const displayName = submission.raw.full_name.trim() || 'Unnamed submission'

  return (
    <tr>
      <td className="whitespace-nowrap px-4 py-4 align-top text-slate-700 sm:px-5">
        {formatSubmittedDate(submission.raw.created_at)}
      </td>
      <td className="max-w-[15rem] px-4 py-4 align-top">
        <div className="font-medium text-slate-950">{displayName}</div>
        <div className="mt-1 break-all font-mono text-xs text-slate-600">
          {submission.submission_id}
        </div>
      </td>
      <td className="px-4 py-4 align-top">
        <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-slate-600">
          {stage ? formatStatus(stage) : 'Unknown stage'}
        </span>
      </td>
      <td className="max-w-[12rem] px-4 py-4 align-top">
        {errorCode ? (
          <span className="break-all font-mono text-xs text-slate-700">{errorCode}</span>
        ) : (
          <span className="text-slate-500">No error code available</span>
        )}
      </td>
      <td className="max-w-[24rem] px-4 py-4 align-top text-slate-700">
        {summary ? (
          <span className="line-clamp-3 break-words">{summary}</span>
        ) : (
          <span className="text-slate-500">No error summary available</span>
        )}
      </td>
      <td className="max-w-[15rem] px-4 py-4 align-top text-slate-700 sm:px-5">
        <dl className="grid gap-2 text-xs">
          <ContextField label="Upload" value={submission.raw.resume_status} />
          <ContextField
            label="Parser"
            value={
              submission.parsed.parser_state === 'pending'
                ? 'No linked parser result'
                : formatStatus(submission.parsed.parser_state)
            }
          />
          <ContextField label="Resolver" value={formatStatus(submission.resolved.resolver_state)} />
          <ContextField label="Workflow" value={formatStatus(submission.ops.status)} />
        </dl>
      </td>
    </tr>
  )
}

function ContextField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-slate-700">{value.trim() || 'Not available'}</dd>
    </div>
  )
}

async function fetchErrorsState(signal: AbortSignal): Promise<ErrorsState> {
  const response = await fetch('/snapshot', { signal })

  if (!response.ok) {
    throw new Error(`Snapshot request failed with ${response.status}`)
  }

  const data = await response.json()

  if (!Array.isArray(data)) {
    throw new Error('Snapshot response must be an array')
  }

  return {
    status: 'ready',
    submissions: data as ReviewerSubmissionSnapshot[]
  }
}

function compareErrorSubmissions(
  first: ReviewerSubmissionSnapshot,
  second: ReviewerSubmissionSnapshot
) {
  const firstCreatedAt = getSortableDateValue(first.raw.created_at)
  const secondCreatedAt = getSortableDateValue(second.raw.created_at)

  if (firstCreatedAt !== secondCreatedAt) return secondCreatedAt - firstCreatedAt

  return first.submission_id.localeCompare(second.submission_id)
}

function getSortableDateValue(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}
