# Field Ownership Contract

Issue #296. This contract defines which pipeline stage owns each field in the
v0.3/v0.4 4-tab schema, so parser and resolver improvements never overwrite,
hide, or mislabel volunteer-submitted data.

It turns the invariants introduced by the state transition contract (#279,
`docs/architecture/state_contract.md`) into an explicit field-by-field map. A
reviewer should always be able to tell whether a value came from the
volunteer, the parser, the resolver, a reviewer action, or a backend
read-model derivation.

The machine-readable companion is the field-group constants in
`backend/core/state_contract.py` (`USER_ENTERED_FIELDS`,
`INTAKE_SYSTEM_FIELDS`, `RAW_PARSER_FIELDS`, `RESOLVER_OWNED_FIELDS`,
`REVIEWER_OWNED_FIELDS`, `OPS_ATTRIBUTION_FIELDS`, `AUDIT_ERROR_FIELDS`,
`SNAPSHOT_DERIVED_FIELDS`, and the combined `FIELD_OWNERSHIP` map). Those
tuples use the canonical column names from `backend/sheet_schema.py` and are
verified against it by `test_field_ownership_groups_match_sheet_schema`.
Keep this document and those constants in sync.

## Ownership map

### `submissions` tab — owner: public intake

The entire row is written once by the intake path and is **append-only and
immutable after append**. Resume upload resolves before the row is written,
so `drive_file_id`, `drive_file_url`, `resume_filename`, and `resume_status`
are final at append time.

| Field | Ownership | Notes |
| --- | --- | --- |
| `full_name` | Volunteer-entered | Canonical evidence of volunteer intent. |
| `email` | Volunteer-entered | |
| `location_raw` | Volunteer-entered | Raw text; never replaced by parser/resolver normalization. |
| `timezone` | Volunteer-entered | |
| `skills_raw` | Volunteer-entered | Raw text; parser output lives in `parser_results`, not here. |
| `interests` | Volunteer-entered | |
| `experience_level` | Volunteer-entered | |
| `availability` | Volunteer-entered | |
| `motivation` | Volunteer-entered | |
| `linkedin_url` | Volunteer-entered | |
| `github_url` | Volunteer-entered | |
| `consent_given` | Volunteer-entered | |
| `submission_id` | Intake system | Canonical correlation key across all tabs, Drive, and logs. |
| `created_at` | Intake system | |
| `drive_file_id` | Intake/upload system | Storage-only Drive file identifier used by the secure resume proxy; not exposed by `/snapshot`. |
| `drive_file_url` | Intake/upload system | Storage-only Drive URL retained for backend operations; not exposed by `/snapshot`. |
| `resume_filename` | Intake/upload system | Deterministic `{submission_id}` naming; matches the actual Drive filename. |
| `resume_status` | Intake/upload system | Final upload outcome (`uploaded` / `failed` / `missing`). |

### `parser_results` tab — owners: parser pipeline and resolver pipeline

Rows are **append-only per parser run**. Within a row, parser-extracted
fields and resolver-normalized fields have different owners.

| Field | Ownership | Notes |
| --- | --- | --- |
| `submission_id` | Correlation key | Copied from the submission; never reassigned. |
| `parser_run_id` | Parser | Identifies the run; distinct from `submission_id`. |
| `created_at` | Parser | Row append time; used to select the latest run. |
| `parser_version` | Parser | |
| `parsed_skills_raw` | Parser | Raw extraction evidence. Resolver must not rewrite it. |
| `parsed_location_raw` | Parser | |
| `parser_confidence` | Parser | Derived evidence; stays visible even when low. |
| `resolver_version` | Resolver | Empty until the resolver runs. |
| `aliases_version` | Resolver | |
| `resolved_skill_ids` | Resolver | Normalization over parser output. |
| `unknown_skills` | Resolver | Unresolved values are preserved here, never dropped. |
| `resolver_coverage` | Resolver | |

### `ops` tab — owner: reviewer operations

One row per `submission_id`, holding the **current** workflow state. Mutable
only through the dashboard writeback path (`/ops/update`), which validates
status via the state contract.

| Field | Ownership | Notes |
| --- | --- | --- |
| `submission_id` | Correlation key | |
| `status` | Reviewer | Validated against `ReviewStatus`. |
| `notes` | Reviewer | Human-authored operational notes. |
| `tags` | Reviewer | |
| `contact_tracking` | Reviewer | |
| `updated_at` | Backend attribution | Set by the write path, not the reviewer. |
| `updated_by` | Backend attribution | Actor identity derived by the backend (`internal_actor`). |

### `errors` tab — owner: audit/error logging

**Append-only.** Failure evidence tied to `submission_id` where possible. No
pipeline stage or reviewer edits error rows after append.

| Field | Ownership |
| --- | --- |
| `submission_id`, `created_at`, `stage`, `error_code`, `error_summary`, `error_details` | Audit/error logging |

### Snapshot fields — owner: backend read model

`/snapshot` responses (including `submission_health_state`) are **derived
assembly for display only**. They are never persisted as canonical storage
and must never be written back into any tab.

## Rules

1. **Parser output must not overwrite raw intake values.** Parser extraction
   lands in `parser_results`; the `submissions` row is untouched.
2. **Resolver output must not hide or erase raw parser output.** Resolver
   fields sit alongside parser fields in the same row; unresolved skills go
   to `unknown_skills` instead of being dropped.
3. **Reviewer status/notes must not alter raw, parsed, or resolved values.**
   Ops writes touch only the `ops` tab.
4. **Nothing overwrites the `submissions` row after append.** This includes
   `drive_file_id`, `drive_file_url`, `resume_filename`, and `resume_status`,
   which are final at append time.
5. **Unknown, unresolved, and low-confidence values are represented
   honestly.** Empty resolver fields mean "resolver has not run" or "could
   not resolve", not "no data existed". Low `parser_confidence` values stay
   visible to reviewers.
6. **Snapshot data is derived, never a source of truth.**

`assert_no_raw_data_overwrite` in `backend/core/state_contract.py` enforces
rules 1, 2, and 4 for any write path that adopts it.

## Where does a new field belong?

When adding a field, ask who produces its value:

- Typed by the volunteer at intake → `submissions`, volunteer-entered group.
- Assigned by the intake/upload pipeline at submission time → `submissions`,
  intake-system group.
- Extracted from the resume by the parser → `parser_results`, parser group.
- Normalized/classified from parser output → `parser_results`, resolver group
  (or a future resolver output tab).
- Decided by a human reviewer → `ops`, reviewer group.
- Records a failure or audit event → `errors` (append-only).
- Computed for display from other tabs → snapshot read model; do not persist.

Then add it to the matching tuple in `backend/core/state_contract.py` and the
table above. The schema-alignment test will fail if the constants drift from
`backend/sheet_schema.py`.

## Out of scope

Schema migration, frontend redesign, parser/resolver quality, and audit/event
history (see the `ops_events` proposal in #290) are intentionally not covered
here.
