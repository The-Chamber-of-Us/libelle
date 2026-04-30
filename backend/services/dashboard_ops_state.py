"""Pure ops state helpers for dashboard snapshot composition."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ops_schema import OPS_STATUS_NEW, is_valid_ops_status
from sheet_schema import OPS_HEADERS


OpsRow = Dict[str, Any]
OpsState = Dict[str, Any]

OPS_STATE_FIELDS = tuple(field for field in OPS_HEADERS if field != "submission_id")


def _updated_at_sort_value(updated_at: Any) -> Tuple[int, Any]:
    """
    Build a deterministic sort value for updated_at.

    Supports the current repo timestamp format and common ISO-like timestamps.
    Falls back to string sorting if parsing fails.
    """
    value = "" if updated_at is None else str(updated_at).strip()

    for fmt in (
        "%m-%d-%Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (1, dt.timestamp())
        except ValueError:
            continue

    return (0, value)


def format_current_ops_state(ops_row: Optional[OpsRow]) -> OpsState:
    """
    Format the current ops row for snapshot output.

    Empty state:
        If no ops row exists, return a complete default workflow state with
        status "new" and blank optional fields.

    Contract boundary:
        This helper emits only repo-owned ops schema fields used by the
        snapshot read model. It does not write ops data, enforce state
        transitions, or expose ops history.
    """
    state = {
        "status": OPS_STATUS_NEW,
        "notes": "",
        "tags": "",
        "contact_tracking": "",
        "updated_at": "",
        "updated_by": "",
    }

    if not ops_row:
        return state

    for field in OPS_STATE_FIELDS:
        value = ops_row.get(field, "")
        state[field] = str(value).strip() if value is not None else ""

    if not is_valid_ops_status(state["status"]):
        state["status"] = OPS_STATUS_NEW

    return state


def compose_current_ops_state(
    submission_id: str,
    ops_rows: List[OpsRow],
) -> OpsState:
    """
    Select and format the current ops state for one submission_id.

    Selection rule:
        Choose the matching row with the latest updated_at timestamp.

    Empty state:
        If no matching row exists, return the default "new" workflow state.
    """
    matching_rows = [
        row for row in ops_rows if str(row.get("submission_id", "")).strip() == submission_id
    ]

    if not matching_rows:
        return format_current_ops_state(None)

    latest_row = max(
        matching_rows,
        key=lambda row: _updated_at_sort_value(row.get("updated_at")),
    )

    return format_current_ops_state(latest_row)
