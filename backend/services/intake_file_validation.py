"""Central validation for public intake resume uploads."""

from dataclasses import dataclass
from pathlib import PurePath
from typing import Optional

from config import MAX_PDF_MB
from services.pdf_text_extraction import (
    PasswordProtectedPDFError,
    extract_text_from_pdf_bytes,
)


ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_PDF_MIMES = {"application/pdf", "application/x-pdf"}


@dataclass(frozen=True)
class ValidatedResumeUpload:
    pdf_bytes: bytes
    original_filename: str
    content_type: str
    extracted_text: str


class ResumeFileValidationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _normalized_content_type(content_type: Optional[str]) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def _filename_extension(filename: str) -> str:
    return PurePath(filename.strip()).suffix.lower()


def validate_resume_upload(
    *,
    filename: Optional[str],
    content_type: Optional[str],
    file_bytes: Optional[bytes],
) -> ValidatedResumeUpload:
    """Validate and pre-extract an optional public intake PDF upload."""

    if file_bytes is None:
        raise ResumeFileValidationError(
            "MISSING_FILE",
            "No resume file was received.",
            status_code=400,
        )

    original_filename = (filename or "").strip()
    if not original_filename:
        raise ResumeFileValidationError(
            "MISSING_FILE",
            "No resume filename was received.",
            status_code=400,
        )

    if not file_bytes:
        raise ResumeFileValidationError(
            "EMPTY_FILE",
            "The uploaded resume file is empty.",
            status_code=400,
        )

    extension = _filename_extension(original_filename)
    if extension not in ALLOWED_PDF_EXTENSIONS:
        raise ResumeFileValidationError(
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF resume files are supported.",
            status_code=400,
        )

    normalized_content_type = _normalized_content_type(content_type)
    if normalized_content_type and normalized_content_type not in ALLOWED_PDF_MIMES:
        raise ResumeFileValidationError(
            "MIME_TYPE_MISMATCH",
            "The resume filename and declared file type do not agree.",
            status_code=400,
        )

    if len(file_bytes) > MAX_PDF_MB * 1024 * 1024:
        raise ResumeFileValidationError(
            "FILE_TOO_LARGE",
            f"Resume PDF must be {MAX_PDF_MB}MB or smaller.",
            status_code=413,
        )

    if b"%PDF-" not in file_bytes[:1024]:
        raise ResumeFileValidationError(
            "INVALID_PDF",
            "The uploaded resume is not a readable PDF.",
            status_code=400,
        )

    try:
        extracted_text = extract_text_from_pdf_bytes(file_bytes)
    except PasswordProtectedPDFError:
        raise ResumeFileValidationError(
            "INVALID_PDF",
            "The uploaded resume is not a readable PDF.",
            status_code=400,
        )
    except Exception:
        raise ResumeFileValidationError(
            "INVALID_PDF",
            "The uploaded resume is not a readable PDF.",
            status_code=400,
        )

    if not extracted_text.strip():
        raise ResumeFileValidationError(
            "INVALID_PDF",
            "The uploaded resume is not a readable PDF.",
            status_code=400,
        )

    return ValidatedResumeUpload(
        pdf_bytes=file_bytes,
        original_filename=original_filename,
        content_type=normalized_content_type or "application/pdf",
        extracted_text=extracted_text,
    )
