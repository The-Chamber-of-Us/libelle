import { useEffect, useRef, useState } from 'react'
import { AlertCircle, ExternalLink, FileText, Loader2 } from 'lucide-react'
import type { OpsStatus, ReviewerSubmissionSnapshot } from '../../types/dashboard'
import { DetailField, StateCallout } from './DetailPrimitives'
import ParsedOutputSection from './ParsedOutputSection'
import RawSubmissionSection from './RawSubmissionSection'
import ResolvedOutputSection from './ResolvedOutputSection'
import WorkflowSection, { type StatusSaveState } from './WorkflowSection'
import { formatSubmittedDate } from './detailUtils'

export default function InboxDetailPanel({
  submission,
  statusOptions,
  pendingStatus,
  statusSaveState,
  notesSaveState,
  onStatusChange,
  onNotesSave
}: {
  submission: ReviewerSubmissionSnapshot | null
  statusOptions: OpsStatus[]
  pendingStatus: OpsStatus | null
  statusSaveState: StatusSaveState
  notesSaveState: StatusSaveState
  onStatusChange: (status: OpsStatus) => void
  onNotesSave: (notes: string) => void
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

      <WorkflowSection
        submission={submission}
        statusOptions={statusOptions}
        pendingStatus={pendingStatus}
        statusSaveState={statusSaveState}
        notesSaveState={notesSaveState}
        onStatusChange={onStatusChange}
        onNotesSave={onNotesSave}
      />
      <ResumeAccessSection submission={submission} />
      <RawSubmissionSection submission={submission} />
      <ParsedOutputSection submission={submission} />
      <ResolvedOutputSection submission={submission} />
    </aside>
  )
}

type ResumeAccessState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'opened'; message: string }
  | { status: 'error'; message: string }

type ResumeAvailability =
  | { state: 'uploaded' }
  | { state: 'missing'; message: string }
  | { state: 'failed'; message: string }
  | { state: 'unknown'; message: string }

function ResumeAccessSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  const [accessState, setAccessState] = useState<ResumeAccessState>({ status: 'idle' })
  const activeRequestRef = useRef(0)
  const activeAbortControllerRef = useRef<AbortController | null>(null)
  const activeResumeWindowRef = useRef<Window | null>(null)
  const resumeStatus = submission.raw.resume_status.trim().toLowerCase()
  const resumeFilename = submission.raw.resume_filename.trim()
  const resumeAvailability = getResumeAvailability(resumeStatus)
  const hasUploadedResume = resumeAvailability.state === 'uploaded'
  const displayFilename = resumeFilename || 'Filename unavailable'
  const downloadFilename = resumeFilename || `${submission.submission_id}-resume.pdf`
  const isOpening = accessState.status === 'loading'

  useEffect(() => {
    cancelActiveResumeRequest()
    setAccessState({ status: 'idle' })

    return cancelActiveResumeRequest
  }, [submission.submission_id])

  async function handleResumeOpen() {
    cancelActiveResumeRequest()

    const requestId = activeRequestRef.current + 1
    activeRequestRef.current = requestId
    const abortController = new AbortController()
    activeAbortControllerRef.current = abortController

    setAccessState({ status: 'loading' })
    const resumeWindow = window.open('', '_blank')
    activeResumeWindowRef.current = resumeWindow
    if (resumeWindow !== null) {
      resumeWindow.opener = null
    }

    try {
      const response = await fetch(
        `/resumes/${encodeURIComponent(submission.submission_id)}`,
        { signal: abortController.signal }
      )

      if (!response.ok) {
        throw new Error(await getResumeAccessErrorMessage(response))
      }

      const resumeBlob = await response.blob()
      const resumeUrl = URL.createObjectURL(resumeBlob)

      if (!isActiveResumeRequest(requestId, abortController.signal)) {
        URL.revokeObjectURL(resumeUrl)
        resumeWindow?.close()
        return
      }

      if (resumeWindow === null) {
        const downloadLink = document.createElement('a')
        downloadLink.href = resumeUrl
        downloadLink.download = downloadFilename
        downloadLink.rel = 'noreferrer'
        downloadLink.click()
        setAccessState({
          status: 'opened',
          message: 'Resume download started.'
        })
      } else {
        resumeWindow.location.href = resumeUrl
        setAccessState({
          status: 'opened',
          message: 'Resume opened in a new tab.'
        })
      }

      activeAbortControllerRef.current = null
      activeResumeWindowRef.current = null
      window.setTimeout(() => URL.revokeObjectURL(resumeUrl), 60_000)
    } catch (error) {
      if (!isActiveResumeRequest(requestId, abortController.signal)) {
        resumeWindow?.close()
        return
      }

      activeAbortControllerRef.current = null
      activeResumeWindowRef.current = null
      setAccessState({
        status: 'error',
        message:
          error instanceof Error
            ? error.message
            : 'Resume could not be opened for this submission.'
      })
      resumeWindow?.close()
    }
  }

  return (
    <section className="border-t border-slate-200 px-5 py-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-libelle-indigo">
            Resume
          </h3>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Uploaded file associated with this submission.
          </p>
        </div>
        {hasUploadedResume && (
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-libelle-indigo bg-libelle-indigo px-3 text-sm font-semibold text-white transition hover:bg-libelle-indigo/90 disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleResumeOpen}
            disabled={isOpening}
            title="Open resume"
          >
            {isOpening ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
            )}
            {isOpening ? 'Opening' : 'Open Resume'}
          </button>
        )}
      </div>

      {hasUploadedResume ? (
        <div className="grid gap-3">
          <div className="flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            <FileText className="mt-0.5 h-4 w-4 flex-none text-libelle-indigo" aria-hidden="true" />
            <span className="break-words">
              Uploaded resume: <span className="font-medium">{displayFilename}</span>
            </span>
          </div>
          <ResumeAccessStatus accessState={accessState} />
        </div>
      ) : resumeAvailability.state === 'failed' ? (
        <StateCallout tone="danger">
          {resumeAvailability.message}
        </StateCallout>
      ) : resumeAvailability.state === 'unknown' ? (
        <StateCallout tone="warning">{resumeAvailability.message}</StateCallout>
      ) : (
        <StateCallout tone="neutral">{resumeAvailability.message}</StateCallout>
      )}
    </section>
  )

  function isActiveResumeRequest(requestId: number, signal: AbortSignal) {
    return activeRequestRef.current === requestId && !signal.aborted
  }

  function cancelActiveResumeRequest() {
    activeRequestRef.current += 1
    activeAbortControllerRef.current?.abort()
    activeAbortControllerRef.current = null
    activeResumeWindowRef.current?.close()
    activeResumeWindowRef.current = null
  }
}

function getResumeAvailability(resumeStatus: string): ResumeAvailability {
  if (resumeStatus === 'uploaded') {
    return { state: 'uploaded' }
  }

  if (resumeStatus === '' || resumeStatus === 'missing') {
    return {
      state: 'missing',
      message: 'No resume was provided.'
    }
  }

  if (resumeStatus === 'failed') {
    return {
      state: 'failed',
      message: 'A resume was provided, but Libelle failed to store it.'
    }
  }

  return {
    state: 'unknown',
    message: 'Resume availability is unknown for this submission.'
  }
}

function ResumeAccessStatus({
  accessState
}: {
  accessState: ResumeAccessState
}) {
  if (accessState.status === 'error') {
    return (
      <p
        className="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm leading-5 text-rose-700"
        role="status"
        aria-live="polite"
      >
        <AlertCircle className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
        {accessState.message}
      </p>
    )
  }

  if (accessState.status === 'opened') {
    return (
      <p
        className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm leading-5 text-emerald-700"
        role="status"
        aria-live="polite"
      >
        {accessState.message}
      </p>
    )
  }

  return null
}

async function getResumeAccessErrorMessage(response: Response) {
  const fallbackMessage =
    response.status === 404
      ? 'Resume is unavailable for this submission.'
      : `Resume request failed with ${response.status}.`

  try {
    const data = await response.json()
    if (isResumeAccessErrorPayload(data)) {
      return data.detail.message || fallbackMessage
    }
  } catch {
    return fallbackMessage
  }

  return fallbackMessage
}

function isResumeAccessErrorPayload(
  data: unknown
): data is { detail: { message?: string } } {
  if (typeof data !== 'object' || data === null || !('detail' in data)) {
    return false
  }

  const detail = (data as { detail: unknown }).detail
  return typeof detail === 'object' && detail !== null
}
