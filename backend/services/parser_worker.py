"""Durable polling worker for parser_jobs."""
from __future__ import annotations

import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

from parser import parse_resume
from services.parser_service import _add_resolver_output, _exception_details
from services.pdf_text_extraction import extract_text_from_pdf_bytes
from storage.drive_repo import download_file
from storage.parser_jobs_repo import (
    STATUS_FAILED,
    STATUS_RETRY_SCHEDULED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    claim_job,
    get_job,
    list_claimable_jobs,
    update_job,
)
from storage.sheets_repo import (
    append_error_row,
    persist_parser_result_if_missing,
    persist_resolver_output_for_parser_result,
)


@dataclass(frozen=True)
class ParserWorkerConfig:
    worker_id: str
    poll_interval_seconds: float = 5.0
    lease_seconds: int = 900
    batch_size: int = 1


class ParserWorker:
    """Single-active-worker parser job poller."""

    def __init__(
        self,
        config: ParserWorkerConfig,
        *,
        parser_run_id_factory: Callable[[], str] | None = None,
    ):
        self.config = config
        self._parser_run_id_factory = parser_run_id_factory or (lambda: str(uuid.uuid4()))

    def run_once(self) -> int:
        """Claim and process currently eligible jobs once. Returns jobs completed or attempted."""
        jobs = list_claimable_jobs(limit=self.config.batch_size)
        processed = 0

        for job in jobs:
            parser_run_id = self._parser_run_id_factory()
            claim = claim_job(
                job_id=job["job_id"],
                worker_id=self.config.worker_id,
                parser_run_id=parser_run_id,
                lease_seconds=self.config.lease_seconds,
            )
            if not claim.claimed or not claim.job:
                continue

            processed += 1
            self._execute_attempt(claim.job, parser_run_id)

        return processed

    def poll_forever(self) -> None:
        while True:
            try:
                self.run_once()
            except Exception as exc:  # noqa: BLE001
                print(f"[PARSER_WORKER] Poll iteration failed: {type(exc).__name__}: {exc}")
                traceback.print_exc()
            time.sleep(self.config.poll_interval_seconds)

    def _execute_attempt(self, job: Dict[str, str], parser_run_id: str) -> None:
        job_id = job["job_id"]
        submission_id = job["submission_id"]

        if not self._lease_ok(job_id, parser_run_id):
            return

        if not self._mark_parser_started(job):
            return

        try:
            parsed = self._run_parser(job)
        except Exception as exc:  # noqa: BLE001
            self._record_attempt_failure(
                job_id=job_id,
                submission_id=submission_id,
                parser_run_id=parser_run_id,
                stage="parser",
                error_code="PARSER_FAILED",
                error_summary="Parser failed",
                exc=exc,
                schedule_retry=True,
            )
            return

        parsed["submission_id"] = submission_id
        parsed["drive_file_id"] = job.get("drive_file_id", "")
        parsed["parser_run_id"] = parser_run_id

        if not self._lease_ok(job_id, parser_run_id):
            return

        try:
            persist_parser_result_if_missing(
                submission_id=submission_id,
                parser_run_id=parser_run_id,
                parsed=parsed,
            )
        except Exception as exc:  # noqa: BLE001
            self._record_attempt_failure(
                job_id=job_id,
                submission_id=submission_id,
                parser_run_id=parser_run_id,
                stage="parser_result",
                error_code="PARSER_RESULT_PERSIST_FAILED",
                error_summary="Parser result persistence failed",
                exc=exc,
                schedule_retry=True,
            )
            return

        resolver_failed = False
        if not self._lease_ok(job_id, parser_run_id):
            return

        try:
            _add_resolver_output(parsed, submission_id)
        except Exception as exc:  # noqa: BLE001
            resolver_failed = True
            self._record_attempt_failure(
                job_id=job_id,
                submission_id=submission_id,
                parser_run_id=parser_run_id,
                stage="resolver",
                error_code="RESOLVER_FAILED",
                error_summary="Resolver failed",
                exc=exc,
                schedule_retry=False,
            )

        if not resolver_failed:
            if not self._lease_ok(job_id, parser_run_id):
                return
            try:
                persist_resolver_output_for_parser_result(
                    submission_id=submission_id,
                    parser_run_id=parser_run_id,
                    parsed=parsed,
                )
            except Exception as exc:  # noqa: BLE001
                self._record_attempt_failure(
                    job_id=job_id,
                    submission_id=submission_id,
                    parser_run_id=parser_run_id,
                    stage="resolver",
                    error_code="RESOLVER_PERSIST_FAILED",
                    error_summary="Resolver persistence failed",
                    exc=exc,
                    schedule_retry=False,
                )

        if not self._lease_ok(job_id, parser_run_id):
            return

        self._mark_succeeded(job_id, parser_run_id)

    def _run_parser(self, job: Dict[str, str]) -> Dict:
        pdf_bytes = download_file(job.get("drive_file_id", ""))
        resume_text = extract_text_from_pdf_bytes(pdf_bytes)
        return parse_resume(resume_text or "")

    def _lease_ok(self, job_id: str, parser_run_id: str) -> bool:
        job = get_job(job_id)
        if not job:
            return False
        if job.get("status") != STATUS_RUNNING:
            return False
        if job.get("locked_by") != self.config.worker_id:
            return False
        if job.get("last_parser_run_id") != parser_run_id:
            return False
        lock_expires_at = _parse_timestamp(job.get("lock_expires_at", ""))
        if lock_expires_at is None or lock_expires_at <= datetime.now(timezone.utc):
            return False
        return True

    def _mark_parser_started(self, job: Dict[str, str]) -> bool:
        job_id = job["job_id"]
        fields = {"updated_at": _format_timestamp(datetime.now(timezone.utc))}
        if not job.get("parser_started_at"):
            fields["parser_started_at"] = fields["updated_at"]
        update_job(job_id, fields)
        return self._lease_ok(job_id, job["last_parser_run_id"])

    def _mark_succeeded(self, job_id: str, parser_run_id: str) -> None:
        current = get_job(job_id)
        if not current:
            return
        existing_authority = current.get("authoritative_parser_run_id", "")
        if existing_authority and existing_authority != parser_run_id:
            return
        update_job(
            job_id,
            {
                "status": STATUS_SUCCEEDED,
                "authoritative_parser_run_id": parser_run_id,
                "last_error_code": "",
                "last_error_summary": "",
                "updated_at": _format_timestamp(datetime.now(timezone.utc)),
            },
        )

    def _record_attempt_failure(
        self,
        *,
        job_id: str,
        submission_id: str,
        parser_run_id: str,
        stage: str,
        error_code: str,
        error_summary: str,
        exc: Exception,
        schedule_retry: bool,
    ) -> None:
        if not self._lease_ok(job_id, parser_run_id):
            return

        try:
            append_error_row(
                submission_id=submission_id,
                parser_run_id=parser_run_id,
                stage=stage,
                error_code=error_code,
                error_summary=error_summary,
                error_details=_exception_details(exc),
            )
        except Exception as logging_exc:  # noqa: BLE001
            print(
                "[PARSER_WORKER] Error-event write failed "
                f"submission_id={submission_id} parser_run_id={parser_run_id}: {logging_exc}"
            )
            traceback.print_exc()

        if schedule_retry and self._lease_ok(job_id, parser_run_id):
            self._mark_failed_or_retry(job_id, error_code, error_summary)

    def _mark_failed_or_retry(
        self,
        job_id: str,
        error_code: str,
        error_summary: str,
    ) -> None:
        current = get_job(job_id)
        if not current:
            return

        attempt_count = _safe_int(current.get("attempt_count"), default=1)
        max_attempts = _safe_int(current.get("max_attempts"), default=3)
        exhausted = attempt_count >= max_attempts
        now = datetime.now(timezone.utc)
        fields = {
            "status": STATUS_FAILED if exhausted else STATUS_RETRY_SCHEDULED,
            "available_at": ""
            if exhausted
            else _format_timestamp(now + timedelta(seconds=_retry_delay_seconds(attempt_count))),
            "locked_by": "",
            "locked_at": "",
            "lock_expires_at": "",
            "last_error_code": error_code,
            "last_error_summary": error_summary[:250],
            "updated_at": _format_timestamp(now),
        }
        update_job(job_id, fields)


def _safe_int(value: object, *, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _retry_delay_seconds(attempt_count: int) -> int:
    if attempt_count <= 1:
        return 60
    return 300


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%m-%d-%Y %H:%M:%S %Z")


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
