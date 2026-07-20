import type { ReviewerSubmissionSnapshot } from '../../types/dashboard'
import {
  DetailField,
  ListDetailField,
  SectionHeader,
  StateCallout
} from './DetailPrimitives'
import {
  formatResolverResultState,
  getResolverResultTone,
  parseSnapshotList
} from './detailUtils'

export default function ResolvedOutputSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  const resolved = submission.resolved
  const resolvedSkillIds = parseSnapshotList(resolved.resolved_skill_ids)
  const unknownSkills = parseSnapshotList(resolved.unknown_skills)
  const hasUnknowns = unknownSkills.length > 0
  const hasAvailableResolverOutput =
    resolved.resolver_result_state === 'available' ||
    resolved.resolver_result_state === 'empty_success'

  return (
    <section className="border-t border-slate-200 px-5 py-5">
      <SectionHeader
        title="Resolved Canonical Output"
        description="Resolver/canonical values derived from parser output. Raw parsed values are not replaced here."
        status={formatResolverResultState(resolved.resolver_result_state)}
        statusTone={getResolverResultTone(resolved.resolver_result_state)}
      />

      {!hasAvailableResolverOutput ? (
        <ResolverResultCallout resultState={resolved.resolver_result_state} />
      ) : (
        <div className="grid gap-4">
          {resolved.resolver_state === 'zero_matches' && (
            <StateCallout tone="warning">
              Resolver ran but found zero canonical skill matches.
            </StateCallout>
          )}

          {resolved.resolver_state === 'resolved' && hasUnknowns && (
            <StateCallout tone="warning">
              Partial resolution: some parsed values resolved, while unknown fields remain.
            </StateCallout>
          )}

          <dl className="grid gap-4 text-sm">
            <DetailField label="Resolver Version" value={resolved.resolver_version} />
            <DetailField label="Aliases Version" value={resolved.aliases_version} />
            <ListDetailField
              label="Resolved Skill IDs"
              values={resolvedSkillIds}
              emptyLabel="No resolved skill IDs"
            />
            <ListDetailField
              label="Unknown Skills"
              values={unknownSkills}
              emptyLabel="No unknown skills"
              tone={hasUnknowns ? 'warning' : 'neutral'}
            />
            <DetailField
              label="Resolver Coverage"
              value={resolved.resolver_coverage}
            />
          </dl>
        </div>
      )}
    </section>
  )
}

function ResolverResultCallout({
  resultState
}: {
  resultState: ReviewerSubmissionSnapshot['resolved']['resolver_result_state']
}) {
  if (resultState === 'failed') {
    return (
      <StateCallout tone="danger">
        Resolver failed. Parser output, if present, remains visible.
      </StateCallout>
    )
  }

  if (resultState === 'unavailable_upstream') {
    return (
      <StateCallout tone="danger">
        Resolver could not run because upstream parser output is unavailable.
      </StateCallout>
    )
  }

  return (
    <StateCallout tone="neutral">
      Resolver has not run for this parser result yet.
    </StateCallout>
  )
}
