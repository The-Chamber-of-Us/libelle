"""Pure dashboard snapshot composition service."""

import json
from typing import Any, Dict, List, Mapping, Optional

from services.dashboard_errors import summarize_submission_errors
from services.dashboard_ops_state import compose_current_ops_state
from services.dashboard_parser_results import select_latest_parser_result
from sheet_schema import SUBMISSIONS_HEADERS


SubmissionRecord = Mapping[str, Any]
ParserResultRow = Mapping[str, Any]
OpsRow = Mapping[str, Any]
ErrorRow = Mapping[str, Any]
SnapshotRecord = Dict[str, Any]

RAW_FIELDS = tuple(field for field in SUBMISSIONS_HEADERS if field != "submission_id")
PARSED_FIELDS = (
    "parser_run_id",
    "created_at",
    "parser_version",
    "parsed_skills_raw",
    "parsed_location_raw",
    "parser_confidence",
)
RESOLVED_FIELDS = (
    "resolver_version",
    "aliases_version",
    "resolved_skill_ids",
    "unknown_skills",
    "resolver_coverage",
)


def assemble_snapshot_records(
    submissions_by_id: Mapping[str, SubmissionRecord],
    parser_rows: List[ParserResultRow],
    ops_rows: List[OpsRow],
    error_rows: List[ErrorRow],
) -> List[SnapshotRecord]:
    """
    Compose reviewer-facing dashboard snapshot records from preloaded data layers.

    This is a deterministic, side-effect-free composition layer. It performs no
    direct I/O and constructs new dictionaries rather than mutating inputs.
    """
    records: List[SnapshotRecord] = []

    keyed_submissions = sorted(
        (
            (str(submission_id).strip(), submission)
            for submission_id, submission in submissions_by_id.items()
            if str(submission_id).strip()
        ),
        key=lambda item: item[0],
    )

    for submission_id, submission in keyed_submissions:
        matching_parser_rows = [
            dict(row)
            for row in parser_rows
            if str(row.get("submission_id", "")).strip() == submission_id
        ]
        latest_parser_row = select_latest_parser_result(matching_parser_rows)

        records.append(
            {
                "submission_id": submission_id,
                "raw": _compose_raw_layer(submission),
                "parsed": _compose_parsed_layer(latest_parser_row),
                "resolved": _compose_resolved_layer(latest_parser_row),
                "ops": compose_current_ops_state(submission_id, [dict(row) for row in ops_rows]),
                "errors": summarize_submission_errors(
                    submission_id,
                    [dict(row) for row in error_rows],
                ),
            }
        )

    return records


def _compose_raw_layer(submission: SubmissionRecord) -> Dict[str, Any]:
    return {field: _value_or_blank(submission.get(field, "")) for field in RAW_FIELDS}


def _compose_parsed_layer(parser_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "parser_state": "pending",
        "parser_run_id": "",
        "created_at": "",
        "parser_version": "",
        "parsed_skills_raw": "",
        "parsed_location_raw": "",
        "parser_confidence": "",
    }

    if not parser_row:
        return state

    state["parser_state"] = "complete"
    for field in PARSED_FIELDS:
        state[field] = _value_or_blank(parser_row.get(field, ""))

    return state


def _compose_resolved_layer(parser_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "resolver_state": "not_run",
        "resolver_version": "",
        "aliases_version": "",
        "resolved_skill_ids": "",
        "unknown_skills": "",
        "resolver_coverage": "",
    }

    if not parser_row:
        return state

    for field in RESOLVED_FIELDS:
        state[field] = _value_or_blank(parser_row.get(field, ""))

    if not _has_resolver_output(parser_row):
        return state

    state["resolver_state"] = (
        "resolved"
        if _has_resolved_skill_matches(parser_row.get("resolved_skill_ids", ""))
        else "zero_matches"
    )
    return state


def _has_resolver_output(parser_row: Mapping[str, Any]) -> bool:
    return any(_value_or_blank(parser_row.get(field, "")) != "" for field in RESOLVED_FIELDS)


def _has_resolved_skill_matches(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, list):
        return len(value) > 0

    text = str(value).strip()
    if not text:
        return False

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return True

    if isinstance(parsed, list):
        return len(parsed) > 0

    return bool(parsed)


def _value_or_blank(value: Any) -> Any:
    if value is None:
        return ""
    return value
