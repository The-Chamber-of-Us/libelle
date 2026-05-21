import type { ReviewerSubmissionSnapshot } from '../../types/dashboard'
import {
  DetailField,
  ListDetailField,
  SectionHeader,
  StateCallout
} from './DetailPrimitives'
import { formatStatus, getResolverStatusTone, parseSnapshotList } from './detailUtils'

export default function ResolvedOutputSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  const resolved = submission.resolved
  const resolvedSkillIds = parseSnapshotList(resolved.resolved_skill_ids)
  const unknownSkills = parseSnapshotList(resolved.unknown_skills)
  const hasUnknowns = unknownSkills.length > 0
  const hasResolverRun = resolved.resolver_state !== 'not_run'

  return (
    <section className="border-t border-slate-200 px-5 py-5">
      <SectionHeader
        title="Resolved Canonical Output"
        description="Resolver/canonical values derived from parser output. Raw parsed values are not replaced here."
        status={formatStatus(resolved.resolver_state)}
        statusTone={getResolverStatusTone(resolved.resolver_state)}
      />

      {!hasResolverRun ? (
        <StateCallout tone="neutral">
          Resolver has not run for this parser result yet.
        </StateCallout>
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
