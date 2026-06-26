import uuid

import fitz
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

    def fake_upload(pdf_bytes, submission_id, original_filename):
        captured["drive_submission_id"] = submission_id
        captured["drive_original_filename"] = original_filename
        return (
            "drive-file-id",
            "https://drive.example/view",
            f"{submission_id}_{original_filename}",
        )

    def fake_write_base_row(**kwargs):
        submission_id = kwargs["submission_id"]
        captured["sheets_submission_id"] = submission_id
        captured["row"] = kwargs

    monkeypatch.setattr(intake_service, "_extract_text_from_pdf", fake_extract)
    monkeypatch.setattr(intake_service, "upload_pdf", fake_upload)
    monkeypatch.setattr(intake_service, "write_base_row", fake_write_base_row)


def _finalize():
    return intake_service.finalize_submission(
        pdf_bytes=_VALID_PDF_BYTES,
        original_filename="Test Resume.PDF",
        normalized=_normalized(),
        linkedin_url=None,
        github_url=None,
        motivation=None,
    )


def test_finalize_submission_returns_full_uuidv4(monkeypatch):
    """#129: submission_id must be a full UUIDv4 string, not truncated."""
    _patch_io(monkeypatch, {})

    submission_id = _finalize()["submission_id"]

    parsed = uuid.UUID(submission_id)
    assert parsed.version == 4
    assert str(parsed) == submission_id
    assert len(submission_id) == 36


def test_finalize_submission_threads_same_id_through_drive_and_sheets(monkeypatch):
    """The generated submission_id must be the same one passed to Drive + Sheets writes."""
    captured = {}
    _patch_io(monkeypatch, captured)

    result = _finalize()

    assert captured["drive_submission_id"] == result["submission_id"]
    assert captured["drive_original_filename"] == "Test Resume.PDF"
    assert captured["sheets_submission_id"] == result["submission_id"]
    expected_filename = f"{result['submission_id']}_Test Resume.PDF"
    assert captured["row"]["resume_filename"] == expected_filename
    assert result["resume_filename"] == expected_filename
    assert captured["row"]["resume_status"] == "uploaded"
    assert result["resume_status"] == "uploaded"


def test_finalize_submission_generates_unique_ids(monkeypatch):
    """Two separate intakes must produce distinct submission_ids."""
    _patch_io(monkeypatch, {})

    first = _finalize()
    second = _finalize()

    assert first["submission_id"] != second["submission_id"]


def test_finalize_submission_without_resume_records_missing(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        intake_service,
        "write_base_row",
        lambda **kwargs: captured.update(kwargs),
    )

    result = intake_service.finalize_submission(
        pdf_bytes=None,
        original_filename=None,
        normalized=_normalized(),
        linkedin_url=None,
        github_url=None,
        motivation=None,
    )

    assert result["resume_status"] == "missing"
    assert result["resume_filename"] == ""
    assert result["drive_file_id"] == ""
    assert captured["resume_status"] == "missing"
    assert captured["resume_filename"] == ""


def test_finalize_submission_records_failed_drive_upload(monkeypatch):
    captured = {}
    monkeypatch.setattr(intake_service, "_extract_text_from_pdf", lambda _: "resume text")
    monkeypatch.setattr(
        intake_service,
        "upload_pdf",
        lambda *_: (_ for _ in ()).throw(RuntimeError("Drive unavailable")),
    )
    monkeypatch.setattr(
        intake_service,
        "write_base_row",
        lambda **kwargs: captured.setdefault("row", kwargs),
    )
    monkeypatch.setattr(
        intake_service,
        "append_error_row",
        lambda **kwargs: captured.setdefault("error", kwargs),
    )

    result = _finalize()

    assert result["resume_status"] == "failed"
    assert result["resume_filename"] == ""
    assert captured["row"]["resume_status"] == "failed"
    assert captured["row"]["resume_filename"] == ""
    assert captured["error"]["submission_id"] == result["submission_id"]
    assert captured["error"]["stage"] == "upload"
    assert captured["error"]["error_code"] == "DRIVE_UPLOAD_FAILED"


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("resume.txt", "application/pdf"),
        ("resume.pdf", "text/plain"),
    ],
)
def test_validate_intake_rejects_non_pdf_metadata(filename, content_type):
    with pytest.raises(intake_service.IntakeError) as exc_info:
        intake_service.validate_intake(
            filename=filename,
            content_type=content_type,
            full_name="Test User",
            email="test@example.com",
            location="Remote",
            interests="Engineering",
            availability="Weekly",
            experience_level="Mid",
            consent=True,
        )

    assert exc_info.value.code == "INVALID_FILE_TYPE"


def test_finalize_submission_rejects_invalid_pdf_content(monkeypatch):
    monkeypatch.setattr(intake_service, "write_base_row", lambda **_: None)

    with pytest.raises(intake_service.IntakeError) as exc_info:
        intake_service.finalize_submission(
            pdf_bytes=b"plain text",
            original_filename="resume.pdf",
            normalized=_normalized(),
            linkedin_url=None,
            github_url=None,
            motivation=None,
        )

    assert exc_info.value.code == "INVALID_PDF_CONTENT"


def test_finalize_submission_enforces_configured_size_limit(monkeypatch):
    monkeypatch.setattr(intake_service, "MAX_PDF_MB", 0)

    with pytest.raises(intake_service.IntakeError) as exc_info:
        _finalize()

    assert exc_info.value.code == "FILE_TOO_LARGE"


def test_password_protected_pdf_is_rejected():
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "resume")
    encrypted_pdf = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    doc.close()

    with pytest.raises(intake_service.IntakeError) as exc_info:
        intake_service._extract_text_from_pdf(encrypted_pdf)

    assert exc_info.value.code == "PASSWORD_PROTECTED_PDF"
