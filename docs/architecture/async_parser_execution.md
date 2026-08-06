# Asynchronous Parser Execution Model

Issue #338 defines the implementation contract for moving parser execution out
of the public intake request path. This document is design-only: it does not
change production parser execution behavior.

## Current Behavior

The public intake endpoint is `POST /api/upload` in
`backend/api/routes/intake.py`.

Current flow:

1. The route validates public form fields and file metadata.
2. The route reads the uploaded PDF bytes.
3. `finalize_submission()` validates size and PDF content.
4. If a resume exists, intake extracts text from the PDF before persistence.
5. The PDF is uploaded to Google Drive.
6. A base row is appended to the `submissions` tab with `resume_status` set to
   `uploaded`, `missing`, or `failed`.
7. If `resume_status == uploaded`, FastAPI schedules
   `parse_and_update(submission_id, drive_file_id, pre_text)` through
   `BackgroundTasks`.
8. The endpoint returns `200` after intake persistence and background-task
   scheduling, not after parser completion.
9. `parse_and_update()` parses the pre-extracted text, runs Resolver V1, and
   appends one row to `parser_results`.
10. Parser and resolver failures append rows to `errors` when error logging
    itself succeeds.

This is asynchronous from the caller's perspective, but it is not a durable job
model. The queued task lives in the API process. If the process stops after the
submission row is written but before or during background execution, there is no
canonical queued job to recover from.

Current storage facts:

- `submission_id` is created by intake and is the cross-system correlation key.
- `submissions` is append-only after intake append.
- `parser_results` is append-only per parser result row.
- `parser_run_id` exists in `parser_results`; today
  `update_resume_in_sheet()` creates a short UUID if the parser did not provide
  one.
- `/snapshot` derives reviewer-facing state from `submissions`,
  `parser_results`, `ops`, and `errors`.
- The latest parser result is selected by `created_at`, then `parser_run_id`.

## Proposed Intake Boundary

The intake success response must mean:

- the public request was accepted;
- the submission was validated;
- the immutable `submissions` row was persisted;
- if a resume was provided, the resume upload outcome was persisted; and
- if a resume was uploaded, a durable parser job record was created or an
  enqueue failure was persisted visibly.

The intake success response must not mean parser completion. It should continue
to return `submission_id`, `resume_filename`, and `resume_status`, and it should
add a parser-facing acknowledgement such as:

```json
{
  "status": "success",
  "submission_id": "sub_123",
  "resume_status": "uploaded",
  "parser_job_status": "queued"
}
```

If the submission and resume are persisted but job creation fails, the endpoint
may still return success only if the failure is persisted as visible pipeline
state, for example `parser_job_status: "enqueue_failed"` plus an `errors` row.
That preserves the v0.4 guarantee of no invisible submissions. A later recovery
scanner must be able to find uploaded submissions without a queued or completed
parser job.

No-resume submissions do not create parser jobs. Their parser state remains
derived as `skipped_no_resume`.

## Recommended Architecture

Use a durable job table in the current Google Sheets system of record, with a
small polling worker.

Add a required `parser_jobs` tab:

| Column | Purpose |
| --- | --- |
| `job_id` | Stable job identifier, recommended equal to `submission_id` for the initial parser job. |
| `submission_id` | Canonical submission correlation key. |
| `drive_file_id` | Storage reference needed to recover text if pre-extracted text is unavailable. |
| `resume_filename` | Display/debug context only. |
| `job_type` | `parse_resume`. |
| `status` | `queued`, `running`, `retry_scheduled`, `succeeded`, `failed`, `enqueue_failed`. |
| `attempt_count` | Number of claimed attempts. |
| `max_attempts` | Default `3`. |
| `available_at` | Earliest time a worker may claim the job. |
| `locked_by` | Worker instance identifier. |
| `locked_at` | Claim timestamp. |
| `lock_expires_at` | Stale-lock recovery timestamp. |
| `last_parser_run_id` | Latest attempt run ID, successful or failed. |
| `last_error_code` | Most recent failure code. |
| `last_error_summary` | Short operational failure summary. |
| `created_at` | Job creation timestamp. |
| `updated_at` | Last state change timestamp. |

The first implementation can use Sheets because Libelle already depends on
Sheets for canonical submission, parser result, ops, and error records. The
worker can run locally, in staging, and on the Raspberry Pi without adding a new
network service. This is enough for current scale and keeps the implementation
observable to reviewers and operators.

The queue implementation must be isolated behind a small repository/service
interface so a future Redis, Postgres, or managed queue migration does not
change intake, parser, resolver, or snapshot contracts.

