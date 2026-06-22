# Libelle v0.4 State Contract

## Purpose

This document defines the state contract for Libelle v0.4: **Trusted Intake Pipeline**.

Libelle v0.4 is not just a form, dashboard, or parser. It is a trusted intake pipeline built over several partially independent systems:

- public form input
- Google Drive resume storage
- `submissions` sheet
- `parser_results` sheet
- `ops` sheet
- `errors` sheet
- async parser jobs
- deterministic resolver output
- reviewer actions

The purpose of this contract is to make sure a volunteer record does not become invisible, ambiguous, overwritten, or untraceable because of partial failure across those systems.

This contract should guide implementation in:

- intake
- file upload
- parser jobs
- resolver output
- snapshot materialization
- dashboard display
- reviewer operations
- audit/error logging

## Relationship to v0.3 Foundation Issues

This state contract formalizes and extends several v0.3 foundation issues. Those issues remain historically useful, but v0.4 should treat this state contract as the governing interpretation layer.

### Issue #70: Generate and standardize `submission_id` across the intake pipeline

#70 establishes `submission_id` as the stable identifier used across the intake pipeline.

The v0.4 state contract adopts this as a core invariant:

> `submission_id` is the sole correlation key across submissions, Drive files, parser jobs, resolver output, ops state, errors, logs, and snapshot records.

This contract should prevent downstream modules from introducing alternate identity keys or ad hoc matching rules.

### Issue #122: Resume upload / Drive persistence behavior

#122 governs the resume file path and Drive persistence behavior.

The v0.4 state contract maps that work into `ResumeState`.

In v0.4:

- no-resume submissions are valid
- uploaded resumes should resolve to `uploaded`
- failed upload attempts should resolve to `upload_failed`
- snapshot and dashboard logic should use explicit resume states rather than treating missing files as parser failures

### Issue #169: Ops status and notes writeback for reviewer workflow

#169 defines the reviewer workflow writeback layer.

The v0.4 state contract maps that work into `ReviewStatus` and `canUpdateOps`.

Ops state should remain:

- reviewer-owned
- backend-validated
- traceable to an actor
- separate from parser/resolver health

Reviewer status and notes must not overwrite submission data, parser output, or resolver output.

### Issue #279: State Transition Contract Layer

#279 is the v0.4 keystone implementation issue for this contract.

It defines:

- state model
- transition rules
- derived `SubmissionHealthState`
- failure visibility rules
- backend/frontend boundary
- no-silent-disappearance rules
- traceable origin rules

This document should evolve with #279 and become the reference used by later v0.4 implementation issues.

## State Domains

Libelle should define separate state domains rather than one overloaded status field.

### ResumeState

`ResumeState` describes whether a resume file exists and whether the upload path succeeded.

Suggested values:

- `none_provided`
- `upload_pending`
- `uploaded`
- `upload_failed`

Resume upload is optional. A missing resume is not itself a failure.

### ParserState

`ParserState` describes whether parser execution has run and what happened.

Suggested values:

- `not_started`
- `skipped_no_resume`
- `started`
- `succeeded`
- `failed`

If no resume is provided, parser execution should be skipped for read-model purposes rather than treated as a broken pipeline.

### ResolverState

`ResolverState` describes whether deterministic normalization has run and what happened.

Suggested values:

- `not_started`
- `succeeded`
- `failed`
- `skipped_no_parser_output`

Resolver failure must not destroy valid parser output.

### ReviewStatus

`ReviewStatus` describes the reviewer-owned workflow state.

Suggested values:

- `new`
- `reviewed`
- `contacted`
- `in_progress`
- `paused`
- `closed`

Review status is separate from parser health, resolver health, and submission health.

## Layering Requirement

The state contract should be organized into three conceptual layers.

### 1. State Model

The State Model defines allowed state values, type definitions, and invariant language.

It should answer:

- What states can exist?
- Which state values are valid?
- Which fields are canonical?
- Which fields are derived?
- Which fields are reviewer-owned?

### 2. Transition Rules

Transition Rules define pure validator functions.

Examples:

- `canStartParser(record)`
- `canSkipParser(record)`
- `canRunResolver(record)`
- `canMaterializeSnapshot(record)`
- `canUpdateOps(record)`
- `validateReviewStatus(status)`
- `assertNoRawDataOverwrite(previous, next)`
- `requireErrorLogForFailure(failureEvent)`

These functions should depend only on record state.

They should not depend on:

- Google Sheets calls
- Google Drive calls
- network calls
- file system side effects
- frontend UI state

### 3. Derived Health View

The Derived Health View defines how the backend derives a reviewer-facing `SubmissionHealthState` from the composed record state.

This prevents backend snapshot logic and frontend dashboard logic from drifting apart.

