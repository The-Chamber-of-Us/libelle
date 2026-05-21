import type { ReviewerSubmissionSnapshot } from '../../types/dashboard'
import { DetailField, SectionHeader, StateCallout } from './DetailPrimitives'
import { formatStatus, formatSubmittedDate, hasSnapshotValue } from './detailUtils'

export default function ParsedOutputSection({
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