## Job Creation

Intake owns job creation because intake is the only component that knows when a
submission and resume upload have both crossed the success boundary.

Rules:

- Create a parser job only after the `submissions` row has been appended with
  `resume_status == uploaded`.
- Use `submission_id` as the idempotency key for the initial parser job.
- The durable job payload should contain identifiers, not resume contents.
- Do not store raw resume text in the job table.
- If text extraction remains in intake temporarily, pass the text to the worker
  only through an in-process optimization when available; the durable recovery
  path must be able to re-read the PDF from Drive by `drive_file_id`.
- If job creation fails after the submission row is written, append an `errors`
  row with stage `parser_enqueue` and code `PARSER_ENQUEUE_FAILED`.
- A recovery scanner must be able to create a missing job for any
  `submissions.resume_status == uploaded` record with no parser job and no
  successful parser result.

## parser_run_id Ownership

`submission_id` identifies the volunteer submission and the logical parser job.
`parser_run_id` identifies one processing attempt.

Rules:

- The parser worker creates `parser_run_id` when it claims an attempt.
- Every automatic retry and manual retry gets a new `parser_run_id`.
- A single `submission_id` may have many `parser_run_id` values.
- Successful attempts append rows to `parser_results`.
- Failed attempts append rows to `errors` with both `submission_id` and
  `parser_run_id` once the errors schema is extended.
- The authoritative parser result remains the latest successful
  `parser_results` row selected by `created_at`, then `parser_run_id`, until a
  future schema adds an explicit result state.
- Prior attempts remain traceable through append-only `parser_results`,
  `errors`, and `parser_jobs` state history or job audit rows.

The implementation should move `parser_run_id` generation out of
`update_resume_in_sheet()` and into the worker attempt boundary. The sheet
writer may keep a fallback only as a defensive guard, not as the owner.

## Idempotency and Duplicate Prevention

Job idempotency key: `parse_resume:{submission_id}`.

Duplicate enqueue:

- Creating the same initial parser job twice must return the existing job
  instead of appending a second active job.
- Recovery scanners use the same idempotency key.
- Manual retry creates a new attempt for the same logical job, not a second
  independent active job.

Duplicate worker execution:

- A worker claims only jobs whose `status` is `queued` or `retry_scheduled` and
  whose `available_at <= now`.
- Claim updates `status=running`, increments `attempt_count`, sets
  `last_parser_run_id`, and writes a bounded lease through `locked_by`,
  `locked_at`, and `lock_expires_at`.
- A worker may continue only if its lease and `parser_run_id` still match the
  job row before finalizing.
- If a worker finishes after another attempt has already succeeded, it must not
  mark the job failed or overwrite the authoritative result.
- Parser output writes are append-only. Submission rows are never overwritten.
- Job rows may be updated in place as operational state, but state transitions
  should be monotonic: `succeeded` is terminal unless a reviewer explicitly
  requests a new manual retry.

For Sheets, exact compare-and-swap is limited. The first implementation should
minimize duplicate claims with a short polling interval, process-level worker
identity, and a re-read before finalization. If duplicate execution still
occurs, append-only parser results and latest-row selection keep the reviewer
state deterministic.

## State Mapping

Persisted operational states:

- `submissions.resume_status`: `missing`, `uploaded`, `failed`
- `parser_jobs.status`: `queued`, `running`, `retry_scheduled`, `succeeded`,
  `failed`, `enqueue_failed`
- `parser_results` rows: successful parser/resolver-enriched output attempts
- `errors` rows: parser, resolver, enqueue, and worker failures

Derived state-contract states:

| Pipeline condition | ResumeState | ParserState | ResolverState |
| --- | --- | --- | --- |
| Submission persisted without resume | `none_provided` | `skipped_no_resume` | `skipped_no_parser_output` |
| Resume upload failed | `upload_failed` | `not_started` | `not_started` |
| Resume uploaded, job queued | `uploaded` | `not_started` | `not_started` |
| Job running | `uploaded` | `started` | `not_started` |
| Retry scheduled | `uploaded` | `not_started` or `started` | `not_started` |
| Parser succeeded, resolver not run | `uploaded` | `succeeded` | `not_started` |
| Parser and resolver succeeded | `uploaded` | `succeeded` | `succeeded` |
| Parser failed, retry remains | `uploaded` | `not_started` or `started` | `not_started` |
| Parser retry exhausted | `uploaded` | `failed` | `skipped_no_parser_output` |
| Resolver failed after parser output | `uploaded` | `succeeded` | `failed` |
| Downstream Sheets/Drive unavailable | Preserve last known state; expose error and stale job health through `/snapshot`. |

