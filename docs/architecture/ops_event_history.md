# Ops Event History (`ops_events`)

Issues #290, #305 and #408. The `ops` tab is the current-state source of truth for
reviewer workflow status, notes, tags, contact tracking, structured coordination intent, and latest
attribution. It stores one latest workflow row per `submission_id`, so later
edits overwrite the previous visible actor and timestamp. The `ops_events`
tab adds append-only, best-effort governance history of reviewer actions so
responsibility for individual changes can be reconstructed when event writes
are available.

## Tab schema

Ordinary workflow writes append one row per changed field. Coordination intent
writes append one state-history row per successful intent, even when the state
value is unchanged:

| Column | Meaning |
| --- | --- |
| `event_id` | Generated UUIDv4 for the event row. |
| `submission_id` | Canonical submission key. |
| `actor_email` | Backend-derived actor for the write (same value as ops `updated_by`). |
| `action` | `create` (first ordinary ops row), `update`, or `coordination_intent`. Offline retention can minimize this to `anonymized`. |
| `field_changed` | `status`, `notes`, `tags`, `contact_tracking`, or `coordination_state` for lifecycle intent. |
| `old_value` | Value before the write (`""` on create); previous `active`/`ended` state or blank for first coordination intent. |
| `new_value` | Value after the write; `active` or `ended` for coordination intent. |
| `created_at` | Event timestamp. |
| `source` | Originating surface; currently `dashboard`. |

## Behavior

- Dashboard writeback (`/ops/update` upsert path) emits events from
  `storage/sheets_repo.py`: the create path records every non-empty initial
  reviewer field, and the update path records only fields whose value
  actually changed. Saving an identical status or note emits nothing.
- `POST /submissions/{submission_id}/coordination` writes current ops first,
  then attempts one `action=coordination_intent`,
  `field_changed=coordination_state` event. First preservation records blank →
  active; end records active → ended; renewed purpose records ended → active.
  Further preservation or repeated end writes can record active → active or
  ended → ended. This records explicit intent, not a complete history of changed
  text. A first coordination write does not additionally emit workflow `create`
  events. These state changes are independent of workflow `status`.
- Purpose, takeaway, WHY, NEXT ACTION, REVISIT, name and contact content are not
  copied into lifecycle event values. Current `ops.coordination` remains their
  authority and owns the lifecycle timestamps; history is not a retention clock
  or an alternative archive of human text.
- `actor_email` is copied from the same backend-derived actor used for
  `ops.updated_by`; actor fields submitted in the request body are ignored by
  ordinary workflow endpoints. Coordination requests instead reject client actor/timestamp fields.
- The current `ops` row remains the fast current-state table for dashboard
  loading; nothing reads `ops_events` on the snapshot path.
- `ops_events` does not replace `ops` for current reviewer workflow state.
- Event history is append-only through dashboard endpoints. The offline
  [retention executor](../deployment/volunteer_data_retention.md) is the explicit
  exception: source expiry, coordination expiry and full deletion clear all
  identifying event cells, retaining only `create`/`update` action counts or
  `anonymized` for other actions, including `coordination_intent`. Event/submission
  IDs, actor, timestamps, field names and values do not survive that minimization.
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
