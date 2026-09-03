"""
Sheets-backed repository for durable parser jobs.

Concurrency contract:
    Google Sheets is the v0.4 persistence substrate for parser_jobs, but it is
    not a queue or a distributed lock service. This repository provides a
    logical read-model contract for one active polling worker per queue. It
    reduces accidental duplicate enqueue/claim behavior and re-reads after
    claim writes, but it cannot atomically enforce uniqueness or fencing.

    If duplicate physical rows exist for the same logical
    parse_resume:{submission_id} job, reads choose one deterministic canonical
    row and attach duplicate metadata so the anomaly is diagnosable. Downstream
    code should use this repository rather than treating duplicate rows as
    independent active parser jobs.
"""
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import GOOGLE_SHEET_ID
from sheet_schema import build_row, get_headers
from storage.sheets_repo import _get_sheet, _local_timestamp


PARSER_JOBS_SHEET_NAME = "parser_jobs"

JOB_TYPE_PARSE_RESUME = "parse_resume"
VALID_JOB_TYPES = (JOB_TYPE_PARSE_RESUME,)

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_RETRY_SCHEDULED = "retry_scheduled"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_ENQUEUE_FAILED = "enqueue_failed"
VALID_JOB_STATUSES = (
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_RETRY_SCHEDULED,
    STATUS_SUCCEEDED,
    STATUS_FAILED,
    STATUS_ENQUEUE_FAILED,
)
CLAIMABLE_STATUSES = (STATUS_QUEUED, STATUS_RETRY_SCHEDULED)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LEASE_SECONDS = 15 * 60

_parser_jobs_write_lock = threading.Lock()


@dataclass(frozen=True)
class ClaimResult:
    """Observed result of a Sheets claim write after re-reading the job row."""

    claimed: bool
    job: Optional[Dict[str, str]]


def logical_idempotency_key(
    submission_id: str,
    job_type: str = JOB_TYPE_PARSE_RESUME,
) -> str:
    """Return the logical enqueue key used by the initial parser job."""
    normalized_submission_id = _required_str("submission_id", submission_id)
    _validate_job_type(job_type)
    return f"{job_type}:{normalized_submission_id}"


