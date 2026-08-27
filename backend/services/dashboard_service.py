"""Dashboard snapshot composition service."""

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.state_contract import (
    ParserState,
    ResolverState,
    ResumeState,
    derive_submission_health_state,
)
from services.dashboard_errors import summarize_submission_errors
from services.dashboard_ops_state import compose_current_ops_state
from services.dashboard_parser_results import select_latest_parser_result
from sheet_schema import SUBMISSIONS_HEADERS


SubmissionRecord = Mapping[str, Any]
ParserResultRow = Mapping[str, Any]
OpsRow = Mapping[str, Any]
ErrorRow = Mapping[str, Any]
SnapshotRecord = Dict[str, Any]

SNAPSHOT_STORAGE_ONLY_FIELDS = {"submission_id", "drive_file_id"}
RAW_FIELDS = tuple(
    field for field in SUBMISSIONS_HEADERS if field not in SNAPSHOT_STORAGE_ONLY_FIELDS
)
PARSED_FIELDS = (
    "parser_run_id",
    "created_at",
    "parser_version",
    "parsed_skills_raw",
    "parsed_location_raw",
    "parser_confidence",
)
PARSED_OUTPUT_FIELDS = (
    "parsed_skills_raw",
    "parsed_location_raw",
)
RESOLVED_FIELDS = (
    "resolver_version",
    "aliases_version",
    "resolved_skill_ids",
    "unknown_skills",
    "resolver_coverage",
)


def get_snapshot_records() -> List[SnapshotRecord]:
    """
    Load dashboard data layers and compose reviewer-facing snapshot records.

    The row readers stay in storage, while snapshot selection and formatting stay
    in this service layer so API routes can remain thin.
    """
    from storage.sheets_repo import (
        load_error_rows,
        load_ops_rows,
        load_parser_job_rows,
        load_parser_result_rows,
        load_submission_records,
    )

    return assemble_snapshot_records(
        load_submission_records(),
        load_parser_result_rows(),
        load_ops_rows(),
        load_error_rows(),
        load_parser_job_rows(),
    )


