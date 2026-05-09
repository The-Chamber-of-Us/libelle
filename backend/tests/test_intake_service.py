import uuid

import pytest

from services import intake_service


_VALID_PDF_BYTES = b"%PDF-1.4 stub"


def _normalized():
    return {
        "full_name": "Test User",
        "email": "test@example.com",
        "location": "Remote",
        "interests": "ai",
        "availability": "weekly",
        "experience_level": "beginner",
    }


def _patch_io(monkeypatch, captured):
    def fake_extract(pdf_bytes):
        return "extracted resume text"

    def fake_upload(pdf_bytes, submission_id):
        captured["drive_submission_id"] = submission_id
        return ("drive-file-id", "https://drive.example/view")

    def fake_write_base_row(*, drive_file_id, drive_file_url, submission_id, ui_data):
        captured["sheets_submission_id"] = submission_id

    monkeypatch.setattr(intake_service, "_extract_text_from_pdf", fake_extract)
    monkeypatch.setattr(intake_service, "upload_pdf", fake_upload)
    monkeypatch.setattr(intake_service, "write_base_row", fake_write_base_row)


def test_finalize_submission_returns_full_uuidv4(monkeypatch):
    """#129: submission_id must be a full UUIDv4 string, not truncated."""
    captured = {}
    _patch_io(monkeypatch, captured)

    result = intake_service.finalize_submission(
        pdf_bytes=_VALID_PDF_BYTES,
        normalized=_normalized(),
        linkedin_url=None,
        github_url=None,
        motivation=None,
    )

    submission_id = result["submission_id"]
    parsed = uuid.UUID(submission_id)
    assert parsed.version == 4
    assert str(parsed) == submission_id
    assert len(submission_id) == 36


def test_finalize_submission_threads_same_id_through_drive_and_sheets(monkeypatch):
    """The generated submission_id must be the same one passed to Drive + Sheets writes."""
    captured = {}
    _patch_io(monkeypatch, captured)

    result = intake_service.finalize_submission(
        pdf_bytes=_VALID_PDF_BYTES,
        normalized=_normalized(),
        linkedin_url=None,
        github_url=None,
        motivation=None,
    )

    assert captured["drive_submission_id"] == result["submission_id"]
    assert captured["sheets_submission_id"] == result["submission_id"]


def test_finalize_submission_generates_unique_ids(monkeypatch):
    """Two separate intakes must produce distinct submission_ids."""
    captured = {}
    _patch_io(monkeypatch, captured)

    first = intake_service.finalize_submission(
        pdf_bytes=_VALID_PDF_BYTES,
        normalized=_normalized(),
        linkedin_url=None,
        github_url=None,
        motivation=None,
    )
    second = intake_service.finalize_submission(
        pdf_bytes=_VALID_PDF_BYTES,
        normalized=_normalized(),
        linkedin_url=None,
        github_url=None,
        motivation=None,
    )

    assert first["submission_id"] != second["submission_id"]
