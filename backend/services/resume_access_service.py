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

    The v0.3 submissions sheet stores resume presence and filename, but not a
    durable Drive file id. This service keeps the mediation narrow by resolving
    the expected uploaded PDF by filename inside the configured Drive folder.
    """
    normalized_submission_id = _normalize_required(submission_id, "submission_id")
    normalized_actor = _normalize_required(actor, "actor")

    try:
        from storage.drive_repo import download_file, find_pdf_by_name
        from storage.sheets_repo import load_submission_records

        submission = load_submission_records().get(normalized_submission_id)
        if submission is None:
            raise ResumeAccessError(
                status_code=404,
                code="SUBMISSION_NOT_FOUND",
                message="No submission found for submission_id.",
            )

        filename = _resume_filename_from_submission(submission)
        if filename is None:
            raise ResumeAccessError(
                status_code=404,
                code="RESUME_NOT_AVAILABLE",
                message="No uploaded resume is available for this submission.",
            )

        drive_file = find_pdf_by_name(filename)
        if drive_file is None or not str(drive_file.get("id", "")).strip():
            raise ResumeAccessError(
                status_code=404,
                code="RESUME_FILE_NOT_FOUND",
                message="Resume metadata exists, but the file is unavailable.",
            )

        drive_file_id = str(drive_file["id"]).strip()
        try:
            content = download_file(drive_file_id)
        except Exception as exc:
            raise ResumeAccessError(
                status_code=502,
                code="RESUME_FETCH_FAILED",
                message="Resume file exists, but could not be retrieved from storage.",
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


def _resume_filename_from_submission(submission: Mapping[str, Any]) -> str | None:
    resume_status = str(submission.get("resume_status", "")).strip().lower()
    filename = str(submission.get("resume_filename", "")).strip()
    if resume_status != "uploaded" or not filename:
        return None
    return filename


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
