# State Transition Contract

Issue 279 introduces a backend-owned contract for interpreting submission state across
intake, resume upload, parser jobs, resolver output, snapshot materialization, reviewer
operations, and audit/error records.

This contract defines pure validators, reviewer-facing health derivation, and the state
matrix. Snapshot health derivation is now wired: `backend/services/dashboard_service.py`
calls `derive_submission_health_state()` when assembling `/snapshot`. This does not mean
every transition helper or historical parser-job state mapping is used by runtime paths.
Start with the [current architecture map](contributor_architecture_map.md) for execution
boundaries; this document owns the pure state contract.

## Files

- `backend/core/state_contract.py` defines state values, validators, and derivation helpers.
- `backend/tests/test_state_contract.py` covers the first-pass state matrix.
- `docs/architecture/state_contract.md` describes how the contract should be used.

The issue text originally suggested `backend/core/stateContract.ts`. The current backend is
Python, so Phase 1 implements `backend/core/state_contract.py`. A TypeScript shared contract
can be added later only if the frontend needs compile-time type sharing. The preferred v0.4
direction is backend-first: the snapshot API derives health state and the frontend treats it
as opaque display data.

## Design Rationale

The intake pipeline is composed of several loosely coupled systems that operate
independently. A resume may upload successfully while parsing fails, or parsing may succeed
while resolver processing is still pending.

For that reason, the contract models each subsystem independently rather than forcing every
submission through a single linear status field. Reviewer-facing health is derived from the
composed state rather than stored directly.

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

`SubmissionHealthState` is a deterministic, backend-owned read model. It is derived from the
canonical state domains and should never be persisted as the primary source of truth.

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
or the network. Runtime callers adopt individual helpers; the contract itself stays pure.
Transition validators answer whether an operation is allowed given the current record state.
They do not perform the operation themselves and should not mutate records.

## State Ownership

Each state domain has a single authoritative owner.

| State | Owner |
| --- | --- |
| `ResumeState` | Intake / upload pipeline |
| `ParserState` | Parser worker |
| `ResolverState` | Resolver pipeline |
| `ReviewStatus` | Reviewer operations |
| `SubmissionHealthState` | Backend read model |

No subsystem should directly modify state owned by another subsystem. Cross-system
interpretation occurs through the state contract rather than ad hoc application logic.

## Derived Health View

Snapshot materialization derives one reviewer-facing `SubmissionHealthState` from
`ResumeState`, `ParserState`, and `ResolverState`.

The health derivation matrix is:

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
- Pipeline failure handlers attempt to append traceable error records. These writes
  are best-effort: error logging itself can fail, so a fatal failure is not guaranteed
  to have a persisted error record.
- Resume access must require authentication and audit logging.
- State transitions should be idempotent whenever practical so retried pipeline steps do not
  create inconsistent records.
- Every state transition and derived health interpretation should be traceable to a single
  origin event: intake, file upload, parser, resolver, snapshot, ops, or audit/error logging.

## Runtime integration boundary

`backend/services/dashboard_service.py` maps persisted submission, selected parser result,
error, and parser-job data into the state domains and calls
`derive_submission_health_state()`. `/snapshot` exposes the resulting
`submission_health_state`; the frontend should display it without recomputing the matrix.

Incoming reviewer status is validated through `backend/ops_schema.py`, not this
contract's `validate_review_status()` helper. Snapshot ops formatting also normalizes
invalid stored status to `new`, as it defaults a missing ops row to `new`; it does
not repair the stored row.

Durable job status, claim eligibility, lease ownership, retry scheduling, and result
authority are implemented by the job repository, worker, and snapshot selection code.
Their operational states are not interchangeable with the pure enums above. The historical
async design's job-state table is not evidence that every mapping or transition helper is
wired. See [precedence rules](system_of_record_precedence.md) and the
[snapshot API](../api-spec.md#get-snapshot) for current read behavior.
