# Issue #388: architecture documentation reconciliation plan

## Proposed current entry point

Use [Contributor Architecture Map](contributor_architecture_map.md) as the
single **Current architecture — start here** document. The documentation
index already directs contributors there, and its ownership/read-model
explanation is useful. Update that existing map rather than create a competing
overview. Keep detailed rules in the state, ownership, precedence, API, and
operations references.

## Documents reviewed and findings

[System architecture](../architecture.md): Earlier overview presented as current. The
lifecycle says parsed data is appended to the submission's same row before confirmation;
the service paths use `backend/app/services`; the strictly one-way diagram omits
independent workers and composed reads. Preserve its body as historical context, with a
prominent historical banner and current-entry link.

[Data flow v0.1](../data-flow.md): Useful historical account, but headings such as
“Current Reality,” `BackgroundTasks`, and same-row parser writes can mislead readers.
Preserve the v0.1 body; explicitly label the entire document historical and superseded
for implementation guidance.

[Contributor architecture map](contributor_architecture_map.md): Correct separation of
raw, parsed, resolved, ops, errors, and snapshot domains. Stale “async background task”
and lifecycle; omits jobs, attempts, authority, and reconciliation. Diagram places
submission persistence before upload even though the implementation finalizes the upload
outcome first. “4-tab” storage omits required `parser_jobs`. Replace the future
identity/canonical/matching discussion with the implemented execution boundaries and a
short scope statement.

[Asynchronous parser execution](async_parser_execution.md): Original #338 design,
explicitly design-only, but mixes “Current Behavior” BackgroundTasks with durable
proposals. Useful historical rationale, not an exact implementation reference. Preserve
it with a historical-design banner and links to the current map, precedence rules, and
worker runbook. Its fallback allowance for missing authority must not be presented as
current behavior for succeeded jobs.

[State contract](state_contract.md): State domains and derivation remain useful. Intro
says the contract is not wired into live paths; “Future Integration” says snapshot
integration is still future work. Update those integration-status statements against
current callers without redefining the state matrix.

[Field ownership](field_ownership_contract.md): Raw/parser/resolver/reviewer separation
is useful. “4-tab” scope, parser-owned run-ID attribution, latest-run timestamp
selection, missing job ownership and error run ID are stale. Unqualified append-only
result wording omits resolver enrichment of the same result row. Add bounded corrections
and a parser-job ownership section; link schema/repository definitions rather than
duplicate a second job schema.

[System-of-record precedence](system_of_record_precedence.md): Correct raw-data and
snapshot boundaries, but table, decision 2, and assembly rule 3 unconditionally select
the latest result. Correct these together to describe explicit authority, fail-closed
succeeded jobs, and the actual fallback scope. Add the job operational-state boundary.

