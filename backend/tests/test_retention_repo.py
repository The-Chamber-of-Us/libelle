from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from sheet_schema import SHEET_SCHEMA, build_row
from storage.retention_repo import (DeletionIncomplete, delete_submissions,
                                    expired_submission_ids, read_inventory)


class Sheet:
    def __init__(self):
        self.rows = {tab: [headers.copy()] for tab, headers in SHEET_SCHEMA.items()}
        self.requests = []
        self.fail = False

    def values(self):
        return self

    def get(self, **kwargs):
        if "range" in kwargs:
            result = {"values": deepcopy(self.rows[kwargs["range"].strip("'")])}
        else:
            result = {"sheets": [{"properties": {"title": tab, "sheetId": i}}
                                 for i, tab in enumerate(self.rows)]}
        return Mock(execute=Mock(return_value=result))

    def batchUpdate(self, **kwargs):
        def execute():
            if self.fail:
                raise RuntimeError("sensitive API failure")
            self.requests.extend(kwargs["body"]["requests"])
            for request in kwargs["body"]["requests"]:
                op = next(iter(request.values()))
                region = op["range"]
                tab = list(self.rows)[region["sheetId"]]
                if "deleteDimension" in request:
                    del self.rows[tab][region["startIndex"]:region["endIndex"]]
                else:
                    self.rows[tab][region["startRowIndex"]] = [
                        v["userEnteredValue"]["stringValue"] for v in op["rows"][0]["values"]]
        return Mock(execute=execute)

    def add(self, tab, **row):
        self.rows[tab].append(build_row(tab, row))


def populated():
    sheet = Sheet()
    for tab in SHEET_SCHEMA:
        for sid in ("target", "other", "target"):
            row = {"submission_id": sid}
            if tab in {"submissions", "parser_jobs"}:
                row["drive_file_id"] = sid + "-file"
            if tab == "ops_events":
                row.update(old_value="private", new_value="private", actor_email="private", action="update")
            sheet.add(tab, **row)
    return sheet


def test_preview_and_delete_all_duplicates_and_anonymize_history(tmp_path):
    sheet, drive = populated(), Mock()
    before = deepcopy(sheet.rows)
    assert not delete_submissions(sheet, drive, "sheet", ["target"])["applied"]
    assert sheet.rows == before
    drive.files.assert_not_called()
    result = delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json")
    assert result["applied"]
    drive.files().delete.assert_called_once_with(fileId="target-file")
    for tab, rows in sheet.rows.items():
        assert not any("target" in row for row in rows)
        assert before[tab][2] in rows
    assert all("private" not in row for row in (sheet.rows["ops_events"][1], sheet.rows["ops_events"][3]))
    assert delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json")["drive_files"] == 0


def test_drive_failure_keeps_sheet_references_and_does_not_leak_error(tmp_path):
    sheet, drive = populated(), Mock()
    before = deepcopy(sheet.rows)
    drive.files().delete().execute.side_effect = RuntimeError("private")
    with pytest.raises(DeletionIncomplete, match="incomplete") as exc:
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json")
    assert "private" not in str(exc.value)
    assert sheet.rows == before


def test_sheet_failure_retry_with_explicit_absence_attestation(tmp_path):
    sheet, drive = populated(), Mock()
    sheet.fail = True
    with pytest.raises(DeletionIncomplete):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json")
    sheet.fail = False
    drive.reset_mock()
    assert delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json",
                              confirmed_absent=["target-file"])["applied"]
    drive.files.assert_not_called()


def test_shared_file_and_unknown_schema_block_before_drive(tmp_path):
    sheet, drive = populated(), Mock()
    sheet.add("parser_jobs", submission_id="other", drive_file_id="target-file")
    with pytest.raises(DeletionIncomplete, match="shared"):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json")
    drive.files.assert_not_called()
    sheet.rows["unknown"] = [["submission_id"]]
    with pytest.raises(DeletionIncomplete, match="Uninventoried"):
        read_inventory(sheet, "sheet")


def test_expiry_boundary_and_malformed_timestamp():
    sheet = Sheet()
    sheet.add("submissions", submission_id="old", created_at="09-25-2025 00:00:00 UTC")
    sheet.add("submissions", submission_id="new", created_at="2026-09-25T00:00:00Z")
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)
    assert expired_submission_ids(read_inventory(sheet, "sheet"), now) == {"old"}
    sheet.add("submissions", submission_id="bad", created_at="")
    with pytest.raises(DeletionIncomplete, match="timestamp"):
        expired_submission_ids(read_inventory(sheet, "sheet"), now)


def test_verification_failure_is_not_success(tmp_path):
    sheet, drive = populated(), Mock()
    sheet.batchUpdate = Mock(return_value=Mock(execute=Mock(return_value={})))
    with pytest.raises(DeletionIncomplete):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json")


def test_optional_events_tab_and_missing_resume_reference(tmp_path):
    sheet, drive = Sheet(), Mock()
    del sheet.rows["ops_events"]
    sheet.add("submissions", submission_id="target", resume_status="uploaded")
    with pytest.raises(DeletionIncomplete, match="reference"):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json")
    drive.files.assert_not_called()