def create_parser_job(
    *,
    submission_id: str,
    drive_file_id: str,
    resume_filename: str = "",
    job_id: Optional[str] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    available_at: Optional[str] = None,
) -> Dict[str, str]:
    """
    Create or return the existing logical parse_resume job for a submission.

    Logical uniqueness is derived from parse_resume:{submission_id}. Sheets
    cannot atomically enforce that uniqueness, so concurrent callers can still
    race between lookup and append. Repeated non-racing calls return the
    canonical observed job instead of intentionally appending duplicate active
    work.
    """
    normalized_submission_id = _required_str("submission_id", submission_id)
    normalized_drive_file_id = _required_str("drive_file_id", drive_file_id)
    normalized_max_attempts = _validate_int("max_attempts", max_attempts, minimum=1)

    with _parser_jobs_write_lock:
        existing = get_parser_job_by_submission(normalized_submission_id)
        if existing is not None:
            return existing

        timestamp = _local_timestamp()
        row_data = {
            "job_id": str(job_id).strip() if job_id else str(uuid.uuid4()),
            "submission_id": normalized_submission_id,
            "drive_file_id": normalized_drive_file_id,
            "resume_filename": str(resume_filename or "").strip(),
            "job_type": JOB_TYPE_PARSE_RESUME,
            "status": STATUS_QUEUED,
            "attempt_count": "0",
            "max_attempts": str(normalized_max_attempts),
            "available_at": available_at or timestamp,
            "locked_by": "",
            "locked_at": "",
            "lock_expires_at": "",
            "last_parser_run_id": "",
            "authoritative_parser_run_id": "",
            "parser_started_at": "",
            "last_error_code": "",
            "last_error_summary": "",
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        _append_job_row(row_data)
        return row_data


def get_job(job_id: str) -> Optional[Dict[str, str]]:
    """Return the deterministic canonical row for job_id, if observed."""
    normalized_job_id = _required_str("job_id", job_id)
    matches = [
        (row_number, row)
        for row_number, row in _load_parser_job_rows_with_sheet_row_numbers()
        if row.get("job_id", "") == normalized_job_id
    ]
    return _canonicalize_matches(matches)


def get_parser_job_by_submission(submission_id: str) -> Optional[Dict[str, str]]:
    """
    Return the logical parse_resume job for a submission, not a parser attempt.
    """
    normalized_submission_id = _required_str("submission_id", submission_id)
    matches = [
        (row_number, row)
        for row_number, row in _load_parser_job_rows_with_sheet_row_numbers()
        if row.get("submission_id", "") == normalized_submission_id
        and row.get("job_type", "") == JOB_TYPE_PARSE_RESUME
    ]
    return _canonicalize_matches(matches)


def list_parser_jobs() -> List[Dict[str, str]]:
    """
    Return canonical logical parse_resume jobs for operational read models.

    Duplicate physical rows for the same logical job are collapsed in the same
    way as point reads so callers do not expose raw Sheets rows as queue state.
    """
    rows_by_logical_key: Dict[str, List[tuple[int, Dict[str, str]]]] = {}
    for row_number, row in _load_parser_job_rows_with_sheet_row_numbers():
        if row.get("job_type", "") != JOB_TYPE_PARSE_RESUME:
            continue
        submission_id = row.get("submission_id", "")
        if not submission_id:
            continue
        rows_by_logical_key.setdefault(
            logical_idempotency_key(submission_id, row.get("job_type", "")),
            [],
        ).append((row_number, row))

    jobs = [
        canonical
        for canonical in (
            _canonicalize_matches(matches)
            for matches in rows_by_logical_key.values()
        )
        if canonical is not None
    ]
    jobs.sort(
        key=lambda row: (
            row.get("submission_id", ""),
            _timestamp_sort_key(row.get("created_at", "")),
            row.get("job_id", ""),
        )
    )
    return jobs


def list_claimable_jobs(
    *,
    now: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    List jobs that currently appear eligible for a worker to claim.

    This is a polling aid, not an atomic reservation. The initial Sheets-backed
    deployment supports one active polling worker per queue.
    """
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    rows_by_logical_key: Dict[str, List[tuple[int, Dict[str, str]]]] = {}
    for row_number, row in _load_parser_job_rows_with_sheet_row_numbers():
        if row.get("job_type", "") != JOB_TYPE_PARSE_RESUME:
            continue
        submission_id = row.get("submission_id", "")
        if not submission_id:
            continue
        rows_by_logical_key.setdefault(
            logical_idempotency_key(submission_id, row.get("job_type", "")),
            [],
        ).append((row_number, row))

    claimable: List[Dict[str, str]] = []
    for matches in rows_by_logical_key.values():
        row = _canonicalize_matches(matches)
        if row is None:
            continue
        if row.get("status", "") not in CLAIMABLE_STATUSES:
            continue
        if not _timestamp_is_due(row.get("available_at", ""), observed_at):
            continue
        claimable.append(row)

    claimable.sort(
        key=lambda row: (
            _timestamp_sort_key(row.get("available_at", "")),
            row.get("job_id", ""),
        )
    )
    if limit is not None:
        return claimable[: _validate_int("limit", limit, minimum=0)]
    return claimable


def claim_job(
    *,
    job_id: str,
    worker_id: str,
    parser_run_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: Optional[datetime] = None,
) -> ClaimResult:
    """
    Persist an intended claim and report whether it is currently observed.

    The write sets status=running, increments attempt_count, stores the worker
    lease fields, and records last_parser_run_id. The row is then re-read and
    the result is confirmed only if that same worker/run is still observed.
    This is not a hard fencing guarantee because Sheets has no atomic
    compare-and-swap primitive.
    """
    normalized_job_id = _required_str("job_id", job_id)
    normalized_worker_id = _required_str("worker_id", worker_id)
    normalized_parser_run_id = _required_str("parser_run_id", parser_run_id)
    normalized_lease_seconds = _validate_int(
        "lease_seconds",
        lease_seconds,
        minimum=1,
    )
    claimed_at_dt = now or datetime.now(timezone.utc)
    if claimed_at_dt.tzinfo is None:
        claimed_at_dt = claimed_at_dt.replace(tzinfo=timezone.utc)

    with _parser_jobs_write_lock:
        located = _find_job_with_row_number(normalized_job_id)
        if located is None:
            return ClaimResult(claimed=False, job=None)

        sheet_row_number, current = located
        if current.get("status", "") not in CLAIMABLE_STATUSES:
            return ClaimResult(claimed=False, job=current)
        if not _timestamp_is_due(current.get("available_at", ""), claimed_at_dt):
            return ClaimResult(claimed=False, job=current)
        attempt_count = _parse_nonnegative_int(current.get("attempt_count", "0"))
        if attempt_count is None:
            return ClaimResult(claimed=False, job=current)

        claimed_at = _format_timestamp(claimed_at_dt)
        lock_expires_at = _format_timestamp(
            claimed_at_dt + timedelta(seconds=normalized_lease_seconds)
        )
        updated = dict(current)
        updated.update(
            {
                "status": STATUS_RUNNING,
                "attempt_count": str(attempt_count + 1),
                "locked_by": normalized_worker_id,
                "locked_at": claimed_at,
                "lock_expires_at": lock_expires_at,
                "last_parser_run_id": normalized_parser_run_id,
                "updated_at": claimed_at,
            }
        )
        _update_job_row(sheet_row_number, updated)

        observed = get_job(normalized_job_id)
        claimed = bool(
            observed
            and observed.get("status") == STATUS_RUNNING
            and observed.get("locked_by") == normalized_worker_id
            and observed.get("last_parser_run_id") == normalized_parser_run_id
            and observed.get("lock_expires_at") == lock_expires_at
        )
        return ClaimResult(claimed=claimed, job=observed)


def update_job(job_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Update mutable job-state fields in place.

    This intentionally does not implement higher-level parser finalization,
    retry policy, authoritative result selection, or stale-worker fencing.
    Later worker code must apply those rules before calling this primitive.
    """
    normalized_job_id = _required_str("job_id", job_id)
    if not fields:
        return get_job(normalized_job_id)

    mutable_fields = {
        "status",
        "attempt_count",
        "max_attempts",
        "available_at",
        "locked_by",
        "locked_at",
        "lock_expires_at",
        "last_parser_run_id",
        "authoritative_parser_run_id",
        "parser_started_at",
        "last_error_code",
        "last_error_summary",
        "updated_at",
    }
    unknown_fields = [field for field in fields if field not in mutable_fields]
    if unknown_fields:
        raise ValueError(
            f"Unsupported parser job update field(s): {', '.join(unknown_fields)}"
        )

    if "status" in fields:
        _validate_status(fields["status"])
    if "attempt_count" in fields:
        fields["attempt_count"] = str(
            _validate_int("attempt_count", fields["attempt_count"], minimum=0)
        )
    if "max_attempts" in fields:
        fields["max_attempts"] = str(
            _validate_int("max_attempts", fields["max_attempts"], minimum=1)
        )

    with _parser_jobs_write_lock:
        located = _find_job_with_row_number(normalized_job_id)
        if located is None:
            return None

        sheet_row_number, current = located
        updated = dict(current)
        for field, value in fields.items():
            updated[field] = str(value).strip() if value is not None else ""
        if "updated_at" not in fields:
            updated["updated_at"] = _local_timestamp()
        _update_job_row(sheet_row_number, updated)
        return get_job(normalized_job_id)


def _append_job_row(row_data: Dict[str, Any]) -> None:
    _get_sheet().values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{PARSER_JOBS_SHEET_NAME}!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [build_row(PARSER_JOBS_SHEET_NAME, row_data)]},
    ).execute()