def assemble_snapshot_records(
    submissions_by_id: Mapping[str, SubmissionRecord],
    parser_rows: List[ParserResultRow],
    ops_rows: List[OpsRow],
    error_rows: Optional[List[ErrorRow]],
    parser_job_rows: Optional[List[Mapping[str, Any]]] = None,
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
        latest_parser_row = _select_authoritative_or_latest_parser_result(
            submission_id,
            matching_parser_rows,
            parser_job_rows or [],
        )
        errors = _compose_errors_layer(submission_id, error_rows)

        records.append(
            {
                "submission_id": submission_id,
                "submission_health_state": _compose_submission_health_state(
                    submission,
                    latest_parser_row,
                    errors,
                ),
                "raw": _compose_raw_layer(submission),
                "parsed": _compose_parsed_layer(submission, latest_parser_row, errors),
                "resolved": _compose_resolved_layer(submission, latest_parser_row, errors),
                "ops": compose_current_ops_state(submission_id, [dict(row) for row in ops_rows]),
                "errors": errors,
            }
        )

    return records


def _select_authoritative_or_latest_parser_result(
    submission_id: str,
    parser_rows: List[ParserResultRow],
    parser_job_rows: List[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    authoritative_run_id = ""
    for job in parser_job_rows:
        if str(job.get("submission_id", "")).strip() != submission_id:
            continue
        candidate = str(job.get("authoritative_parser_run_id", "")).strip()
        if candidate:
            authoritative_run_id = candidate
            break

    if authoritative_run_id:
        for row in parser_rows:
            if str(row.get("parser_run_id", "")).strip() == authoritative_run_id:
                return dict(row)

    return select_latest_parser_result(parser_rows)


def _compose_raw_layer(submission: SubmissionRecord) -> Dict[str, Any]:
    return {field: _value_or_blank(submission.get(field, "")) for field in RAW_FIELDS}


def _compose_submission_health_state(
    submission: SubmissionRecord,
    parser_row: Optional[Dict[str, Any]],
    errors: Mapping[str, Any],
) -> str:
    return derive_submission_health_state(
        {
            "resume_state": _resume_state_from_submission(submission),
            "parser_state": _parser_state_from_snapshot(submission, parser_row, errors),
            "resolver_state": _resolver_state_from_snapshot(submission, parser_row, errors),
        }
    )


def _resume_state_from_submission(submission: SubmissionRecord) -> str:
    explicit_state = _normalized_text(submission.get("resume_state"))
    if explicit_state:
        return explicit_state

    status = _normalized_text(submission.get("resume_status"))
    if status == "uploaded":
        return ResumeState.UPLOADED.value
    if status == "missing":
        return ResumeState.NONE_PROVIDED.value
    if status == "failed":
        return ResumeState.UPLOAD_FAILED.value
    if status == "pending":
        return ResumeState.UPLOAD_PENDING.value
    return status


def _parser_state_from_snapshot(
    submission: SubmissionRecord,
    parser_row: Optional[Dict[str, Any]],
    errors: Mapping[str, Any],
) -> str:
    explicit_state = _normalized_text(submission.get("parser_state"))
    if explicit_state:
        return explicit_state

    if _resume_state_from_submission(submission) == ResumeState.NONE_PROVIDED.value:
        return ParserState.SKIPPED_NO_RESUME.value
    if parser_row:
        return ParserState.SUCCEEDED.value
    if _latest_error_code(errors) == "PARSER_FAILED":
        return ParserState.FAILED.value
    return ParserState.NOT_STARTED.value


def _resolver_state_from_snapshot(
    submission: SubmissionRecord,
    parser_row: Optional[Dict[str, Any]],
    errors: Mapping[str, Any],
) -> str:
    explicit_state = _normalized_text(submission.get("resolver_state"))
    if explicit_state:
        return explicit_state

    resume_state = _resume_state_from_submission(submission)
    parser_state = _parser_state_from_snapshot(submission, parser_row, errors)
    if resume_state == ResumeState.NONE_PROVIDED.value:
        return ResolverState.SKIPPED_NO_PARSER_OUTPUT.value
    if _latest_error_code(errors) == "RESOLVER_FAILED":
        return ResolverState.FAILED.value
    if parser_state == ParserState.FAILED.value:
        return ResolverState.SKIPPED_NO_PARSER_OUTPUT.value
    if parser_row and _has_resolver_output(parser_row):
        return ResolverState.SUCCEEDED.value
    return ResolverState.NOT_STARTED.value


def _compose_parsed_layer(
    submission: SubmissionRecord,
    parser_row: Optional[Dict[str, Any]],
    errors: Mapping[str, Any],
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "parser_state": "pending",
        "parser_result_state": "not_yet_run",
        "parser_run_id": "",
        "created_at": "",
        "parser_version": "",
        "parsed_skills_raw": "",
        "parsed_location_raw": "",
        "parser_confidence": "",
        "parser_confidence_score": None,
    }

    if not parser_row:
        if _latest_error_code(errors) == "PARSER_FAILED":
            state["parser_result_state"] = "failed"
        elif _resume_state_from_submission(submission) == ResumeState.NONE_PROVIDED.value:
            state["parser_result_state"] = "skipped"
        return state

    state["parser_state"] = "complete"
    state["parser_result_state"] = (
        "available" if _has_any_output(parser_row, PARSED_OUTPUT_FIELDS) else "empty_success"
    )
    for field in PARSED_FIELDS:
        state[field] = _value_or_blank(parser_row.get(field, ""))
    state["parser_confidence_score"] = _bounded_float_or_none(parser_row.get("parser_confidence"))

    return state


def _compose_resolved_layer(
    submission: SubmissionRecord,
    parser_row: Optional[Dict[str, Any]],
    errors: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "resolver_state": "not_run",
        "resolver_result_state": "not_yet_run",
        "resolver_version": "",
        "aliases_version": "",
        "resolved_skill_ids": "",
        "unknown_skills": "",
        "resolver_coverage": "",
        "resolver_coverage_score": None,
    }

    if _latest_error_code(errors or {}) == "RESOLVER_FAILED":
        state["resolver_result_state"] = "failed"
        return state

    if not parser_row:
        if (
            _latest_error_code(errors or {}) == "PARSER_FAILED"
            or _resume_state_from_submission(submission) == ResumeState.NONE_PROVIDED.value
        ):
            state["resolver_result_state"] = "unavailable_upstream"
        return state

    for field in RESOLVED_FIELDS:
        state[field] = _value_or_blank(parser_row.get(field, ""))
    state["resolver_coverage_score"] = _bounded_float_or_none(parser_row.get("resolver_coverage"))

    if not _has_resolver_output(parser_row):
        return state

    state["resolver_state"] = (
        "resolved"
        if _has_resolved_skill_matches(parser_row.get("resolved_skill_ids", ""))
        else "zero_matches"
    )
    state["resolver_result_state"] = (
        "available" if state["resolver_state"] == "resolved" else "empty_success"
    )
    return state


def _compose_errors_layer(
    submission_id: str,
    error_rows: Optional[Sequence[ErrorRow]],
) -> Dict[str, Any]:
    if error_rows is None:
        return {
            "error_state": "unavailable",
            "has_error": False,
            "latest_error_summary": "",
            "latest_error_stage": "",
            "latest_error_code": "",
        }

    errors = summarize_submission_errors(
        submission_id,
        [dict(row) for row in error_rows],
    )
    errors["error_state"] = "present" if errors["has_error"] else "none"
    return errors


def _has_resolver_output(parser_row: Mapping[str, Any]) -> bool:
    return any(_value_or_blank(parser_row.get(field, "")) != "" for field in RESOLVED_FIELDS)


def _has_any_output(parser_row: Mapping[str, Any], fields: Sequence[str]) -> bool:
    return any(_value_or_blank(parser_row.get(field, "")) != "" for field in fields)


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


def _latest_error_code(errors: Mapping[str, Any]) -> str:
    return str(errors.get("latest_error_code") or "").strip().upper()


def _normalized_text(value: Any) -> str:
    return "" if value is None else str(value).strip().lower()


def _value_or_blank(value: Any) -> Any:
    if value is None:
        return ""
    return value


def _bounded_float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None

    if number < 0.0 or number > 1.0:
        return None
    return number
