# Ops Event History (`ops_events`)

Issues #290 and #305. The `ops` tab is the current-state source of truth for
reviewer workflow status, notes, tags, contact tracking, and latest
attribution. It stores one latest workflow row per `submission_id`, so later
edits overwrite the previous visible actor and timestamp. The `ops_events`
tab adds append-only, best-effort governance history of reviewer actions so
responsibility for individual changes can be reconstructed when event writes
are available.

## Tab schema

One row per changed field per write:

| Column | Meaning |
| --- | --- |
| `event_id` | Generated UUIDv4 for the event row. |
| `submission_id` | Canonical submission key. |
| `actor_email` | Backend-derived actor for the write (same value as ops `updated_by`). |
| `action` | `create` (first ops row for a submission) or `update`. |
| `field_changed` | `status`, `notes`, `tags`, or `contact_tracking`. |
| `old_value` | Value before the write (`""` on create). |
| `new_value` | Value after the write. |
| `created_at` | Event timestamp. |
| `source` | Originating surface; currently `dashboard`. |

## Behavior

- Dashboard writeback (`/ops/update` upsert path) emits events from
  `storage/sheets_repo.py`: the create path records every non-empty initial
  reviewer field, and the update path records only fields whose value
  actually changed. Saving an identical status or note emits nothing.
- The current `ops` row remains the fast current-state table for dashboard
  loading; nothing reads `ops_events` on the snapshot path.
- `ops_events` does not replace `ops` for current reviewer workflow state.
- Event history is append-only and not editable through the dashboard —
  no endpoint writes to or updates this tab besides the append.
- Event appends are best-effort governance records: if the tab is missing
  or the append fails, the ops write still succeeds and a
  `[SHEETS] WARNING` is logged.
- Event history is not a transactional audit guarantee. Sheets writes are not
  committed atomically across `ops` and `ops_events`, and event append failure
  must not block the reviewer writeback path.

## The tab is optional

`ops_events` is declared in `sheet_schema.py` but listed in `OPTIONAL_TABS`.
Startup validation does not require it (existing v0.3 sheets keep working);
if the tab exists, its headers are validated like any other tab. To start
capturing history, add an `ops_events` tab to the sheet with the header row
above.
