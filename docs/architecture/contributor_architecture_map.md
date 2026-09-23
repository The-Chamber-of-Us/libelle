# Contributor Architecture Map

**Current architecture — start here.** This is the canonical overview of
Libelle’s implemented v0.4 architecture, reconciled in #388. It describes the
repository implementation, not a claim that deployment acceptance is complete.
Detailed rules belong to the [contracts below](#deeper-contracts-and-implementation).
Earlier overviews and proposals are [historical context](../README.md#historical-architecture--retained-for-context).

## System boundaries

Libelle preserves volunteer intake, derives parser and Resolver output, and
composes those sources for internal reviewer workflow. Raw input, extraction,
normalization, current operational state, and event history have separate owners.

| Boundary | Owner and persistence |
| --- | --- |
| Raw intake | `submissions`: immutable after append, including final resume upload outcome and file reference. |
| Resume artifact | Google Drive: uploaded PDF, referenced by the submission. |
| Parser execution | `parser_jobs`: mutable durable job state, claims, attempts, leases, and result authority. |
| Parser extraction | `parser_results`: derived output for a logical `(submission_id, parser_run_id)` result. |
| Resolver normalization | Resolver-owned columns on that same result; enrichment preserves parser-owned fields. |
| Reviewer workflow | `ops`: current status, notes, tags, contact tracking, and attribution. |
| Failure evidence | `errors`: append-only failure records, with attempt identity when available. |
| Reviewer history | Optional `ops_events`: append-only, best-effort per-field change history. |
| Reviewer read model | `/snapshot`: composed at read time, never a persisted source of truth. |

The [schema](../../backend/sheet_schema.py) defines five required Sheets tabs:
`submissions`, `parser_results`, `parser_jobs`, `ops`, and `errors`, plus optional
`ops_events`. Startup validates required tabs and headers, including optional-tab
headers when present. The frontend accesses backend APIs, not Google APIs directly.

## Intake through reviewer workflow

```text
Public form → POST /api/upload
  → validate input and finalize optional Drive upload outcome
  → append immutable submissions row
      ├─ missing/failed resume → no parser job
      └─ uploaded resume → create durable parser job → return intake acknowledgement
                            ↓
                    independent polling worker
                            ↓
                    claim + attempt/run ID + lease
                            ↓
                    download PDF → extract text → parse
                            ↓
                    persist parser-owned result
                            ↓
                    Resolver → enrich the same attempt result
                            ↓
                    finalize authoritative parser success

submissions + parser_jobs + selected parser_results + ops + errors
                            ↓
                        GET /snapshot
                            ↓
                     reviewer dashboard
                            ↓
                 POST /ops/update → current ops state
                                  → best-effort ops_events append
```

`finalize_submission()` resolves the upload outcome before appending the raw
submission. It creates work only after persisting `resume_status=uploaded`.
Intake acknowledgement means intake persistence and the enqueue outcome, not
parser completion. The public intake path no longer owns parser execution through
FastAPI `BackgroundTasks`.

Submission persistence and enqueue are separate Sheets writes. If enqueue fails,
intake returns `parser_job_status=enqueue_failed` and attempts to append
`PARSER_ENQUEUE_FAILED` evidence. Even if error logging also fails, the persisted
uploaded submission remains evidence for recovery.

## Logical jobs, physical rows, and attempts

`submission_id` is the cross-system correlation key. Join sources by this ID,
never by name, email, filename, or row position.

The logical parser-job key is `parse_resume:{submission_id}`, derived from job
type and submission identity. It is distinct from the physical `job_id` used to
address the persisted job. Intake supplies the logical key as its `job_id`;
reconciliation can omit `job_id`, causing the repository to generate a UUID.
Both paths find existing work by logical identity, not by assuming those IDs match.

The worker creates a fresh `parser_run_id` for each claimed attempt. Claiming
increments the attempt count and records worker ownership and a bounded lease.
Retries retain the logical job and receive a new run ID. `last_parser_run_id`
identifies the latest attempt; `authoritative_parser_run_id` identifies the
successful result selected for reviewer reads.

The worker rechecks lease and attempt ownership before subsequent durable side
effects. Expired running jobs with attempts remaining can be reclaimed. Parser
or result-persistence failures schedule a retry or become terminal when the
attempt budget is exhausted. A job row stores current execution state; it is not
an append-only history of every claim or transition.

Sheets has no atomic compare-and-swap claim or uniqueness constraint. The supported
configuration is **one active polling worker per environment**. Repository
idempotency checks and lease rereads do not establish distributed fencing or
exactly-once execution. The [worker runbook](../deployment/parser_worker.md)
owns service configuration, local lock limitations, and live acceptance checks.

## Parser output and Resolver enrichment

The worker downloads the PDF using the durable file reference, extracts text,
and calls `parse_resume`. It persists parser-owned output before running
Resolver V1. `persist_parser_result_if_missing()` guards logical result identity
`(submission_id, parser_run_id)` before appending; physical uniqueness is not
transactionally enforced by Sheets.

Resolver normalizes extraction into fields such as `resolved_skill_ids`,
`unknown_skills`, and `resolver_coverage`. Its enrichment updates resolver-owned
columns on the same attempt’s row. Thus new parser runs append results, while
resolver enrichment can update an existing result without changing raw intake
or parser-owned fields.

Resolver failure preserves successful parser output. The worker attempts to
record resolver-stage failure evidence and can still finalize the parser job as
`succeeded`; that status does not assert Resolver success. Missing Resolver
output, failed Resolver execution, and successful zero matches remain distinct
read-model cases. Legacy `"[]"` placeholders alone do not prove Resolver ran;
see the [snapshot API](../api-spec.md#get-snapshot) for exact result-state semantics.

## Result authority and snapshot composition

The worker finalizes `authoritative_parser_run_id` after parser output persistence
and ownership checks. Snapshot composition starts from submissions so missing
or failed derived data does not remove an intake record.

If an authority ID exists, selection uses that attempt’s result and does not
substitute another result when the ID cannot be resolved. A `succeeded` job
requires authority: blank or unresolvable authority produces malformed job
state and no selected parser result. When authority is absent and not required,
the current selector falls back to latest `created_at`, then `parser_run_id`.
That fallback includes legacy submissions without jobs and non-succeeded jobs
without authority. Results from different attempts are not merged.

`/snapshot` assembles separate `raw`, `parsed`, `resolved`, `parser_job`, `ops`,
and `errors` domains. The backend calls `derive_submission_health_state()` for
reviewer-facing health. The frontend displays that derivation rather than
reimplementing the health matrix. Snapshot output is never written back to Sheets.

Parser-job projections preserve unknown/malformed operational values rather than
invent valid attempt counts or healthy success authority. Staleness is a read-time
projection and does not reclaim a job. The safe projection excludes Drive IDs,
filenames, worker identity, and lease internals. Exact fields and failure semantics
belong to the [API reference](../api-spec.md#get-snapshot); selection belongs to
[system-of-record precedence](system_of_record_precedence.md).

## Recovery and operational history

`reconcile_missing_parser_jobs()` is a separate maintenance operation. It creates
missing logical jobs for uploaded submissions with no existing job and no parser
result. The current implementation treats any parser-result row for a submission
as successful-result evidence for this skip check. Reconciliation does not parse,
rewrite submissions/results, or reset existing jobs. The worker service does not
install a reconciliation timer.

Reviewer writeback changes current `ops` state using backend-derived attribution.
Incoming status is validated through `backend/ops_schema.py`, not the state-contract
helper. Snapshot composition defaults a missing ops row to `new` and also
normalizes an invalid stored status to `new`, without repairing storage. This
reviewer-state fallback differs from the conservative parser-job projection above.
Reviewer writeback does not change raw, parsed, or resolved values. `ops_events` records per-field
changes when its optional tab and writes are available. Missing or failed event
appends do not block current ops writes; snapshot reads current `ops`, not a replay
of event history. `errors` holds separate failure evidence. Cross-tab writes are
not transactional, so neither event stream guarantees a complete audit trail.

## Contributor guardrails

- Preserve raw intake; display extraction and normalization alongside it.
- Use the canonical job repository for logical identity, claims, and updates.
- Keep attempt identity distinct from submission and physical job identity.
- Do not infer Resolver completion from empty list strings or parser-job success.
- Do not replace missing success authority with the latest convenient result.
- Keep snapshot composition free of persistence and job-recovery side effects.
- Keep reviewer workflow separate from parser/Resolver output and event history.
- Verify implementation and live deployment separately; repository tests do not
  establish restart, reboot, isolation, or cross-host worker exclusivity.

This overview introduces no future Person, Evidence, Capability, matching, or
Pathfinder domain architecture.

## Deeper contracts and implementation

- [Engineering principles](engineering_principles.md): contributor standards.
- [State contract](state_contract.md): pure state domains and health derivation.
- [Field ownership](field_ownership_contract.md): writers and persistence boundaries.
- [System-of-record precedence](system_of_record_precedence.md): authoritative reads.
- [Snapshot API](../api-spec.md#get-snapshot): response fields and availability states.
- [Ops event history](ops_event_history.md): current state versus best-effort history.
- [Worker runbook](../deployment/parser_worker.md): deployment and operational checks.

Implementation anchors: [intake](../../backend/services/intake_service.py),
[job repository](../../backend/storage/parser_jobs_repo.py),
[worker](../../backend/services/parser_worker.py),
[reconciliation](../../backend/services/parser_job_reconciliation.py),
[result persistence and ops events](../../backend/storage/sheets_repo.py),
[result selection](../../backend/services/dashboard_parser_results.py), and
[snapshot composition](../../backend/services/dashboard_service.py).
