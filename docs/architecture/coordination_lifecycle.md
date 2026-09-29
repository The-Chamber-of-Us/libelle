# Intake evidence and coordination lifecycle (#408)

## Investigation and decision

The current intake is immutable `submissions`, with a Drive PDF, parser jobs,
parser/Resolver results and errors. Current reviewer state is `ops`; event
history is optional and best-effort. Before this change, snapshot composition
started exclusively from submissions. Deleting that root hid surviving ops.
The offline deletion/recovery executor from local `volunteer-data-retention`
commit `dc170b7` is integrated here and calls the domain policy for source expiry,
coordination expiry and explicit full deletion. The existing maintenance-only
execution contract is retained; live deployment and isolation still require
operational verification.

Extend ops with one `coordination` JSON cell, keyed by the existing
`submission_id`. No Person, Contributor, Relationship, identity inference or
second current-state store is needed. Multiple submissions remain independent,
even with identical email addresses. A verified deletion request covering several
submissions must explicitly identify all applicable IDs; email matching alone is
not identity verification. After intake removal, lookup can use the known ID or
intentionally supplied coordination display name/contact, subject to human
verification. The application does not automatically discover a person's IDs.

## Explicit intent and field ownership

`POST /submissions/{submission_id}/coordination` accepts `action` (`preserve` or
`end`), a required nonblank `purpose`, `context_reviewed: true`, and optional
`takeaway`, `why`, `next_action`, `revisit` (ISO date), `display_name`, and `contact`.
The Inbox exposes these controls. Each request replaces the coordination content;
omitted optional content becomes blank. Existing workflow state remains intact.
The endpoint requires the existing trusted internal actor. Clients cannot supply
actor or lifecycle timestamps. A first preserve requires an existing submission
or ops row; ending requires an existing coordination decision. Duplicate ops rows
or malformed lifecycle JSON require operator repair and cannot be silently reset.

`preserve` deliberately records a coordination purpose. The backend sets
`purpose_started_at`, `state=active`, and `decided_by`. Further preserve saves
within that active purpose keep the start time. `end` sets `state=ended` and
`purpose_ended_at`; repeated end saves keep the original end time. A deliberate
preserve after ending starts a new purpose. Ordinary status/notes edits, parser
activity, `ops.updated_at`, `submissions.created_at`, and REVISIT do not change
these timestamps. Missing legacy JSON is **unassessed**, not active or expired.
Malformed JSON is **malformed**, not a default lifecycle.

STATE remains existing `ops.status`. WHY, NEXT ACTION, REVISIT and reviewer
takeaway are human-authored coordination fields, alongside notes, tags and
contact tracking. They follow the coordination purpose together. No generated
interpretation or deterministic parser evidence is promoted into these fields.
An ended purpose does not automatically set workflow status to closed, and closed
workflow status does not end a purpose. REVISIT supports a deliberate follow-up;
it never extends retention automatically.

The reviewer attests that current context contains only what is intentionally
needed for coordination. Name/contact are entered deliberately and are never
copied from intake by the system. Do not store resumes, employment/education
histories or extracted evidence in these fields or notes. Length limits and
strict field validation bound the new content but cannot prove the meaning of
free text; review remains necessary. Approval does not certify historical notes.
Lifecycle events record state only, without copying the new free text into history.

## Retention policy and integration contract

The pure `core.coordination_lifecycle.retention_scope()` function returns logical
data domains, not Sheets ranges or retention durations. The deletion executor in `storage/retention_repo.py`
maps these domains to physical artifacts:

| Domain | Current artifacts |
| --- | --- |
| `intake_evidence` | All matching submissions, Drive PDFs, parser jobs, parser/Resolver results, and errors, including raw details. |
| `coordination_context` | All matching ops rows, including current notes, tags, contact tracking, coordination JSON and attribution. |
| `reviewer_history` | All identifying content in matching ops_events, including old/new notes; only non-identifying action counts remain. |