`retry_scheduled`, `retry_exhausted`, and `downstream_unavailable` are
operational job/read-model facts, not new core state-contract enum values unless
the state contract is explicitly revised later.

## Flow Diagram

```text
Public intake request
  |
  v
Validate fields and PDF metadata
  |
  v
Persist resume outcome and submissions row
  |
  +-- no resume -----------> /snapshot derives no_resume_ok
  |
  +-- upload failed -------> errors row + /snapshot pending_processing today
  |
  v
Create durable parser_jobs row
  |
  +-- create failed -------> errors row + recovery scanner
  |
  v
Return success: accepted, persisted, queued
  |
  v
Polling worker claims job with lease
  |
  v
Create parser_run_id for attempt
  |
  v
Parse resume and run resolver
  |
  +-- retryable failure ---> errors row + retry_scheduled
  |
  +-- exhausted failure ---> errors row + job failed
  |
  v
Append parser_results row
  |
  v
Mark parser_jobs succeeded
  |
  v
/snapshot selects latest parser_results row and derives health
```

## Retry Policy

Default policy:

- `max_attempts`: 3 total attempts.
- Backoff: 1 minute, 5 minutes, 15 minutes, with small jitter if multiple jobs
  are queued.
- Stale running lease timeout: 15 minutes, adjusted after parser duration is
  measured.

Retryable failures:

- transient Google Drive read failures;
- transient Google Sheets append/update failures;
- worker process interruption;
- temporary parser dependency failure;
- resolver alias-file read errors that are clearly environmental.

Non-retryable failures:

- invalid or unsupported PDF that passed an older intake check;
- password-protected PDF;
- no extractable text;
- deterministic parser validation error for the same input;
- missing Drive file after confirmed deletion or permission denial.

Manual retry:

- A reviewer or operator may reset a terminal failed job to
  `retry_scheduled` with a new `available_at`.
- Manual retry creates a new `parser_run_id`.
- Manual retry must not delete previous `errors` or `parser_results` rows.

Retry exhaustion:

- Set `parser_jobs.status = failed`.
- Persist the final error row.
- `/snapshot` should expose parser failure through the existing
  `parser_failed` health derivation and include retry count/job status once the
  snapshot schema is extended.

## Crash and Restart Recovery

API stops after submission persistence but before enqueue:

- Recovery scanner finds uploaded submissions with no job and no successful
  parser result, then creates the idempotent job.
- The original submission remains visible in `/snapshot` as pending or broken
  depending on available state.

Worker stops during parsing:

- The job remains `running` until `lock_expires_at`.
- Another worker may reclaim it after the lease expires.
- The new attempt receives a new `parser_run_id`.

Raspberry Pi restarts:

- systemd starts the API and worker processes.
- The worker resumes polling durable jobs.
- Stale `running` jobs are reclaimed by lease timeout.

Queue or Sheets unavailable:

- Intake returns success only after submission persistence. If job creation
  cannot be persisted, append an enqueue error when possible and rely on the
  recovery scanner.
- Worker backs off and logs operational errors without reading or logging resume
  contents.

Job claimed but never acknowledged:

- Lease expiry makes it claimable again.
- Attempt evidence is visible through `last_parser_run_id`, `attempt_count`, and
  any error rows that were written before the crash.

Storage succeeds but parser-result persistence fails:

- The worker treats this as retryable until max attempts are exhausted.
- If a later retry appends a result successfully, the job becomes `succeeded`.
- If the result append succeeds but marking the job succeeded fails, finalization
  re-reads `parser_results`; if a row for the current `parser_run_id` exists,
  the worker may safely mark the job `succeeded` on the next pass.

## Deployment Model

### Option A: Sheets-backed job table and polling worker

Operational dependencies: existing Google Sheets and Drive credentials.

Persistence: durable enough for current staging and Pi deployment; visible in
the same spreadsheet as related records.

Restart recovery: lease timeout plus recovery scanner.

Local development: works with the existing local Google setup.

Staging: no new service dependency.

Raspberry Pi: simple systemd worker service next to the backend.

Future migration cost: moderate if hidden behind a queue repository interface.

Observability: high for humans inspecting Sheets; can be surfaced in `/snapshot`
and ops views.

Complexity: low to moderate. The main weakness is limited atomic locking.

### Option B: Redis-backed queue

Operational dependencies: Redis service, backups/configuration, worker process.

Persistence: good if configured with AOF/RDB; weaker if treated as ephemeral.

