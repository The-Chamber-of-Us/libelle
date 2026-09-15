from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict


class ErrorEventV1(TypedDict):
    submission_id: str
    parser_run_id: str
    created_at: str
    stage: str
    error_code: str
    error_summary: str
    error_details: str


def _utc_timestamp() -> str:
    """
    Return the current UTC timestamp in ISO 8601 format with a trailing 'Z'.

    Example:
        2026-04-21T17:42:13Z
    """
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_error_event(
    submission_id: str,
    stage: str,
    error_code: str,
    error_summary: str,
    error_details: str = "",
    parser_run_id: str = "",
    created_at: str | None = None,
) -> ErrorEventV1:
    """
    Build a strict v0.3 error event dictionary aligned to the repo-owned PRD schema.

    This helper is intentionally pure:
    - it performs no I/O
    - it returns a plain structured dict
    - it auto-generates a UTC timestamp when created_at is not provided

    Args:
        submission_id: The submission identifier associated with the failure.
        stage: The pipeline stage where the failure occurred.
        error_code: A stable machine-readable error code.
        error_summary: A concise human-readable error summary.
        error_details: Optional additional error details. Defaults to "".
        created_at: Optional precomputed UTC timestamp. If omitted, one is generated.

    Returns:
        ErrorEventV1: Strictly formatted error event dictionary.
    """
    return {
        "submission_id": submission_id,
        "parser_run_id": parser_run_id or "",
        "created_at": created_at or _utc_timestamp(),
        "stage": stage,
        "error_code": error_code,
        "error_summary": error_summary,
        "error_details": error_details or "",
    }
