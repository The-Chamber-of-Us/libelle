"""Pure error summary helpers for dashboard snapshot composition."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


ErrorRow = Dict[str, Any]
ErrorSummary = Dict[str, Any]


def _created_at_sort_value(created_at: Any) -> Tuple[int, Any]:
    """
    Build a deterministic sort value for created_at.

    Supports the current repo timestamp format and common ISO-like timestamps.
    Falls back to string sorting if parsing fails.
    """
    value = "" if created_at is None else str(created_at).strip()

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


def summarize_submission_errors(
    submission_id: str,
    error_rows: List[ErrorRow],
) -> ErrorSummary:
    """
    Derive lightweight error visibility for one submission_id.

    Selection rule:
        Latest error is the row with the highest created_at for the submission_id.

    Empty state:
        If no matching error rows exist, return a normal no-error summary.

    Scope boundary:
        This helper does not read from Sheets, assemble snapshots, expose raw
        error details, include stack traces, or return full error history.
    """
    matching_rows = [
        row for row in error_rows if str(row.get("submission_id", "")) == submission_id
    ]

    if not matching_rows:
        return {
            "has_error": False,
            "latest_error_summary": "",
            "latest_error_stage": "",
            "latest_error_code": "",
        }

    latest_row = max(
        matching_rows,
        key=lambda row: _created_at_sort_value(row.get("created_at")),
    )

    return {
        "has_error": True,
        "latest_error_summary": latest_row.get("error_summary", ""),
        "latest_error_stage": latest_row.get("stage", ""),
        "latest_error_code": latest_row.get("error_code", ""),
    }