The frontend should receive `SubmissionHealthState` from the backend snapshot response, treat it as opaque, and avoid independently reimplementing state-matrix interpretation for badges, filters, or reviewer-visible status.

## State Matrix Handling

Snapshot materialization must explicitly handle the cascading matrix of states to avoid dashboard hangs, invisible records, or crashes.

If `ResumeState` is `none_provided`, then `ParserState` and `ResolverState` must be interpreted at read-time only as `skipped_no_resume` and `skipped_no_parser_output` for snapshot/read-model purposes.

These derived interpretations should not be persisted as canonical parser or resolver state unless an explicit pipeline event writes them.

If `ParserState` is `failed`, `ResolverState` must handle fallback gracefully without destroying parser output or blocking reviewer visibility.

Partial or failed records must resolve to an explicit visible state rather than disappearing from the dashboard or blocking snapshot generation.

## Derived SubmissionHealthState

The contract should define a single reviewer-facing derived health state for each submission.

This is not a new source of truth. It is a deterministic read-model interpretation used by the snapshot engine and dashboard.

Suggested values:

- `complete`
- `partial_success`
- `no_resume_ok`
- `parser_failed`
- `resolver_failed`
- `pending_processing`
- `broken_pipeline`

The purpose of `SubmissionHealthState` is to prevent snapshot and dashboard code from inventing their own interpretations of partial records.

Examples:

- If `ResumeState` is `none_provided`, `ParserState` should be interpreted as `skipped_no_resume`, `ResolverState` should be interpreted as `skipped_no_parser_output`, and `SubmissionHealthState` should resolve to `no_resume_ok`.
- If `ParserState` is `succeeded` and `ResolverState` is `succeeded`, `SubmissionHealthState` should resolve to `complete`.
- If `ParserState` is `succeeded` and `ResolverState` is `failed`, `SubmissionHealthState` should resolve to `resolver_failed` or `partial_success`, while preserving raw parser output.
- If `ParserState` is `failed`, `SubmissionHealthState` should resolve to `parser_failed` and remain reviewer-visible.
- If required state fields are missing or contradictory, `SubmissionHealthState` should resolve to `broken_pipeline` rather than disappearing from the dashboard.

The health state must be deterministic, backend-owned, and shared by the snapshot API and dashboard.

## Invariants

The following invariants govern v0.4 state behavior.

- `submission_id` is the sole correlation key across Sheets, Drive, parser jobs, resolver output, ops, errors, logs, and snapshot records.
- User-entered submission data is immutable after append.
- Parser output may never overwrite user-entered fields.
- Resolver output may never overwrite raw parser fields.
- Ops status and notes are reviewer-owned.
- Snapshot data is derived and must not become a source of truth.
- Resume upload is optional.
- No-resume submissions must be valid and reviewer-visible.
- Resolver failure must not destroy valid parser output.
- Fatal pipeline failures must create traceable error records.
- Resume access must require authentication and audit logging.
- No partial, failed, or ambiguous record should silently disappear from reviewer visibility.
- All state transitions and derived health interpretations must be traceable to a single origin step: `intake`, `file_upload`, `parser`, `resolver`, `snapshot`, `ops`, or `audit_error`.
- No state should appear without an identifiable origin.

## Implementation Notes

Before implementing parser, resolver, snapshot, or ops changes for v0.4, check whether the change preserves the invariants inherited from #70, #122, and #169 and formalized in #279.

Implementation should begin with:

- `backend/core/stateContract.ts`
- `backend/core/stateContract.test.ts`
- this document

The first implementation pass should focus on:

- state values
- pure validators
- `deriveSubmissionHealthState()`
- no-resume behavior
- parser failure behavior
- resolver failure behavior
- invalid review status rejection
- raw-data overwrite protection

## Out of Scope for This Contract

This contract does not implement:

- full parser execution
- full dashboard UI
- full Google Sheets integration
- full Google Drive integration
- distributed transaction guarantees
- database migrations
- production alerting

## Acceptance Alignment

This document supports #279 by clarifying how later implementation work should satisfy the state contract.

Expected implementation outcomes:

- `stateContract.ts` exports state types and validators.
- Unit tests cover valid and invalid parser/resolver/reviewer paths.
- Snapshot materialization deterministically resolves all valid and partial combinations of `ResumeState`, `ParserState`, and `ResolverState` into a visible `SubmissionHealthState`.
- The frontend receives `SubmissionHealthState` from the backend snapshot response and does not independently reimplement state-matrix interpretation.
- No-resume submissions are treated as valid records.
- Resolver failure preserves parser output.
- Invalid review statuses are rejected.
- Attempted raw data overwrite is rejected or flagged.
- Partial or failed records resolve to explicit visible states rather than disappearing from the dashboard.
