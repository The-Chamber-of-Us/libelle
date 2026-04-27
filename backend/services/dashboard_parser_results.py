"""Pure parser_results selection helpers for dashboard snapshot composition."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


ParserResultRow = Dict[str, Any]


def _parser_run_sort_value(parser_run_id: Any) -> Tuple[int, Any]:
    """
    Build a deterministic sort value for parser_run_id.

    Numeric-looking IDs are sorted numerically so "10" is newer than "2".
    Other IDs are sorted as strings.
    """
    value = "" if parser_run_id is None else str(parser_run_id).strip()

    if value.isdigit():
        return (1, int(value))

    return (0, value)


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


def select_latest_parser_result(
    parser_rows: List[ParserResultRow],
) -> Optional[ParserResultRow]:
    """
    Select the latest parser_results row for one submission_id.

    Selection rule:
        1. Choose the row with the highest parser_run_id.
        2. If parser_run_id ties, choose the latest created_at.

    Empty state:
        If no parser_results rows exist, return None. This is a valid
        parser-pending state and should not block snapshot assembly.

    Scope boundary:
        This helper does not read from Sheets, assemble snapshots, modify parser
        behavior, compose ops state, or summarize errors.
    """
    if not parser_rows:
        return None

    latest_row = max(
        parser_rows,
        key=lambda row: (
            _parser_run_sort_value(row.get("parser_run_id")),
            _created_at_sort_value(row.get("created_at")),
        ),
    )

    return dict(latest_row)