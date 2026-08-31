"""Recovery scanner for uploaded submissions missing durable parser jobs."""
from dataclasses import dataclass, field
from typing import Dict, List

from storage import parser_jobs_repo, sheets_repo


@dataclass(frozen=True)
class ReconciliationFailure:
    submission_id: str
    logical_job_key: str
    reason: str


@dataclass(frozen=True)
class ReconciliationSummary:
    scanned: int = 0
    eligible: int = 0
    recovered: int = 0
    skipped_existing_job: int = 0
    skipped_successful_result: int = 0
    skipped_not_uploaded: int = 0
    failures: List[ReconciliationFailure] = field(default_factory=list)


def reconcile_missing_parser_jobs() -> ReconciliationSummary:
    """
    Create missing logical parser jobs for uploaded submissions.

    A submission is eligible only when it is uploaded, has no logical parser job,
    and has no successful parser result. This routine never executes parser
    work and never updates submissions or parser_results.
    """
    submissions = sheets_repo.load_submission_records()
    successful_result_submission_ids = _successful_parser_result_submission_ids(
        sheets_repo.load_parser_result_rows()
    )

    scanned = 0
    eligible = 0
    recovered = 0
    skipped_existing_job = 0
    skipped_successful_result = 0
    skipped_not_uploaded = 0
    failures: List[ReconciliationFailure] = []

    for submission_id, submission in sorted(submissions.items()):
        scanned += 1
        logical_key = parser_jobs_repo.logical_idempotency_key(submission_id)

        if str(submission.get("resume_status", "")).strip().lower() != "uploaded":
            skipped_not_uploaded += 1
            continue

        existing_job = parser_jobs_repo.get_parser_job_by_submission(submission_id)
        if existing_job is not None:
            skipped_existing_job += 1
            continue

        if submission_id in successful_result_submission_ids:
            skipped_successful_result += 1
            continue

        eligible += 1
        try:
            parser_jobs_repo.create_parser_job(
                submission_id=submission_id,
                drive_file_id=submission.get("drive_file_id", ""),
                resume_filename=submission.get("resume_filename", ""),
            )
            recovered += 1
            print(
                "[PARSER_RECONCILE] recovered "
                f"submission_id={submission_id} logical_job_key={logical_key}"
            )
        except Exception as exc:  # noqa: BLE001
            reason = type(exc).__name__
            failures.append(
                ReconciliationFailure(
                    submission_id=submission_id,
                    logical_job_key=logical_key,
                    reason=reason,
                )
            )
            print(
                "[PARSER_RECONCILE] failed "
                f"submission_id={submission_id} logical_job_key={logical_key} "
                f"reason={reason}"
            )

    return ReconciliationSummary(
        scanned=scanned,
        eligible=eligible,
        recovered=recovered,
        skipped_existing_job=skipped_existing_job,
        skipped_successful_result=skipped_successful_result,
        skipped_not_uploaded=skipped_not_uploaded,
        failures=failures,
    )


def _successful_parser_result_submission_ids(
    rows: List[Dict[str, str]]
) -> set[str]:
    submission_ids: set[str] = set()
    for row in rows:
        submission_id = str(row.get("submission_id", "")).strip()
        if submission_id:
            submission_ids.add(submission_id)
    return submission_ids