After an approved source boundary, `source_expiry` selects intake evidence and
reviewer history, preserving current ops. Old events may contain superseded source
text, so they must not become a shadow archive. Source eligibility belongs to the
approved source policy; the function does not invent an age or authorize a source
boundary. Active approved coordination survives independently. The executor blocks source expiry when existing ops is unassessed, malformed or
duplicated, requiring explicit review before source removal. It never silently
approves or cascades away that context. This is a review backlog, not authorization
for indefinite retention. Ordinary orphan cleanup protects every ops root.

`coordination_expiry` selects current coordination and its history only when an
explicit ended timestamp is on or before a caller-supplied approved cutoff.
Without that cutoff, or while active/unassessed, it selects nothing. Malformed
metadata raises rather than authorizing deletion. The timestamp starting any
future coordination retention period is **purpose_ended_at**, not last edit,
intake age, planned revisit, or the last parser run. TCUS must select the period
and purpose-review cadence; this implementation selects neither.

`volunteer_deletion` selects all three domains regardless of active purpose or
malformed metadata. Locate artifacts by explicitly verified submission IDs,
including ops-only roots. Do not require an extant submission or Drive reference
to delete coordination. Delete every matching physical row, including duplicates.
A deletion request overrides ongoing coordination; it cannot be downgraded to
source expiry.

The [offline executor and runbook](../deployment/volunteer_data_retention.md)
require all readers/writers to be stopped on all hosts. The CLI refuses apply
without the maintenance attestation and a private recovery manifest. It durably
records references and policy scope, deletes PDFs before removing references,
applies a scoped Sheets batch, and verifies the selected domains. Retries retain
the exact reason and cutoff, including after a lost Sheets response. A source
expiry receipt cannot become full deletion. This reuses the #407 machinery rather
than introducing an online deletion service or a second persistence framework.

The existing ops process lock is not a distributed deletion lock. Maintenance
isolation is an operational precondition, including during backup restore. Live
checks remain required; a snapshot showing no source alone does not prove erasure.

## Read model after source removal

Snapshot roots are the union of submission IDs and ops IDs. Intake-backed records
keep existing parser authority rules. Ops-only records have
`source_state=unavailable`, `submission_health_state=coordination_only`, blank raw
fields, `source_unavailable` parser/Resolver result states, no parser job, and no
joined error details. Leftover processing artifacts cannot leak back through the
retained coordination record. `unavailable` describes absence, not a claim of
successful physical erasure. Resume access continues to require intake evidence.

`coordination_state` reports active, ended, unassessed or malformed separately from
workflow state; `coordination` exposes validated human-authored content or null.
Legacy/malformed ops-only roots remain visible for review. The Inbox hides source
panels when unavailable and retains workflow editing and coordination controls.
The public intake schema and parser job contracts are unchanged. Refreshing the
same selected submission replaces the coordination form with the latest snapshot
and resets its review checkbox; unsaved coordination drafts are replaced on a
changed server record. A successful save updates the parent Inbox snapshot so
navigation and search use the saved context.

## Deployment and validation

Before deploying this version, stop writers and append the exact header
`coordination` at column H of the ops tab (after `updated_by`). Leave existing
cells blank; do not backfill approval from status or timestamps. Required schema
validation deliberately rejects an unmigrated sheet. Resume writers only after
schema validation succeeds. Use the same deployment procedure for staging and
production; this repository change does not modify a live Sheet.

Regression tests cover lifecycle transitions, explicit cutoffs, malformed intent,
source-only scope, deletion override, same-email isolation, persisted actor
attribution, ordinary workflow edits preserving lifecycle state, invalid/duplicate
roots, and snapshots suppressing residual evidence after source removal. Integration tests execute all three deletion scopes against fake Sheets/Drive,
including ops-only full deletion and scoped recovery after lost responses. Live
retention and maintenance isolation must still be verified before using v0.5 with
real volunteer data relying on this continuity.
