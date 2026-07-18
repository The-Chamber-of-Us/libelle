import type { ReviewerSubmissionSnapshot } from '../../types/dashboard'
import { DetailField, SectionHeader, StateCallout } from './DetailPrimitives'
import {
  formatParserResultState,
  formatSubmittedDate,
  getParserResultTone,
  hasSnapshotValue
} from './detailUtils'

export default function ParsedOutputSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  const parsed = submission.parsed
  const hasAvailableParserOutput = parsed.parser_result_state === 'available'
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
        status={formatParserResultState(parsed.parser_result_state)}
        statusTone={getParserResultTone(parsed.parser_result_state)}
      />

      {!hasAvailableParserOutput && !hasParserOutput ? (
        <ParserResultCallout resultState={parsed.parser_result_state} />
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

function ParserResultCallout({
  resultState
}: {
  resultState: ReviewerSubmissionSnapshot['parsed']['parser_result_state']
}) {
  if (resultState === 'failed') {
    return (
      <StateCallout tone="danger">
        Parser failed. The submission remains visible for reviewer follow-up.
      </StateCallout>
    )
  }

  if (resultState === 'skipped') {
    return (
      <StateCallout tone="neutral">
        Parser was skipped for this submission.
      </StateCallout>
    )
  }

  if (resultState === 'empty_success') {
    return (
      <StateCallout tone="neutral">
        Parser ran successfully but produced no extracted fields.
      </StateCallout>
    )
  }

  return (
    <StateCallout tone="neutral">
      No parser results yet. The parser has not produced a row for this submission.
    </StateCallout>
  )
}
