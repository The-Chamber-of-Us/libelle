"""Bounded backend mediation for reviewer resume access."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediatedResume:
    submission_id: str
    filename: str
    content: bytes


class ResumeAccessError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_detail(self) -> dict[str, str]:
        return {
            "status": "error",
            "code": self.code,
            "message": self.message,
        }


def get_mediated_resume(submission_id: str, actor: str) -> MediatedResume:
    """
    Resolve and proxy one uploaded resume for an authenticated internal actor.

    Submission rows are the source of truth for whether a resume exists and
    which Drive file id belongs to that submission. The client supplies only the
    submission_id; filenames and Drive URLs are never trusted as lookup inputs.
    """
    normalized_submission_id = _normalize_required(submission_id, "submission_id")
    normalized_actor = _normalize_required(actor, "actor")

    try:
        from storage.drive_repo import download_file
        from storage.sheets_repo import load_submission_records

        submission = load_submission_records().get(normalized_submission_id)
        if submission is None:
            raise ResumeAccessError(
                status_code=404,
                code="SUBMISSION_NOT_FOUND",
                message="No submission found for submission_id.",
            )

        resume_reference = _resume_reference_from_submission(submission)
        if resume_reference is None:
            raise ResumeAccessError(
                status_code=404,
                code="RESUME_NOT_AVAILABLE",
                message="No uploaded resume is available for this submission.",
            )

        drive_file_id, filename = resume_reference
        if not drive_file_id:
            raise ResumeAccessError(
                status_code=502,
                code="RESUME_REFERENCE_BROKEN",
                message="Resume metadata exists, but its Drive file reference is missing.",
            )

        try:
            content = download_file(drive_file_id)
        except Exception as exc:  # noqa: BLE001
            raise ResumeAccessError(
                status_code=502,
                code="RESUME_REFERENCE_BROKEN",
                message="Resume metadata exists, but the Drive file could not be retrieved.",
            ) from exc

        _log_resume_access(
            submission_id=normalized_submission_id,
            actor=normalized_actor,
            outcome="served",
            filename=filename,
            drive_file_id=drive_file_id,
        )
        return MediatedResume(
            submission_id=normalized_submission_id,
            filename=filename,
            content=content,
        )
    except ResumeAccessError as exc:
        _log_resume_access(
            submission_id=normalized_submission_id,
            actor=normalized_actor,
            outcome="denied",
            reason=exc.code,
        )
        raise


def _resume_reference_from_submission(submission: Mapping[str, Any]) -> tuple[str, str] | None:
    resume_status = str(submission.get("resume_status", "")).strip().lower()
    if resume_status != "uploaded":
        return None

    drive_file_id = str(submission.get("drive_file_id", "")).strip()
    filename = str(submission.get("resume_filename", "")).strip()
    if not filename:
        filename = f"{str(submission.get('submission_id', '')).strip() or 'resume'}-resume.pdf"
    return drive_file_id, filename


def _normalize_required(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ResumeAccessError(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"{field_name} is required.",
        )
    return normalized


def _log_resume_access(
    *,
    submission_id: str,
    actor: str,
    outcome: str,
    filename: str = "",
    drive_file_id: str = "",
    reason: str = "",
) -> None:
    event = {
        "event": "resume_access",
        "submission_id": submission_id,
        "actor": actor,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": outcome,
        "filename": filename,
        "drive_file_id": drive_file_id,
        "reason": reason,
    }
    logger.info("resume_access %s", json.dumps(event, sort_keys=True))
