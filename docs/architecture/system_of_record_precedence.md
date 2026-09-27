# System-of-Record Precedence Rules

Issue #295. This contract defines which Libelle data source wins when raw
submission data, parser output, resolver output, reviewer ops state, errors,
and audit events disagree or are incomplete. It exists so `/snapshot`
can assemble reviewer-facing records deterministically, without ad hoc
assumptions, in support of the v0.4 snapshot trust contract (#294) and the
state transition contract (#279, `docs/architecture/state_contract.md`).

The companion field-level map is
`docs/architecture/field_ownership_contract.md` (#296): ownership says who
may *write* a field; precedence says which source a *reader* must treat as
authoritative when assembling one record from many sources.

## Precedence table

| Data area | System of record | Rule |
| --- | --- | --- |
| Raw volunteer-submitted data | `submissions` tab | Canonical evidence of volunteer intent. Never overwritten or replaced by parser, resolver, or ops values. |
| Resume file reference | `submissions.drive_file_id` / `resume_status` | The file is tied to `submission_id` through the immutable intake row; never inferred from email, name, filename, or client-provided Drive paths. `resume_filename` is display-only. |
| Parser execution | `parser_jobs` tab | Current job/attempt/lease state and explicit successful-result authority; not an append-only execution log. |
| Parser output | Selected `parser_results` row per `submission_id` | Follow explicit authority; require it for succeeded jobs. Latest-result fallback is allowed only as described below. Display alongside raw submitted values. |
| Resolver output | resolver-owned columns of the selected `parser_results` row | Derived normalization. Unresolved values stay visible in `unknown_skills`; resolver output never hides raw parser output. |
| Reviewer workflow status | `ops` tab | Current reviewer-owned workflow state, one row per `submission_id`. |
| Reviewer notes | `ops` tab (current text); `ops_events` tab (best-effort authorship/history) | The current `ops` row shows latest state; append-only events provide non-transactional history when event writes succeed. |
| Errors/failures | `errors` tab | Failure evidence tied to `submission_id`. Informs health state; never removes a submission from view. |
| Snapshot | `/snapshot` response | Derived read model only. Never a source of truth, never written back to any tab. |

## Required decisions

**1. Who owns raw submitted fields?** The `submissions` tab. It is
append-only; the row (including intake-assigned `submission_id`,
`created_at`, `drive_file_id`, `resume_filename`, `resume_status`) is
immutable after append.

**2. Who owns parser-derived fields?** The `parser_results` tab, parser-owned
columns (`parser_run_id`, `parser_version`, `parsed_skills_raw`,
`parsed_location_raw`, `parser_confidence`). New runs append separate results;
Resolver enrichment updates only its own columns on the same attempt row.
`services/dashboard_parser_results.py::select_parser_result` follows
`parser_jobs.authoritative_parser_run_id` when supplied. An unresolvable ID
returns no selected result, not a different attempt. A succeeded job requires
this ID, so blank authority also fails closed. Only when authority is absent
and not required does selection use latest `created_at`, then `parser_run_id`.
This includes legacy submissions without jobs and non-succeeded jobs without
authority. Job logical identity is `parse_resume:{submission_id}`, distinct
from the physical `job_id`, which can be generated during reconciliation.

**3. Who owns resolver-normalized fields?** The resolver-owned columns of the
same `parser_results` row (`resolver_version`, `aliases_version`,
`resolved_skill_ids`, `unknown_skills`, `resolver_coverage`), until a
dedicated resolver output tab exists.

**4. Who owns reviewer status and notes?** The `ops` tab, written only
through the dashboard writeback path with backend-derived actor attribution
(`updated_by`, `updated_at`). Incoming status values are validated through
`backend/ops_schema.py`, not the state-contract `validate_review_status()` helper. `ops_events` records append-only best-effort history for reviewer
changes when available, but it is not the current-state source of truth and
is not a transactional audit guarantee.

**5. What happens when parser/resolver output conflicts with raw submitted
values?** The raw submitted value remains authoritative for what the
volunteer said; parser/resolver output is derived enrichment about the
resume. `/snapshot` presents them as distinct fields from distinct sources
(e.g. `skills_raw` vs `parsed_skills_raw` vs `resolved_skill_ids`) and must
not merge, reconcile, or substitute one for another. Parser output is not
user-confirmed truth; disagreement is signal for the reviewer, not an error
to auto-resolve.

**6. What happens when error rows exist for a submission?** The submission
stays reviewer-visible. Error rows inform the derived health state
(`parser_failed`, `resolver_failed`, `broken_pipeline`, …) and can be
surfaced as failure detail, but an error never makes the underlying
submission disappear from the Inbox.

**7. What happens when ops state exists but parser/resolver data is
missing?** Both are shown for what they are: ops state is reviewer-owned
workflow truth and stands on its own; missing parser/resolver data degrades
the derived health state (`pending_processing`, `partial_success`,
`parser_failed`), not the reviewer workflow state. Absence of an ops row
means "no reviewer action yet" and may be displayed as a default `new`
state, which is why the writeback path upserts on first save. The current
snapshot formatter also normalizes invalid stored ops status to `new`, without
repairing the stored row. A displayed `new` therefore does not prove that no
reviewer action has occurred.

**8. What should `/snapshot` display when sources are partial or degraded?**
Every source it has, each labeled by origin, plus a derived
`SubmissionHealthState` that is honest about degradation. Missing derived
data is shown as missing. Explicit result states distinguish absent, failed,
and successful empty Resolver output; legacy empty arrays alone do not prove
that Resolver ran. A submission with only a `submissions`
row is still a complete, displayable record.

The top-level snapshot domains (`raw`, `parsed`, `resolved`, `ops`, and
`errors`) are always present and are never `null`. Stage availability is
represented with explicit nested state fields rather than by omitting domains.
`parser_job` is also always present but is `null` when no job exists. Its safe
projection preserves unknown/malformed status, counts, and lease-derived staleness;
a succeeded job with missing or unresolvable authority is malformed and cannot
supply healthy-looking parser success. See the [API](../api-spec.md#get-snapshot)
for fields and the precise scope of `error_state="unavailable"`.

Result-state fields:

| Domain | Explicit state field | States |
| ------ | -------------------- | ------ |
| `parsed` | `parser_result_state` | `not_yet_run`, `failed`, `skipped`, `empty_success`, `available` |
| `resolved` | `resolver_result_state` | `not_yet_run`, `failed`, `unavailable_upstream`, `empty_success`, `available` |
| `errors` | `error_state` | `none`, `present`, `unavailable` |

Within these domains, `""` means the source row has no stored scalar value for
that field, JSON strings like `"[]"` mean the source row stored an empty list,
and `null` is reserved for typed optional numeric projections such as
`parser_confidence_score` and `resolver_coverage_score` when no bounded numeric
value is available. Consumers should not infer pipeline state from blank
payload fields; they should read the explicit state fields and
`submission_health_state`.

## Assembly rules for `/snapshot`

1. Start from `submissions` — it defines which records exist. Every
   submission row appears in the read model regardless of the state of any
   other tab.
2. Join other tabs by `submission_id` only. No email-based or positional
   joins.
3. Read canonical logical jobs through `list_parser_jobs()` and select parser
   results by explicit authority as described in decision 2. Succeeded jobs
   must not fall back when authority is blank or unresolvable. Latest-result
   fallback applies only without required or supplied authority. Results from
   different attempts remain separate and are not merged.
4. Never let a derived source shadow a canonical one: parsed/resolved fields
   are presented as their own fields, not folded into submitted fields.
5. Derive health via `derive_submission_health_state` rather than storing
   it. Snapshot output is never persisted back to Sheets.
6. Pipeline contradictions remain visible through backend health derivation.
   Reviewer workflow is a separate source: an ops row can legitimately coexist
   with a degraded pipeline and does not repair parser or Resolver state.

## Out of scope

Full `/snapshot` rewrite, frontend redesign, transactional audit guarantees,
parser/resolver quality work, and production promotion.
