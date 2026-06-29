# State Transition Contract

Issue 279 introduces a backend-owned contract for interpreting submission state across
intake, resume upload, parser jobs, resolver output, snapshot materialization, reviewer
operations, and audit/error records.

This first pass is intentionally design-first. It defines the contract shape, pure
validators, the derived reviewer-facing health state, and unit tests for the state matrix.
It does not yet wire the contract into the live snapshot, dashboard, intake, parser, or
resolver paths.

## Files

- `backend/core/state_contract.py` defines state values, validators, and derivation helpers.
- `backend/tests/test_state_contract.py` covers the first-pass state matrix.
- `docs/architecture/state_contract.md` describes how the contract should be used.

The issue text originally suggested `backend/core/stateContract.ts`. The current backend is
Python, so Phase 1 implements `backend/core/state_contract.py`. A TypeScript shared contract
can be added later only if the frontend needs compile-time type sharing. The preferred v0.4
direction is backend-first: the snapshot API derives health state and the frontend treats it
as opaque display data.

## State Model

The contract keeps separate state domains instead of collapsing the pipeline into one linear
status field.

`ResumeState`

- `none_provided`
- `upload_pending`
- `uploaded`
- `upload_failed`

`ParserState`

- `not_started`
- `skipped_no_resume`
- `started`
- `succeeded`
- `failed`

`ResolverState`

- `not_started`
- `succeeded`
- `failed`
- `skipped_no_parser_output`

`ReviewStatus`

- `new`
- `reviewed`
- `contacted`
- `in_progress`
- `paused`
- `closed`

`SubmissionHealthState`

- `complete`
- `partial_success`
- `no_resume_ok`
- `parser_failed`
- `resolver_failed`
- `pending_processing`
- `broken_pipeline`

`SubmissionHealthState` is a derived read-model category, not a source of truth.

## Transition Rules

The contract exposes pure functions that depend only on record state:

- `validate_review_status(status)`
- `derive_submission_health_state(record)`
- `can_start_parser(record)`
- `can_skip_parser(record)`
- `can_run_resolver(record)`
- `can_materialize_snapshot(record)`
- `can_update_ops(record)`
- `assert_no_raw_data_overwrite(previous, next_record)`
- `require_error_log_for_failure(failure_event)`

These functions must not call Google Sheets, Google Drive, FastAPI, the parser, the resolver,
or the network. Runtime services can call them later, but the contract itself stays pure.

## Derived Health View

Snapshot materialization should derive one reviewer-facing `SubmissionHealthState` from
`ResumeState`, `ParserState`, and `ResolverState`.

The first-pass matrix is:

| ResumeState | ParserState | ResolverState | SubmissionHealthState |
| --- | --- | --- | --- |
| `none_provided` | `not_started` or `skipped_no_resume` | `not_started` or `skipped_no_parser_output` | `no_resume_ok` |
| `uploaded` | `not_started` or `started` | `not_started` | `pending_processing` |
| `uploaded` | `succeeded` | `not_started` | `partial_success` |
| `uploaded` | `succeeded` | `succeeded` | `complete` |
| `uploaded` | `succeeded` | `failed` | `resolver_failed` |
| `uploaded` | `failed` | `not_started`, `failed`, or `skipped_no_parser_output` | `parser_failed` |
| `upload_pending` or `upload_failed` | `not_started` | `not_started` | `pending_processing` |
| missing, unknown, or contradictory state | any | any | `broken_pipeline` |

No-resume submissions are valid and reviewer-visible. Parser and resolver skip states may be
derived at snapshot read time for no-resume records without being persisted as canonical
parser or resolver events.

## Invariants

- `submission_id` is the correlation key across Sheets, Drive, parser jobs, resolver output,
  ops, and errors.
- User-entered submission fields are immutable after append.
- Parser output must not overwrite user-entered fields.
- Resolver output must not overwrite raw parser fields.
- Ops status and notes are reviewer-owned.
- Snapshot data is derived and must not become a source of truth.
- Resume upload is optional.
- No-resume submissions must remain reviewer-visible.
- Parser and resolver failures must remain reviewer-visible.
- Resolver failure must preserve valid parser output.
- Fatal pipeline failures must create traceable error records.
- Resume access must require authentication and audit logging.
- State transitions and health derivations should be traceable to an origin step: intake,
  file upload, parser, resolver, snapshot, ops, or audit/error logging.

## Future Integration

Later PRs can call this contract from the snapshot assembler and expose
`SubmissionHealthState` through `/snapshot`. At that point, the frontend should display the
backend-provided health state for badges and filters without recomputing the matrix.
