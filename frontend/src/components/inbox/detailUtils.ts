import type { SubmissionHealthState } from '../../types/dashboard'

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

export function formatSubmissionHealthState(status: SubmissionHealthState) {
  return formatStatus(status)
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

export function getSubmissionHealthTone(status: SubmissionHealthState) {
  if (status === 'complete' || status === 'no_resume_ok') return 'success'
  if (status === 'partial_success' || status === 'pending_processing') return 'warning'
  if (
    status === 'parser_failed' ||
    status === 'resolver_failed' ||
    status === 'broken_pipeline'
  ) {
    return 'danger'
  }

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
