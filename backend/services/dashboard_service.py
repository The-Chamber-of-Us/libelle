"""Dashboard snapshot composition service."""

import json
from datetime import datetime, timezone
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
ParserJobRow = Mapping[str, Any]
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
        load_parser_result_rows,
        load_submission_records,
    )
    from storage.parser_jobs_repo import list_parser_jobs

    return assemble_snapshot_records(
        load_submission_records(),
        load_parser_result_rows(),
        load_ops_rows(),
        load_error_rows(),
        list_parser_jobs(),
    )


def assemble_snapshot_records(
    submissions_by_id: Mapping[str, SubmissionRecord],
    parser_rows: List[ParserResultRow],
    ops_rows: List[OpsRow],
    error_rows: Optional[List[ErrorRow]],
    parser_job_rows: Optional[List[ParserJobRow]] = None,
    now: Optional[datetime] = None,
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
    parser_jobs_by_submission_id = _index_parser_jobs(parser_job_rows or [])
    observed_at = _normalize_datetime(now or datetime.now(timezone.utc))

    for submission_id, submission in keyed_submissions:
        matching_parser_rows = [
            dict(row)
            for row in parser_rows
            if str(row.get("submission_id", "")).strip() == submission_id
        ]
        latest_parser_row = select_latest_parser_result(matching_parser_rows)
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
                "parser_job": _compose_parser_job_layer(
                    submission_id,
                    parser_jobs_by_submission_id.get(submission_id),
                    observed_at,
                ),
                "ops": compose_current_ops_state(submission_id, [dict(row) for row in ops_rows]),
                "errors": errors,
            }
        )

    return records


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


def _compose_parser_job_layer(
    submission_id: str,
    job: Optional[ParserJobRow],
    now: datetime,
) -> Optional[Dict[str, Any]]:
    if job is None:
        return None

    status = _value_or_blank(job.get("status", ""))
    return {
        "submission_id": submission_id,
        "parser_job_status": status,
        "attempt_count": _nonnegative_int_or_zero(job.get("attempt_count")),
        "max_attempts": _positive_int_or_none(job.get("max_attempts")),
        "parser_run_id": _operational_parser_run_id(job),
        "is_stale": _is_stale_parser_job(job, now),
        "last_error_code": _safe_error_code(job.get("last_error_code")),
        "last_error_summary": _safe_error_summary(job.get("last_error_summary")),
        "available_at": _value_or_blank(job.get("available_at", "")),
        "parser_started_at": _value_or_blank(job.get("parser_started_at", "")),
        "created_at": _value_or_blank(job.get("created_at", "")),
        "updated_at": _value_or_blank(job.get("updated_at", "")),
    }


def _index_parser_jobs(parser_job_rows: Sequence[ParserJobRow]) -> Dict[str, ParserJobRow]:
    indexed: Dict[str, ParserJobRow] = {}
    for row in parser_job_rows:
        submission_id = str(row.get("submission_id", "")).strip()
        if submission_id and submission_id not in indexed:
            indexed[submission_id] = dict(row)
    return indexed


def _operational_parser_run_id(job: ParserJobRow) -> str:
    authoritative_parser_run_id = _value_or_blank(
        job.get("authoritative_parser_run_id", "")
    )
    if authoritative_parser_run_id:
        return authoritative_parser_run_id
    return _value_or_blank(job.get("last_parser_run_id", ""))


def _is_stale_parser_job(job: ParserJobRow, now: datetime) -> bool:
    if _normalized_text(job.get("status")) != "running":
        return False

    lock_expires_at = _parse_timestamp(job.get("lock_expires_at", ""))
    return lock_expires_at is not None and lock_expires_at < now


def _parse_timestamp(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None

    for fmt in ("%m-%d-%Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

    return _normalize_datetime(parsed)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _nonnegative_int_or_zero(value: Any) -> int:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _positive_int_or_none(value: Any) -> Optional[int]:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _safe_error_code(value: Any) -> Optional[str]:
    code = str(value or "").strip().upper()
    return code or None


def _safe_error_summary(value: Any) -> Optional[str]:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return None
    return text[:240]


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