[Snapshot API](../api-spec.md#get-snapshot): Already documents nullable `parser_job`,
explicit result states, malformed job projections, safe operational fields, and
fail-closed authority. Retain this as the response-shape owner; link to it rather than
repeat its field tables.

[Ops event history](ops_event_history.md): Accurately distinguishes mutable current ops
state from optional, append-only, best-effort history. Retain and link; no rewrite
needed.

[Worker deployment](../deployment/parser_worker.md): Describes independent API/worker
services, one active poller, local advisory lock limitations, separate reconciliation,
and live acceptance requirements. Retain as the operational reference; do not turn
repository implementation into a claim of verified deployment.

[Documentation index](../README.md), [root README](../../README.md), [backend
README](../../backend/README.md): Index already chooses the contributor map; root README
has no obvious current architecture link and backend README sends readers there. Label
current versus historical material in the index and add a direct current-entry link in
the root README. Backend README can remain unchanged.

## Implementation trace that the updated map will describe

1. `backend/api/routes/intake.py` and
   `backend/services/intake_service.py::finalize_submission` validate intake,
   assign `submission_id`, finalize the optional Drive upload outcome, and
   append the immutable `submissions` row. Raw volunteer input remains the
   intake system of record.
2. Only an uploaded resume causes `create_parser_job` after submission
   persistence. `backend/storage/parser_jobs_repo.py` owns logical identity
   `parse_resume:{submission_id}`, job state, attempts, and leases. Missing
   or failed uploads create no parser work. Enqueue failure returns
   `enqueue_failed` and attempts to append `PARSER_ENQUEUE_FAILED` evidence;
   the submission and job writes are not transactional, and error logging
   can also fail.
3. `backend/services/parser_job_reconciliation.py` separately creates missing
   jobs for uploaded submissions with neither an existing logical job nor a
   parser result. Its current successful-result check treats the presence of
   any parser-result row for the submission as success evidence. It does not
   execute parsing or rewrite submissions/results; no automatic reconciliation
   timer is installed by the worker deployment.
4. `backend/services/parser_worker.py` generates a new `parser_run_id` for
   a claim, downloads the persisted Drive file, extracts text, and calls
   `parse_resume`. Claims increment attempts and record bounded leases.
   Lease/owner checks guard subsequent persistence boundaries. This is a
   single-active-poller Sheets implementation, not an atomic distributed queue.
5. `persist_parser_result_if_missing` in `backend/storage/sheets_repo.py`
   persists parser-owned output keyed by `(submission_id, parser_run_id)`
   before Resolver runs. Results are separate derived artifacts, never
   submission-row replacements. Repository checks supply logical idempotency;
   Sheets does not enforce physical uniqueness.
6. Resolver V1 normalizes extraction into separate resolver-owned fields.
   `persist_resolver_output_for_parser_result` enriches the same attempt row
   while preserving parser fields. Resolver exceptions log resolver-stage
   failures; parser success can still be finalized. Blank resolver output,
   resolver failure, and successful zero matches are distinct read-model cases.
7. Worker finalization records `authoritative_parser_run_id` on the succeeded
   job. `backend/services/dashboard_parser_results.py::select_parser_result`
   selects that ID when supplied and returns no result if it cannot resolve
   it. `dashboard_service.py` additionally requires authority for succeeded
   jobs, so blank authority cannot fall back. Where authority is absent and
   not required, the implementation still uses timestamp/run-ID selection,
   including non-succeeded jobs, not just submissions without jobs.
8. `backend/services/dashboard_service.py` starts with submissions and
   composes raw, parsed, resolved, safe parser-job, ops, and errors domains.
   It calls `derive_submission_health_state`; `/snapshot` is not persisted
   and does not reclaim jobs. Malformed parser-job values stay explicit;
   missing success authority cannot produce healthy-looking parser success.
9. Reviewer writeback changes current `ops` fields with backend-derived
   attribution. `sheets_repo.py` appends per-field `ops_events` best-effort.
   `ops_events` is optional and is not read to reconstruct snapshot state.
   `errors` preserves failure evidence separately. Neither history stream
   is a transactional guarantee across Sheets writes.

`backend/sheet_schema.py` currently defines five required tabs (`submissions`,
`parser_results`, `parser_jobs`, `ops`, `errors`) plus optional `ops_events`.

## Implementation gap for separate review

`backend/services/dashboard_ops_state.py::format_current_ops_state` changes
an invalid stored reviewer status to `new`, just as it defaults an absent ops
row to `new`. Thus the requested conservative-corruption principle is
implemented for parser-job projections but is not a universal guarantee for
reviewer workflow state. Record this separately rather than claim that unknown
reviewer state is preserved or silently change runtime behavior under #388.
Any change to this fallback needs its own implementation review. The current
architecture map should explicitly acknowledge this limitation.

The historical async design also describes aspirations such as job state
history and stronger duplicate-result handling. Do not claim those guarantees
from that design document alone; current mutable `parser_jobs` rows are not
an append-only job-attempt audit log.

## Smallest proposed documentation change set

Nine existing files:

1. Update `docs/architecture/contributor_architecture_map.md` as the single
   current overview, with the verified flow, ownership boundaries, authority,
   recovery, conservative parser-job state, and the ops limitation above.
2. Add historical banners and current-entry links to `docs/architecture.md`,
   `docs/data-flow.md`, and `docs/architecture/async_parser_execution.md`.
   Retain their historical bodies; retire their role as current guidance.
3. Correct only the identified stale integration, ownership, and selection
   statements in `state_contract.md`, `field_ownership_contract.md`, and
   `system_of_record_precedence.md`.
4. Add the explicit current-entry link to root `README.md`; classify current
   and historical references in `docs/README.md`.

No API rewrite, deployment rewrite, new domain objects, Pathfinder integration,
matching architecture, schema changes, or runtime changes. This plan file can
remain a review record or be omitted from the eventual documentation PR once
the issue comment holds the reviewed plan.

## Validation after plan review

Check all changed relative links and Markdown formatting; run `git diff --check`.
Search the bounded document set for BackgroundTasks, same-row persistence,
latest-result precedence, four-tab schema, and future-integration statements;
ensure remaining historical claims are clearly labeled. Recheck each current
flow statement against the source functions above. Inspect the final diff to
confirm only documentation changed. Runtime tests are not necessary for banner,
link, and prose changes; no live worker acceptance is implied.