def _update_job_row(sheet_row_number: int, row_data: Dict[str, Any]) -> None:
    headers = get_headers(PARSER_JOBS_SHEET_NAME)
    end_column = _column_letter(len(headers))
    schema_data = {header: row_data.get(header, "") for header in headers}
    _get_sheet().values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{PARSER_JOBS_SHEET_NAME}!A{sheet_row_number}:{end_column}{sheet_row_number}",
        valueInputOption="RAW",
        body={"values": [build_row(PARSER_JOBS_SHEET_NAME, schema_data)]},
    ).execute()


def _load_parser_job_rows_with_sheet_row_numbers() -> List[tuple[int, Dict[str, str]]]:
    headers = get_headers(PARSER_JOBS_SHEET_NAME)
    response = _get_sheet().values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{PARSER_JOBS_SHEET_NAME}!A2:ZZ",
    ).execute()

    records: List[tuple[int, Dict[str, str]]] = []
    for sheet_row_number, raw_row in enumerate(response.get("values", []), start=2):
        padded_row = list(raw_row) + [""] * (len(headers) - len(raw_row))
        row_dict = {
            header: str(value).strip() if value is not None else ""
            for header, value in zip(headers, padded_row)
        }
        if not row_dict.get("job_id", ""):
            continue
        records.append((sheet_row_number, row_dict))
    return records


