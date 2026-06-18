import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, RefreshCw, Search, X } from 'lucide-react'
import DashboardTabs from '../components/dashboard/DashboardTabs'
import {
  DetailField,
  ListDetailField,
  StateCallout
} from '../components/inbox/DetailPrimitives'
import {
  formatStatus,
  formatSubmittedDate,
  getResolverStatusTone,
  hasSnapshotValue,
  parseSnapshotList
} from '../components/inbox/detailUtils'
import type {
  ParserState,
  ResolverState,
  ReviewerSubmissionSnapshot
} from '../types/dashboard'

type ParserResultsState =
  | { status: 'loading' }
  | { status: 'ready'; submissions: ReviewerSubmissionSnapshot[] }
  | { status: 'error'; message: string }

type RefreshState =
  | { status: 'idle' }
  | { status: 'refreshing' }
  | { status: 'error'; message: string }

type ParserFilter = ParserState | 'all'
type ResolverFilter = ResolverState | 'all'

export default function ParserResults() {
  const [state, setState] = useState<ParserResultsState>({ status: 'loading' })
  const [refreshState, setRefreshState] = useState<RefreshState>({ status: 'idle' })
  const [expandedSubmissionId, setExpandedSubmissionId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [parserFilter, setParserFilter] = useState<ParserFilter>('all')
  const [resolverFilter, setResolverFilter] = useState<ResolverFilter>('all')

  const filteredSubmissions = useMemo(() => {
    if (state.status !== 'ready') return []

    return state.submissions
      .filter((submission) =>
        matchesParserResultsFilters(submission, {
          searchQuery,
          parserFilter,
          resolverFilter
        })
      )
      .sort(compareParserResults)
  }, [parserFilter, resolverFilter, searchQuery, state])

  const hasActiveFilters =
    searchQuery.trim() !== '' || parserFilter !== 'all' || resolverFilter !== 'all'
  const isRefreshing = refreshState.status === 'refreshing'

  useEffect(() => {
    const controller = new AbortController()

    async function loadSnapshot() {
      try {
        setState(await fetchParserResultsState(controller.signal))
      } catch (error) {
        if (controller.signal.aborted) return

        setState({
          status: 'error',
          message:
            error instanceof Error ? error.message : 'Unable to load parser results'
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
      setState(await fetchParserResultsState(controller.signal))
      setRefreshState({ status: 'idle' })
    } catch (error) {
      setRefreshState({
        status: 'error',
        message:
          error instanceof Error ? error.message : 'Unable to refresh parser results.'
      })
    }
  }

  function clearFilters() {
    setSearchQuery('')
    setParserFilter('all')
    setResolverFilter('all')
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
                  Parser Results
                </h1>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  Snapshot view of parser and resolver output for inspection.
                </p>
              </div>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                onClick={handleRefresh}
                disabled={isRefreshing || state.status === 'loading'}
                title="Refresh parser results"
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
                    placeholder="Name, submission ID, parser run, skills"
                  />
                </span>
              </label>

              <label className="grid gap-1 text-sm font-medium text-slate-700 lg:w-44">
                Parser
                <select
                  className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20"
                  value={parserFilter}
                  onChange={(event) =>
                    setParserFilter(event.target.value as ParserFilter)
                  }
                >
                  <option value="all">All parser states</option>
                  <option value="pending">No parser result</option>
                  <option value="complete">Parser result</option>
                </select>
              </label>

              <label className="grid gap-1 text-sm font-medium text-slate-700 lg:w-48">
                Resolver
                <select
                  className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-libelle-indigo focus:ring-2 focus:ring-libelle-indigo/20"
                  value={resolverFilter}
                  onChange={(event) =>
                    setResolverFilter(event.target.value as ResolverFilter)
                  }
                >
                  <option value="all">All resolver states</option>
                  <option value="not_run">Not run</option>
                  <option value="resolved">Resolved</option>
                  <option value="zero_matches">Zero matches</option>
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
              Loading parser results...
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
                No parser results match the current filters.
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
                      Parser Run
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Parser
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Parsed Output
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Resolved Output
                    </th>
                    <th scope="col" className="px-4 py-3">
                      Unresolved
                    </th>
                    <th scope="col" className="px-4 py-3 text-right sm:px-5">
                      Detail
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {filteredSubmissions.map((submission) => {
                    const isExpanded =
                      expandedSubmissionId === submission.submission_id

                    return (
                      <ParserResultsRow
                        key={submission.submission_id}
                        submission={submission}
                        isExpanded={isExpanded}
                        onToggle={() =>
                          setExpandedSubmissionId(
                            isExpanded ? null : submission.submission_id
                          )
                        }
                      />
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}

function ParserResultsRow({
  submission,
  isExpanded,
  onToggle
}: {
  submission: ReviewerSubmissionSnapshot
  isExpanded: boolean
  onToggle: () => void
}) {
  const parsed = submission.parsed
  const resolved = submission.resolved
  const hasParserResult = parsed.parser_state === 'complete'
  const resolvedSkillIds = parseSnapshotList(resolved.resolved_skill_ids)
  const unknownSkills = parseSnapshotList(resolved.unknown_skills)
  const displayName = submission.raw.full_name.trim() || 'Unnamed submission'

  return (
    <>
      <tr className={isExpanded ? 'bg-indigo-50/40' : 'bg-white'}>
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
        <td className="max-w-[10rem] px-4 py-4 align-top">
          {hasParserResult ? (
            <span className="break-all font-mono text-xs text-slate-700">
              {parsed.parser_run_id.trim() || 'Not provided'}
            </span>
          ) : (
            <span className="text-slate-500">No parser result yet</span>
          )}
        </td>
        <td className="px-4 py-4 align-top">
          <StatusBadge
            label={hasParserResult ? formatStatus(parsed.parser_state) : 'No result'}
            tone={hasParserResult ? 'success' : 'neutral'}
          />
          {parsed.parser_confidence.trim() && (
            <div className="mt-2 text-xs text-slate-500">
              Confidence {parsed.parser_confidence}
            </div>
          )}
        </td>
        <td className="max-w-[18rem] px-4 py-4 align-top text-slate-700">
          {hasParserResult ? (
            <PreviewText
              value={getParsedPreview(submission)}
              emptyLabel="Parser produced no recognizable structured output"
            />
          ) : (
            <span className="text-slate-500">No parser result yet</span>
          )}
        </td>
        <td className="max-w-[18rem] px-4 py-4 align-top text-slate-700">
          {resolved.resolver_state === 'not_run' ? (
            <span className="text-slate-500">No resolved skills available</span>
          ) : (
            <PreviewText
              value={resolvedSkillIds.join(', ')}
              emptyLabel="No resolved skills available"
            />
          )}
        </td>
        <td className="max-w-[14rem] px-4 py-4 align-top text-slate-700">
          <PreviewText
            value={unknownSkills.join(', ')}
            emptyLabel="No unresolved items reported"
          />
        </td>
        <td className="px-4 py-4 text-right align-top sm:px-5">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 transition hover:bg-slate-50 hover:text-slate-950"
            onClick={onToggle}
            aria-expanded={isExpanded}
            title={isExpanded ? 'Collapse details' : 'Expand details'}
          >
            <ChevronDown
              className={[
                'h-4 w-4 transition-transform',
                isExpanded ? 'rotate-180' : ''
              ].join(' ')}
              aria-hidden="true"
            />
            <span className="sr-only">
              {isExpanded ? 'Collapse details' : 'Expand details'}
            </span>
          </button>
        </td>
      </tr>

      {isExpanded && (
        <tr className="bg-white">
          <td colSpan={8} className="px-4 py-5 sm:px-5">
            <ParserResultDetails submission={submission} />
          </td>
        </tr>
      )}
    </>
  )
}

function ParserResultDetails({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  const parsed = submission.parsed
  const resolved = submission.resolved
  const hasParserOutput = hasSnapshotValue([
    parsed.parser_run_id,
    parsed.created_at,
    parsed.parser_version,
    parsed.parsed_skills_raw,
    parsed.parsed_location_raw,
    parsed.parser_confidence
  ])
  const resolvedSkillIds = parseSnapshotList(resolved.resolved_skill_ids)
  const unknownSkills = parseSnapshotList(resolved.unknown_skills)

  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <DetailBlock title="Raw Submitted Data">
        <dl className="grid gap-4 text-sm">
          <DetailField label="Full Name" value={submission.raw.full_name} />
          <DetailField label="Email" value={submission.raw.email} />
          <DetailField label="Location" value={submission.raw.location_raw} />
          <DetailField label="Skills" value={submission.raw.skills_raw} multiline />
          <DetailField label="Resume Status" value={submission.raw.resume_status} />
        </dl>
      </DetailBlock>

      <DetailBlock title="Raw Parsed Output">
        {parsed.parser_state !== 'complete' && !hasParserOutput ? (
          <StateCallout tone="neutral">No parser result yet</StateCallout>
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
      </DetailBlock>

      <DetailBlock
        title="Resolved Canonical Output"
        status={formatStatus(resolved.resolver_state)}
        statusTone={getResolverStatusTone(resolved.resolver_state)}
      >
        {resolved.resolver_state === 'not_run' ? (
          <StateCallout tone="neutral">No resolved skills available</StateCallout>
        ) : (
          <dl className="grid gap-4 text-sm">
            <DetailField label="Resolver Version" value={resolved.resolver_version} />
            <DetailField label="Aliases Version" value={resolved.aliases_version} />
            <ListDetailField
              label="Resolved Skill IDs"
              values={resolvedSkillIds}
              emptyLabel="No resolved skills available"
            />
            <DetailField
              label="Resolver Coverage"
              value={resolved.resolver_coverage}
            />
          </dl>
        )}
      </DetailBlock>

      <DetailBlock title="Unresolved or Unknown">
        <ListDetailField
          label="Unknown Skills"
          values={unknownSkills}
          emptyLabel="No unresolved items reported"
          tone={unknownSkills.length > 0 ? 'warning' : 'neutral'}
        />
      </DetailBlock>
    </div>
  )
}

function DetailBlock({
  title,
  status,
  statusTone = 'neutral',
  children
}: {
  title: string
  status?: string
  statusTone?: 'neutral' | 'success' | 'warning'
  children: React.ReactNode
}) {
  return (
    <section className="rounded-md border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-libelle-indigo">
          {title}
        </h3>
        {status && <StatusBadge label={status} tone={statusTone} />}
      </div>
      {children}
    </section>
  )
}

function StatusBadge({
  label,
  tone
}: {
  label: string
  tone: 'neutral' | 'success' | 'warning'
}) {
  return (
    <span
      className={[
        'inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
        tone === 'success'
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : tone === 'warning'
            ? 'border-amber-200 bg-amber-50 text-amber-700'
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

async function fetchParserResultsState(
  signal: AbortSignal
): Promise<ParserResultsState> {
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

function compareParserResults(
  first: ReviewerSubmissionSnapshot,
  second: ReviewerSubmissionSnapshot
) {
  const firstRank = getParserStateRank(first)
  const secondRank = getParserStateRank(second)

  if (firstRank !== secondRank) return firstRank - secondRank

  const firstCreatedAt = getSortableDateValue(first.parsed.created_at || first.raw.created_at)
  const secondCreatedAt = getSortableDateValue(
    second.parsed.created_at || second.raw.created_at
  )

  if (firstCreatedAt !== secondCreatedAt) return secondCreatedAt - firstCreatedAt

  return first.submission_id.localeCompare(second.submission_id)
}

function getParserStateRank(submission: ReviewerSubmissionSnapshot) {
  if (submission.parsed.parser_state === 'pending') return 0
  if (submission.resolved.resolver_state === 'not_run') return 1
  if (parseSnapshotList(submission.resolved.unknown_skills).length > 0) return 2
  if (submission.resolved.resolver_state === 'zero_matches') return 3
  return 4
}

function matchesParserResultsFilters(
  submission: ReviewerSubmissionSnapshot,
  filters: {
    searchQuery: string
    parserFilter: ParserFilter
    resolverFilter: ResolverFilter
  }
) {
  if (
    filters.parserFilter !== 'all' &&
    submission.parsed.parser_state !== filters.parserFilter
  ) {
    return false
  }

  if (
    filters.resolverFilter !== 'all' &&
    submission.resolved.resolver_state !== filters.resolverFilter
  ) {
    return false
  }

  const normalizedSearchQuery = normalizeFilterText(filters.searchQuery)
  if (
    normalizedSearchQuery &&
    !getParserResultsSearchText(submission).includes(normalizedSearchQuery)
  ) {
    return false
  }

  return true
}

function getParserResultsSearchText(submission: ReviewerSubmissionSnapshot) {
  return normalizeFilterText(
    [
      submission.submission_id,
      submission.raw.full_name,
      submission.raw.email,
      submission.raw.skills_raw,
      submission.raw.location_raw,
      submission.parsed.parser_state,
      submission.parsed.parser_run_id,
      submission.parsed.parser_version,
      submission.parsed.parsed_skills_raw,
      submission.parsed.parsed_location_raw,
      submission.resolved.resolver_state,
      submission.resolved.resolver_version,
      submission.resolved.aliases_version,
      submission.resolved.resolved_skill_ids,
      submission.resolved.unknown_skills
    ].join(' ')
  )
}

function getParsedPreview(submission: ReviewerSubmissionSnapshot) {
  return [
    submission.parsed.parsed_skills_raw,
    submission.parsed.parsed_location_raw
  ]
    .map((value) => value.trim())
    .filter(Boolean)
    .join(' | ')
}

function getSortableDateValue(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

function normalizeFilterText(value: string) {
  return value.trim().toLowerCase()
}
