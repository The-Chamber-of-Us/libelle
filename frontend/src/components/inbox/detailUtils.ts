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
