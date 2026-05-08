import { useEffect, useState } from 'react'
import InboxSubmissionRow from '../components/inbox/InboxSubmissionRow'
import type { ReviewerSubmissionSnapshot } from '../types/dashboard'

type InboxState =
  | { status: 'loading' }
  | { status: 'ready'; submissions: ReviewerSubmissionSnapshot[] }
  | { status: 'error'; message: string }

export default function Inbox() {
  const [state, setState] = useState<InboxState>({ status: 'loading' })

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
              />
            ))}
        </section>
      </div>
    </main>
  )
}
