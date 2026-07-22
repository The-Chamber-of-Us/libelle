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
                "drive_file_id": "drive-file-1",
                "resume_filename": "sub_001-resume.pdf",
                "resume_status": "uploaded",
            }
        },
    )
    monkeypatch.setattr(
        "storage.drive_repo.find_pdf_by_name",
        lambda filename: (_ for _ in ()).throw(AssertionError("filename lookup is not allowed")),
    )
    monkeypatch.setattr(
        "storage.drive_repo.download_file",
        lambda file_id: b"%PDF test" if file_id == "drive-file-1" else b"",
    )

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
                "drive_file_id": "",
                "resume_filename": "",
                "resume_status": "missing",
            }
        },
    )

    with pytest.raises(ResumeAccessError) as exc_info:
        get_mediated_resume("sub_001", "reviewer@example.org")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "RESUME_NOT_AVAILABLE"


def test_get_mediated_resume_rejects_missing_drive_reference(monkeypatch) -> None:
    monkeypatch.setattr(
        "storage.sheets_repo.load_submission_records",
        lambda: {
            "sub_001": {
                "submission_id": "sub_001",
                "drive_file_id": "",
                "resume_filename": "sub_001-resume.pdf",
                "resume_status": "uploaded",
            }
        },
    )

    with pytest.raises(ResumeAccessError) as exc_info:
        get_mediated_resume("sub_001", "reviewer@example.org")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "RESUME_REFERENCE_BROKEN"


def test_get_mediated_resume_surfaces_broken_drive_download(monkeypatch) -> None:
    monkeypatch.setattr(
        "storage.sheets_repo.load_submission_records",
        lambda: {
            "sub_001": {
                "submission_id": "sub_001",
                "drive_file_id": "missing-drive-file",
                "resume_filename": "sub_001-resume.pdf",
                "resume_status": "uploaded",
            }
        },
    )
    monkeypatch.setattr(
        "storage.drive_repo.download_file",
        lambda file_id: (_ for _ in ()).throw(RuntimeError("Drive 404")),
    )

    with pytest.raises(ResumeAccessError) as exc_info:
        get_mediated_resume("sub_001", "reviewer@example.org")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "RESUME_REFERENCE_BROKEN"
