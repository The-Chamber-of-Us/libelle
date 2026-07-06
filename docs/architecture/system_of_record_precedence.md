# System-of-Record Precedence Rules

Issue #295. This contract defines which Libelle data source wins when raw
submission data, parser output, resolver output, reviewer ops state, errors,
and future audit events disagree or are incomplete. It exists so `/snapshot`
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
| Resume file reference | `submissions.resume_filename` / `resume_status` + Drive | The file is tied to `submission_id` via deterministic naming; never inferred from email or other fields. |
| Parser output | `parser_results` tab (latest row per `submission_id`) | Derived enrichment. Displayed alongside — never instead of — raw submitted values. |
| Resolver output | resolver-owned columns of the latest `parser_results` row | Derived normalization. Unresolved values stay visible in `unknown_skills`; resolver output never hides raw parser output. |
| Reviewer workflow status | `ops` tab | Current reviewer-owned workflow state, one row per `submission_id`. |
| Reviewer notes | `ops` tab (current text); future `ops_events` (authorship/history, #290) | The current row shows latest state; per-edit attribution belongs to append-only events once they exist. |
| Errors/failures | `errors` tab | Failure evidence tied to `submission_id`. Informs health state; never removes a submission from view. |
| Snapshot | `/snapshot` response | Derived read model only. Never a source of truth, never written back to any tab. |

## Required decisions

**1. Who owns raw submitted fields?** The `submissions` tab. It is
append-only; the row (including intake-assigned `submission_id`,
`created_at`, `resume_filename`, `resume_status`) is immutable after append.

**2. Who owns parser-derived fields?** The `parser_results` tab, parser-owned
columns (`parser_run_id`, `parser_version`, `parsed_skills_raw`,
`parsed_location_raw`, `parser_confidence`). Rows are append-only per run;
"current" parser output means the latest row selected by `created_at` with
`parser_run_id` as tie-breaker (`services/dashboard_parser_results.py`).

**3. Who owns resolver-normalized fields?** The resolver-owned columns of the
same `parser_results` row (`resolver_version`, `aliases_version`,
`resolved_skill_ids`, `unknown_skills`, `resolver_coverage`), until a
dedicated resolver output tab exists.

**4. Who owns reviewer status and notes?** The `ops` tab, written only
through the dashboard writeback path with backend-derived actor attribution
(`updated_by`, `updated_at`). Status values are validated by the state
contract.

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
state, which is why the writeback path upserts on first save.

**8. What should `/snapshot` display when sources are partial or degraded?**
Every source it has, each labeled by origin, plus a derived
`SubmissionHealthState` that is honest about degradation. Missing derived
data is shown as missing (empty resolver fields mean "not run" or "could not
resolve", never fabricated defaults). A submission with only a `submissions`
row is still a complete, displayable record.

## Assembly rules for `/snapshot`

1. Start from `submissions` — it defines which records exist. Every
   submission row appears in the read model regardless of the state of any
   other tab.
2. Join other tabs by `submission_id` only. No email-based or positional
   joins.
3. For `parser_results`, select the latest row per submission
   (`created_at`, then `parser_run_id`). Older rows remain in the tab as
   history but are not merged.
4. Never let a derived source shadow a canonical one: parsed/resolved fields
   are presented as their own fields, not folded into submitted fields.
5. Derive health via `derive_submission_health_state` rather than storing
   it. Snapshot output is never persisted back to Sheets.
6. When sources contradict (e.g. ops row exists for a broken pipeline), the
   record stays visible with the contradiction reflected in health state —
   the snapshot assembler does not "fix" data.

## Out of scope

Full `/snapshot` rewrite, frontend redesign, `ops_events` implementation
(#290), parser/resolver quality work, and production promotion.
