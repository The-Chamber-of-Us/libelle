import logging

import pytest

from services import resume_access_service
from services.resume_access_service import ResumeAccessError, get_mediated_resume


def test_get_mediated_resume_downloads_uploaded_resume(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        "storage.sheets_repo.load_submission_records",
        lambda: {
            "sub_001": {
                "submission_id": "sub_001",
                "resume_filename": "sub_001-resume.pdf",
                "resume_status": "uploaded",
            }
        },
    )
    monkeypatch.setattr(
        "storage.drive_repo.find_pdf_by_name",
        lambda filename: {"id": "drive-file-1", "name": filename},
    )
    monkeypatch.setattr("storage.drive_repo.download_file", lambda file_id: b"%PDF test")

    with caplog.at_level(logging.INFO, logger=resume_access_service.__name__):
        resume = get_mediated_resume(" sub_001 ", " reviewer@example.org ")

    assert resume.submission_id == "sub_001"
    assert resume.filename == "sub_001-resume.pdf"
    assert resume.content == b"%PDF test"
    assert "resume_access" in caplog.text
    assert '"actor": "reviewer@example.org"' in caplog.text
    assert '"outcome": "served"' in caplog.text
    assert '"submission_id": "sub_001"' in caplog.text


def test_get_mediated_resume_rejects_missing_submission(monkeypatch, caplog) -> None:
    monkeypatch.setattr("storage.sheets_repo.load_submission_records", lambda: {})

    with caplog.at_level(logging.INFO, logger=resume_access_service.__name__):
        with pytest.raises(ResumeAccessError) as exc_info:
            get_mediated_resume("sub_missing", "reviewer@example.org")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "SUBMISSION_NOT_FOUND"
    assert '"outcome": "denied"' in caplog.text
    assert '"reason": "SUBMISSION_NOT_FOUND"' in caplog.text


def test_get_mediated_resume_rejects_submission_without_uploaded_resume(monkeypatch) -> None:
    monkeypatch.setattr(
        "storage.sheets_repo.load_submission_records",
        lambda: {
            "sub_001": {
                "submission_id": "sub_001",
                "resume_filename": "",
                "resume_status": "missing",
            }
        },
    )

    with pytest.raises(ResumeAccessError) as exc_info:
        get_mediated_resume("sub_001", "reviewer@example.org")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "RESUME_NOT_AVAILABLE"


def test_get_mediated_resume_rejects_missing_drive_file(monkeypatch) -> None:
    monkeypatch.setattr(
        "storage.sheets_repo.load_submission_records",
        lambda: {
            "sub_001": {
                "submission_id": "sub_001",
                "resume_filename": "sub_001-resume.pdf",
                "resume_status": "uploaded",
            }
        },
    )
    monkeypatch.setattr("storage.drive_repo.find_pdf_by_name", lambda filename: None)

    with pytest.raises(ResumeAccessError) as exc_info:
        get_mediated_resume("sub_001", "reviewer@example.org")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "RESUME_FILE_NOT_FOUND"


def test_get_mediated_resume_surfaces_download_failure_as_fetch_error(
    monkeypatch, caplog
) -> None:
    monkeypatch.setattr(
        "storage.sheets_repo.load_submission_records",
        lambda: {
            "sub_001": {
                "submission_id": "sub_001",
                "resume_filename": "sub_001-resume.pdf",
                "resume_status": "uploaded",
            }
        },
    )
    monkeypatch.setattr(
        "storage.drive_repo.find_pdf_by_name",
        lambda filename: {"id": "drive-file-1", "name": filename},
    )

    def failing_download(file_id):
        raise RuntimeError("drive api unavailable")

    monkeypatch.setattr("storage.drive_repo.download_file", failing_download)

    with caplog.at_level(logging.INFO, logger=resume_access_service.__name__):
        with pytest.raises(ResumeAccessError) as exc_info:
            get_mediated_resume("sub_001", "reviewer@example.org")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "RESUME_FETCH_FAILED"
    assert '"outcome": "denied"' in caplog.text
    assert '"reason": "RESUME_FETCH_FAILED"' in caplog.text


def test_get_mediated_resume_treats_failed_upload_as_no_resume(monkeypatch) -> None:
    monkeypatch.setattr(
        "storage.sheets_repo.load_submission_records",
        lambda: {
            "sub_001": {
                "submission_id": "sub_001",
                "resume_filename": "sub_001-resume.pdf",
                "resume_status": "failed",
            }
        },
    )

    with pytest.raises(ResumeAccessError) as exc_info:
        get_mediated_resume("sub_001", "reviewer@example.org")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "RESUME_NOT_AVAILABLE"
