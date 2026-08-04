"""Intake orchestration: validation, submission_id generation, Drive + Sheets coordination."""
import json
import re
import traceback
import uuid
from typing import Any, Dict, List, Optional, Union

from services.intake_file_validation import (
    ResumeFileValidationError,
    ValidatedResumeUpload,
    validate_resume_upload,
)
from storage.drive_repo import upload_pdf
from storage.sheets_repo import append_error_row, write_base_row


EMAIL_IN_TEXT_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


class IntakeError(Exception):
    """Domain error raised by the intake flow. The route layer translates it to HTTP."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        fields: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.fields = fields


def _is_placeholder_email(value: str) -> bool:
    if not value:
        return True
    v = value.strip().lower()
    return v in {"string", "email", "example", "test", "none", "null", "undefined", "-"}


def _validate_email(email: str) -> bool:
    if not email or _is_placeholder_email(email):
        return False
    return EMAIL_IN_TEXT_RE.search(email.strip()) is not None


def _normalize_email(email: str) -> str:
    if not email:
        return ""
    m = EMAIL_IN_TEXT_RE.search(email.strip())
    return m.group(0) if m else email.strip()


def _parse_interests(raw: Union[str, List[str], None]) -> str:
    if raw is None:
        return ""

    if isinstance(raw, list):
        return ", ".join([str(x).strip() for x in raw if str(x).strip()])

    s = str(raw).strip()
    if not s:
        return ""

    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return ", ".join([str(x).strip() for x in arr if str(x).strip()])
        except Exception:
            pass

    parts = [p.strip() for p in s.split(",") if p.strip()]
    return ", ".join(parts) if parts else s


def _validate_fields(
    *,
    full_name: Optional[str],
    email: Optional[str],
    location: Optional[str],
    interests: Optional[Union[str, List[str]]],
    availability: Optional[str],
    experience_level: Optional[str],
    consent: Optional[bool],
) -> Dict[str, Any]:
    fields: Dict[str, str] = {}

    if not full_name or not full_name.strip():
        fields["full_name"] = "Required"

    normalized_email = _normalize_email(email or "")
    if not _validate_email(normalized_email):
        fields["email"] = "Required and must be a valid email address"

    if not location or not location.strip():
        fields["location"] = "Required"

    normalized_interests = _parse_interests(interests)
    if not normalized_interests.strip():
        fields["interests"] = "Required"

    if not availability or not availability.strip():
        fields["availability"] = "Required"

    if not experience_level or not experience_level.strip():
        fields["experience_level"] = "Required"

    if consent is not True:
        fields["consent"] = "Must be true to submit"

    if fields:
        raise IntakeError("VALIDATION_ERROR", "Invalid fields", status_code=422, fields=fields)

    return {
        "full_name": full_name.strip(),
        "email": normalized_email,
        "location": location.strip(),
        "interests": normalized_interests,
        "availability": availability.strip(),
        "experience_level": experience_level.strip(),
    }

def validate_intake(
    *,
    filename: Optional[str],
    content_type: Optional[str],
    full_name: Optional[str],
    email: Optional[str],
    location: Optional[str],
    interests: Optional[Union[str, List[str]]],
    availability: Optional[str],
    experience_level: Optional[str],
    consent: Optional[bool],
) -> Dict[str, Any]:
    """
    Validate form fields without reading file bytes.

    Raises IntakeError on validation failure. Returns normalized field values for
    the caller to pass to finalize_submission after the PDF bytes have been read.
    """
    normalized = _validate_fields(
        full_name=full_name,
        email=email,
        location=location,
        interests=interests,
        availability=availability,
        experience_level=experience_level,
        consent=consent,
    )
    return normalized


def _build_ui_data(
    normalized: Dict[str, Any],
    linkedin_url: Optional[str],
    github_url: Optional[str],
    motivation: Optional[str],
) -> Dict[str, str]:
    return {
        "name": normalized["full_name"],
        "email": normalized["email"],
        "location": normalized["location"],
        "areas": normalized["interests"],
        "capacity": normalized["availability"],
        "experience": normalized["experience_level"],
        "linkedin": (linkedin_url or "").strip(),
        "github": (github_url or "").strip(),
        "motivation": (motivation or "").strip(),
    }


def finalize_submission(
    *,
    pdf_bytes: Optional[bytes],
    original_filename: Optional[str],
    normalized: Dict[str, Any],
    linkedin_url: Optional[str],
    github_url: Optional[str],
    motivation: Optional[str],
    content_type: Optional[str] = None,
    validated_resume: Optional[ValidatedResumeUpload] = None,
) -> Dict[str, Any]:
    """
    Persist an intake with an optional validated PDF resume.

    Expects `normalized` from a prior validate_intake call. Raises IntakeError on
    resume validation failure. Upload failures are persisted with resume_status=failed.
    """
    submission_id = str(uuid.uuid4())
    ui_data = _build_ui_data(normalized, linkedin_url, github_url, motivation)

    if pdf_bytes is None and not original_filename and not content_type:
        print(f"[UPLOAD] submission_id={submission_id} no resume provided; status=missing")
        write_base_row(
            submission_id=submission_id,
            ui_data=ui_data,
            drive_file_id="",
            resume_filename="",
            resume_status="missing",
        )
        return {
            "submission_id": submission_id,
            "drive_file_id": "",
            "pre_text": "",
            "resume_filename": "",
            "resume_status": "missing",
        }

    if validated_resume is None:
        try:
            validated_resume = validate_resume_upload(
                filename=original_filename,
                content_type=content_type,
                file_bytes=pdf_bytes,
            )
        except ResumeFileValidationError as exc:
            raise IntakeError(exc.code, exc.message, status_code=exc.status_code)

    pre_text = validated_resume.extracted_text

    print(f"[UPLOAD] submission_id={submission_id} uploading to Drive ...")
    try:
        drive_file_id, _, resume_filename = upload_pdf(
            validated_resume.pdf_bytes,
            submission_id,
            validated_resume.original_filename,
        )
    except Exception as exc:
        traceback.print_exc()
        print(
            f"[UPLOAD] Failed submission_id={submission_id} "
            f"error_type={type(exc).__name__}"
        )
        write_base_row(
            submission_id=submission_id,
            ui_data=ui_data,
            drive_file_id="",
            resume_filename="",
            resume_status="failed",
        )
        try:
            append_error_row(
                submission_id=submission_id,
                stage="upload",
                error_code="DRIVE_UPLOAD_FAILED",
                error_summary="Resume upload failed",
                error_details=f"{type(exc).__name__}: {exc}"[:500],
            )
        except Exception:
            traceback.print_exc()
            print(f"[UPLOAD] Error-event write failed submission_id={submission_id}")
        return {
            "submission_id": submission_id,
            "drive_file_id": "",
            "pre_text": "",
            "resume_filename": "",
            "resume_status": "failed",
        }
    print(f"[UPLOAD] Drive uploaded: submission_id={submission_id} file_id={drive_file_id}")

    print(f"[SHEETS] Writing base row for submission_id={submission_id} ...")
    write_base_row(
        drive_file_id=drive_file_id,
        submission_id=submission_id,
        ui_data=ui_data,
        resume_filename=resume_filename,
        resume_status="uploaded",
    )
    print(f"[SHEETS] Base row written for submission_id={submission_id}")

    return {
        "submission_id": submission_id,
        "drive_file_id": drive_file_id,
        "pre_text": pre_text,
        "resume_filename": resume_filename,
        "resume_status": "uploaded",
    }
