"""Intake orchestration: validation, submission_id generation, Drive + Sheets coordination."""
import json
import re
import traceback
import uuid
from typing import Any, Dict, List, Optional, Union

import fitz

from config import MAX_PDF_MB
from storage.drive_repo import upload_pdf
from storage.sheets_repo import write_base_row


ALLOWED_PDF_MIMES = {"application/pdf", "application/x-pdf"}
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


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join([p.get_text("text") for p in doc])
        doc.close()
        return text
    except Exception:
        traceback.print_exc()
        raise IntakeError("PDF_PARSE_FAILED", "PDF parsing failed", status_code=400)


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


def _validate_file_type(filename: str, content_type: Optional[str]) -> None:
    if content_type not in ALLOWED_PDF_MIMES and not filename.lower().endswith(".pdf"):
        raise IntakeError("INVALID_FILE_TYPE", "Only PDF files supported", status_code=400)


def _validate_file_size(pdf_bytes: bytes) -> None:
    if len(pdf_bytes) > MAX_PDF_MB * 1024 * 1024:
        raise IntakeError(
            "FILE_TOO_LARGE",
            f"PDF too large (>{MAX_PDF_MB}MB)",
            status_code=400,
        )


def process_submission(
    *,
    filename: str,
    content_type: Optional[str],
    pdf_bytes: bytes,
    full_name: Optional[str],
    email: Optional[str],
    location: Optional[str],
    interests: Optional[Union[str, List[str]]],
    availability: Optional[str],
    experience_level: Optional[str],
    linkedin_url: Optional[str],
    github_url: Optional[str],
    motivation: Optional[str],
    consent: Optional[bool],
) -> Dict[str, Any]:
    """
    Validate the intake, upload the resume to Drive, and append the base row to Sheets.

    Raises IntakeError on any validation or extraction failure. Returns a dict with
    submission_id, drive_file_id, drive_file_url, and pre_text (for the parser job).
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

    _validate_file_type(filename, content_type)
    _validate_file_size(pdf_bytes)

    pre_text = _extract_text_from_pdf(pdf_bytes)
    if not pre_text.strip():
        raise IntakeError("NO_TEXT_EXTRACTED", "PDF has no extractable text", status_code=400)

    submission_id = str(uuid.uuid4())[:8]

    print(f"[UPLOAD] submission_id={submission_id} uploading to Drive ...")
    drive_file_id, drive_file_url = upload_pdf(pdf_bytes, submission_id)
    print(f"[UPLOAD] Drive uploaded: file_id={drive_file_id}")

    ui_data = {
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

    print(f"[SHEETS] Writing base row for submission_id={submission_id} ...")
    write_base_row(
        drive_file_id=drive_file_id,
        drive_file_url=drive_file_url,
        submission_id=submission_id,
        ui_data=ui_data,
    )
    print(f"[SHEETS] Base row written for submission_id={submission_id}")

    return {
        "submission_id": submission_id,
        "drive_file_id": drive_file_id,
        "drive_file_url": drive_file_url,
        "pre_text": pre_text,
    }