Restart recovery: mature queue patterns if using reliable queues and leases.

Local development: requires Redis locally or Docker.

Staging: adds a service to provision and monitor.

Raspberry Pi: possible, but adds memory/service management overhead.

Future migration cost: lower if production expects Redis-like infrastructure.

Observability: good with queue tooling, weaker for spreadsheet-first reviewers.

Complexity: moderate. More robust claiming than Sheets, but more operations.

### Option C: Managed queue service

Operational dependencies: cloud queue, IAM, deployment networking, dead-letter
queue, worker hosting.

Persistence: strong.

Restart recovery: strong.

Local development: requires emulator or alternate local implementation.

Staging: adds production-like infrastructure work before Libelle needs it.

Raspberry Pi: awkward unless the Pi can reliably authenticate to the cloud
service and receive jobs.

Future migration cost: lowest if Libelle moves fully to managed hosting.

Observability: strong if connected to cloud logs/metrics.

Complexity: high for the current deployment model.

### Recommendation

Start with Option A: a Sheets-backed `parser_jobs` tab plus a single polling
worker process.

This matches Libelle's current scale, keeps staging and Raspberry Pi deployment
simple, preserves spreadsheet visibility, and avoids introducing a production
queue dependency in a spike whose goal is contract definition. The implementation
must still use a narrow queue abstraction so Option B or C can replace the
storage later without changing public intake semantics or parser result
contracts.

## Observability

Minimum visibility:

- count of queued jobs;
- count of running jobs;
- count of failed jobs;
- retry counts and max attempts;
- stale jobs where `lock_expires_at < now`;
- processing duration from claim to success/failure;
- last error code and summary;
- correlation by `submission_id` and `parser_run_id`;
- enqueue failures;
- recovery-created jobs.

Do not log resume contents, extracted raw text, volunteer email, phone, or other
unnecessary personal information. Logs should prefer `submission_id`,
`parser_run_id`, `job_id`, status, timing, and coarse error codes.

## Security and Privacy

- Store identifiers in job metadata, not raw resume text.
- Keep PDF access behind the existing Drive permissions and authenticated resume
  proxy.
- Treat worker logs as operational logs, not data storage.
- Never expose `drive_file_id` through `/snapshot`.
- Do not let parser output overwrite public intake fields.
- Keep failed submissions reviewer-visible.
- Ensure manual retry controls require internal actor authentication before they
  are implemented.

## Implementation Issue Decomposition

1. Add `parser_jobs` schema and storage repository.
   Acceptance: schema validation knows the new tab; create/list/claim/update
   operations are covered by pure or mocked tests.

2. Move parser run ownership to a worker attempt boundary.
   Acceptance: worker-generated `parser_run_id` is passed into
   `parser_results`; `update_resume_in_sheet()` fallback is retained only for
   defensive compatibility.

3. Replace FastAPI `BackgroundTasks` parser scheduling with durable enqueue.
   Acceptance: `POST /api/upload` returns after submission persistence and
   durable job creation; parser completion is not implied.

4. Add polling parser worker.
   Acceptance: worker claims queued jobs, processes one attempt, records success
   or failure, and honors max attempts and lease expiry.

5. Add recovery scanner.
   Acceptance: uploaded submissions without a job or successful parser result
   receive an idempotent parser job.

6. Extend error/job observability in `/snapshot` or an internal ops endpoint.
   Acceptance: reviewers/operators can see queued, running, retrying, failed,
   and stale parser work without reading logs.

7. Add staging and Raspberry Pi service definitions.
   Acceptance: staging docs and systemd templates describe API plus worker
   startup, restart, and environment variables.

## Unresolved Decisions and Risks

- Whether `parser_jobs` should be required in v0.4 startup validation or treated
  as optional during migration.
- Whether failed attempts need an append-only `parser_job_events` tab in the
  first implementation or whether `errors` plus current job state is enough.
- Whether intake should keep pre-extracting PDF text or move all text extraction
  into the worker. Moving extraction into the worker gives a cleaner async
  boundary, but changes the current validation/error timing.
- Sheets does not provide ideal atomic compare-and-swap semantics for leases.
  The design relies on re-read-before-finalize and append-only outputs to remain
  deterministic if duplicate workers run.
- The current state contract does not have explicit `retry_scheduled`,
  `retry_exhausted`, or `downstream_unavailable` enums. Those should remain
  operational details unless reviewer-facing product needs require new states.
- `errors` currently lacks `parser_run_id`; adding it would improve attempt
  traceability and should be considered before full worker rollout.
