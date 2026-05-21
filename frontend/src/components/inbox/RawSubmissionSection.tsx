import type { ReviewerSubmissionSnapshot } from '../../types/dashboard'
import { DetailField, LinkDetailField } from './DetailPrimitives'

export default function RawSubmissionSection({
  submission
}: {
  submission: ReviewerSubmissionSnapshot
}) {
  return (
    <section className="px-5 py-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-libelle-indigo">
          Raw Submission
        </h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Source-of-truth user-entered values from submissions.
        </p>
      </div>

      <dl className="grid gap-4 text-sm">
        <DetailField label="Full Name" value={submission.raw.full_name} />
        <DetailField label="Email" value={submission.raw.email} />
        <DetailField label="Location" value={submission.raw.location_raw} />
        <DetailField label="Timezone" value={submission.raw.timezone} />
        <DetailField label="Skills" value={submission.raw.skills_raw} multiline />
        <DetailField label="Interests" value={submission.raw.interests} multiline />
        <DetailField
          label="Experience Level"
          value={submission.raw.experience_level}
        />
        <DetailField label="Availability" value={submission.raw.availability} multiline />
        <DetailField label="Motivation" value={submission.raw.motivation} multiline />
        <LinkDetailField label="LinkedIn" value={submission.raw.linkedin_url} />
        <LinkDetailField label="GitHub" value={submission.raw.github_url} />
        <DetailField label="Consent Given" value={submission.raw.consent_given} />
        <DetailField label="Resume Filename" value={submission.raw.resume_filename} />
        <DetailField label="Resume Status" value={submission.raw.resume_status} />
      </dl>
    </section>
  )
}