def _find_job_with_row_number(job_id: str) -> Optional[tuple[int, Dict[str, str]]]:
    matches = [
        (row_number, row)
        for row_number, row in _load_parser_job_rows_with_sheet_row_numbers()
        if row.get("job_id", "") == job_id
    ]
    return _canonicalize_matches_with_row_number(matches)


def _canonicalize_matches(matches: List[tuple[int, Dict[str, str]]]) -> Optional[Dict[str, str]]:
    canonical = _canonicalize_matches_with_row_number(matches)
    if canonical is None:
        return None
    return canonical[1]


def _canonicalize_matches_with_row_number(
    matches: List[tuple[int, Dict[str, str]]]
) -> Optional[tuple[int, Dict[str, str]]]:
    if not matches:
        return None

    sorted_matches = sorted(
        matches,
        key=lambda item: (
            _timestamp_sort_key(item[1].get("created_at", "")),
            item[0],
            item[1].get("job_id", ""),
        ),
    )
    canonical_row_number, canonical = sorted_matches[0]
    if len(sorted_matches) > 1:
        duplicates = [row.get("job_id", "") for _, row in sorted_matches[1:]]
        canonical = dict(canonical)
        canonical["_sheet_row_number"] = str(canonical_row_number)
        canonical["_duplicate_count"] = str(len(sorted_matches) - 1)
        canonical["_duplicate_job_ids"] = ",".join(duplicates)
    return canonical_row_number, canonical


def _timestamp_is_due(value: str, now: datetime) -> bool:
    if not str(value or "").strip():
        return True
    parsed = _parse_timestamp(value)
    return parsed is not None and parsed <= now


def _timestamp_sort_key(value: str) -> datetime:
    if not str(value or "").strip():
        return datetime.min.replace(tzinfo=timezone.utc)
    return _parse_timestamp(value) or datetime.max.replace(tzinfo=timezone.utc)


def _parse_timestamp(value: str) -> Optional[datetime]:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    for fmt in ("%m-%d-%Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%m-%d-%Y %H:%M:%S %Z")


def _column_letter(one_based_index: int) -> str:
    result = ""
    index = one_based_index
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _required_str(field_name: str, value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _validate_job_type(job_type: Any) -> None:
    if str(job_type or "").strip() not in VALID_JOB_TYPES:
        raise ValueError(f"Unsupported parser job type: {job_type}")


def _validate_status(status: Any) -> None:
    if str(status or "").strip() not in VALID_JOB_STATUSES:
        raise ValueError(f"Unsupported parser job status: {status}")


def _validate_int(field_name: str, value: Any, *, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return parsed


def _parse_nonnegative_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed
