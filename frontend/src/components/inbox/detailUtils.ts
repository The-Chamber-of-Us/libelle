import type {
  ParserResultState,
  ResolverResultState,
  SnapshotErrorState,
  SubmissionHealthState
} from '../../types/dashboard'

export type SnapshotTone = 'neutral' | 'success' | 'warning' | 'danger'

const submissionHealthLabels: Record<SubmissionHealthState, string> = {
  complete: 'Complete',
  partial_success: 'Partial success',
  no_resume_ok: 'No resume',
  parser_failed: 'Parser failed',
  resolver_failed: 'Resolver failed',
  pending_processing: 'Pending',
  broken_pipeline: 'Pipeline issue'
}

const parserResultLabels: Record<ParserResultState, string> = {
  not_yet_run: 'Parser not run',
  failed: 'Parser failed',
  skipped: 'Parser skipped',
  empty_success: 'Parser empty',
  available: 'Parser available'
}

const resolverResultLabels: Record<ResolverResultState, string> = {
  not_yet_run: 'Resolver not run',
  failed: 'Resolver failed',
  unavailable_upstream: 'Resolver blocked',
  empty_success: 'Resolver empty',
  available: 'Resolver available'
}

const errorStateLabels: Record<SnapshotErrorState, string> = {
  none: 'No errors',
  present: 'Error present',
  unavailable: 'Errors unavailable'
}

export function formatSubmittedDate(value: string) {
  if (!value.trim()) return 'No date'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  }).format(date)
}

export function formatStatus(status: string) {
  return status.replace(/_/g, ' ')
}

export function formatSubmissionHealthState(state: SubmissionHealthState) {
  return submissionHealthLabels[state]
}

export function formatParserResultState(state: ParserResultState) {
  return parserResultLabels[state]
}

export function formatResolverResultState(state: ResolverResultState) {
  return resolverResultLabels[state]
}

export function formatErrorState(state: SnapshotErrorState) {
  return errorStateLabels[state]
}

export function getSubmissionHealthTone(
  state: SubmissionHealthState
): SnapshotTone {
  if (state === 'complete' || state === 'no_resume_ok') return 'success'
  if (state === 'partial_success' || state === 'pending_processing') {
    return 'warning'
  }
  return 'danger'
}

export function getParserResultTone(state: ParserResultState): SnapshotTone {
  if (state === 'available') return 'success'
  if (state === 'failed') return 'danger'
  return 'neutral'
}

export function getResolverResultTone(state: ResolverResultState): SnapshotTone {
  if (state === 'available') return 'success'
  if (state === 'failed' || state === 'unavailable_upstream') return 'danger'
  return 'neutral'
}

export function getErrorStateTone(state: SnapshotErrorState): SnapshotTone {
  if (state === 'none') return 'success'
  if (state === 'present') return 'danger'
  return 'warning'
}

export function hasSnapshotValue(values: string[]) {
  return values.some((value) => value.trim() !== '')
}

export function getResolverStatusTone(status: string) {
  if (status === 'resolved') return 'success'
  if (status === 'zero_matches') return 'warning'
  return 'neutral'
}

export function getOpsStatusTone(status: string) {
  if (status === 'contacted' || status === 'in_progress') return 'success'
  if (status === 'paused') return 'warning'
  return 'neutral'
}

export function parseSnapshotList(value: string) {
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