def test_deleted_data_absent_from_snapshot_and_resume(monkeypatch, tmp_path):
    from services.dashboard_service import assemble_snapshot_records
    from services.resume_access_service import get_mediated_resume, ResumeAccessError
    from storage import sheets_repo

    sheet = populated()
    delete_submissions(sheet, Mock(), "sheet", ["target"], apply=True, manifest_path=tmp_path / "receipt.json")
    inventory = read_inventory(sheet, "sheet")
    submissions = {row["submission_id"]: row for _, row in inventory["submissions"][1]}
    rows = lambda tab: [row for _, row in inventory[tab][1]]
    result = assemble_snapshot_records(submissions, rows("parser_results"), rows("ops"),
                                      rows("errors"), rows("parser_jobs"))
    assert {row["submission_id"] for row in result} == {"other"}
    monkeypatch.setattr(sheets_repo, "load_submission_records", lambda: submissions)
    with pytest.raises(ResumeAccessError) as exc:
        get_mediated_resume("target", "reviewer@example.org")
    assert exc.value.status_code == 404


def test_api_responses_are_not_cacheable(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from api.routes import dashboard

    monkeypatch.setattr(dashboard, "get_snapshot_records", lambda: [])
    response = TestClient(app).get("/snapshot")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_manifest_precedes_drive_and_resume_skips_confirmed_deletions(tmp_path):
    from storage.deletion_manifest import load_manifest
    sheet, drive = populated(), Mock()
    path = tmp_path / "receipt.json"
    def check_receipt(**kwargs):
        receipt = load_manifest(path)
        assert receipt["submission_ids"] == ["target"]
        assert receipt["drive_file_ids"] == ["target-file"]
        assert receipt["state"] == "deleting"
        return Mock(execute=Mock(return_value={}))
    drive.files().delete.side_effect = check_receipt
    sheet.fail = True
    with pytest.raises(DeletionIncomplete, match="SHEETS_DELETE_FAILED"):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)
    assert load_manifest(path)["deleted_drive_ids"] == ["target-file"]
    sheet.fail = False
    drive.reset_mock()
    delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)
    drive.files.assert_not_called()
    assert load_manifest(path)["state"] == "stores_deleted"


def test_manifest_failure_and_selection_change_block_drive(tmp_path):
    from storage.deletion_manifest import ManifestError
    sheet, drive = populated(), Mock()
    path = tmp_path / "missing" / "receipt.json"
    with pytest.raises(ManifestError, match="MANIFEST_WRITE_FAILED"):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)
    drive.files.assert_not_called()
    path = tmp_path / "receipt.json"
    delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)
    drive.reset_mock()
    with pytest.raises(ManifestError, match="MANIFEST_MISMATCH"):
        delete_submissions(sheet, drive, "sheet", ["other"], apply=True, manifest_path=path)
    drive.files.assert_not_called()


def test_manifest_rejects_symlink_and_public_permissions(tmp_path):
    from storage.deletion_manifest import load_manifest, ManifestError
    path = tmp_path / "receipt.json"
    delete_submissions(populated(), Mock(), "sheet", ["target"], apply=True, manifest_path=path)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(ManifestError):
        load_manifest(link)
    path.chmod(0o644)
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_expiry_includes_orphans_and_rejects_unkeyed_personal_data():
    sheet = Sheet()
    sheet.add("parser_results", submission_id="orphan", parsed_skills_raw="personal")
    sheet.add("ops_events", action="update")  # Already minimized, no source required.
    assert expired_submission_ids(read_inventory(sheet, "sheet")) == {"orphan"}
    sheet.add("submissions", email="private@example.org")
    with pytest.raises(DeletionIncomplete, match="UNKEYED_RECORD"):
        read_inventory(sheet, "sheet")


def test_lost_sheet_response_can_resume_after_rows_are_gone(tmp_path):
    from storage.deletion_manifest import load_manifest
    sheet, drive = populated(), Mock()
    path = tmp_path / "receipt.json"
    original = sheet.batchUpdate
    def lost_response(**kwargs):
        def execute():
            original(**kwargs).execute()
            raise TimeoutError("private transport info")
        return Mock(execute=execute)
    sheet.batchUpdate = lost_response
    with pytest.raises(DeletionIncomplete, match="SHEETS_DELETE_FAILED"):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)
    drive.reset_mock()
    delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)
    drive.files.assert_not_called()
    assert load_manifest(path)["submission_ids"] == ["target"]


def test_ambiguous_drive_404_requires_owner_attestation(tmp_path):
    from googleapiclient.errors import HttpError
    from httplib2 import Response
    sheet, drive = populated(), Mock()
    path = tmp_path / "receipt.json"
    drive.files().delete().execute.side_effect = HttpError(Response({"status": "404"}), b"private")
    with pytest.raises(DeletionIncomplete, match="DRIVE_DELETE_FAILED"):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)
    drive.reset_mock()
    assert delete_submissions(sheet, drive, "sheet", ["target"], apply=True,
        manifest_path=path, confirmed_absent=["target-file"])["applied"]
    drive.files.assert_not_called()
