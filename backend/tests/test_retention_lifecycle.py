"""Issue #408 lifecycle integration through the actual offline deletion adapter."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from core.coordination_lifecycle import CoordinationIntent, apply_intent
from services.dashboard_service import assemble_snapshot_records
from sheet_schema import SHEET_SCHEMA
from storage.deletion_manifest import ManifestError, load_manifest
from storage.retention_repo import DeletionIncomplete, delete_submissions, orphan_submission_ids, read_inventory
from tests.test_retention_repo import Sheet

NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


def coordination(ended=False):
    request = CoordinationIntent(action="preserve", purpose="Ongoing project", context_reviewed=True,
                                 takeaway="Arrange a call", why="Follow up", next_action="Email",
                                 revisit="2026-10-01", display_name="Chosen name", contact="reviewed contact")
    active = apply_intent(None, request, "reviewer@example.org", NOW)
    return apply_intent(active, request.model_copy(update={"action": "end"}), "reviewer@example.org", NOW) if ended else active


def fixture(ended=False):
    sheet = Sheet()
    sheet.add("submissions", submission_id="target", drive_file_id="pdf", resume_status="uploaded",
              email="source@example.org", created_at="2000-01-01T00:00:00Z")
    sheet.add("parser_jobs", submission_id="target", drive_file_id="pdf")
    sheet.add("parser_results", submission_id="target", parsed_skills_raw="source skills")
    sheet.add("errors", submission_id="target", error_details="source details")
    sheet.add("ops", submission_id="target", status="paused", notes="Current reviewed context",
              coordination=coordination(ended).model_dump_json(), updated_at="2099-01-01T00:00:00Z")
    sheet.add("ops_events", submission_id="target", old_value="unreviewed old note", action="update")
    for tab in SHEET_SCHEMA:
        sheet.add(tab, submission_id="other")
    return sheet


def snapshot(sheet):
    inventory = read_inventory(sheet, "sheet")
    rows = lambda tab: [r for _, r in inventory[tab][1]]
    return assemble_snapshot_records({r["submission_id"]: r for r in rows("submissions")},
                                     rows("parser_results"), rows("ops"), rows("errors"), rows("parser_jobs"))


@pytest.mark.parametrize("ended", [False, True])
def test_source_expiry_preserves_current_context_removes_source_and_old_history(tmp_path, ended):
    sheet, drive = fixture(ended), Mock()
    before = deepcopy(sheet.rows)
    result = delete_submissions(sheet, drive, "sheet", ["target"], reason="source_expiry", apply=True,
                                manifest_path=tmp_path / "source.json")
    assert result["applied"]
    assert sheet.rows["ops"] == before["ops"]
    drive.files().delete.assert_called_once_with(fileId="pdf")
    for tab in SHEET_SCHEMA:
        assert before[tab][-1] in sheet.rows[tab]
    retained = next(row for row in snapshot(sheet) if row["submission_id"] == "target")
    assert retained["source_state"] == "unavailable"
    assert retained["coordination"]["takeaway"] == "Arrange a call"
    assert retained["coordination"]["why"] == "Follow up"
    assert retained["coordination"]["next_action"] == "Email"
    assert retained["coordination"]["revisit"] == "2026-10-01"
    assert retained["ops"]["status"] == "paused"
    assert "source@example.org" not in str(sheet.rows)
    assert "unreviewed old note" not in str(sheet.rows)
    assert orphan_submission_ids(read_inventory(sheet, "sheet")) == set()


def test_later_coordination_expiry_uses_end_time_not_edit_time_and_never_deletes_source(tmp_path):
    sheet, drive = fixture(ended=True), Mock()
    before = deepcopy(sheet.rows)
    result = delete_submissions(sheet, drive, "sheet", ["target"], reason="coordination_expiry",
                                approved_coordination_cutoff=NOW, apply=True, manifest_path=tmp_path / "coord.json")
    assert result["applied"]
    drive.files.assert_not_called()
    for tab in ("submissions", "parser_results", "parser_jobs", "errors"):
        assert sheet.rows[tab] == before[tab]
    assert all("target" not in row for row in sheet.rows["ops"])


@pytest.mark.parametrize("ended,cutoff", [(False, NOW), (True, None), (True, NOW - timedelta(seconds=1))])
def test_ineligible_coordination_cannot_be_deleted(tmp_path, ended, cutoff):
    sheet, drive = fixture(ended), Mock()
    before = deepcopy(sheet.rows)
    with pytest.raises(DeletionIncomplete, match="LIFECYCLE_REVIEW_REQUIRED"):
        delete_submissions(sheet, drive, "sheet", ["target"], reason="coordination_expiry",
                           approved_coordination_cutoff=cutoff, apply=True, manifest_path=tmp_path / "x.json")
    assert sheet.rows == before
    drive.files.assert_not_called()


@pytest.mark.parametrize("stored", ["", "bad JSON"])
def test_unassessed_or_malformed_context_blocks_source_expiry_but_not_explicit_deletion(tmp_path, stored):
    sheet, drive = fixture(), Mock()
    sheet.rows["ops"][1][-1] = stored
    with pytest.raises(DeletionIncomplete, match="LIFECYCLE_REVIEW_REQUIRED"):
        delete_submissions(sheet, drive, "sheet", ["target"], reason="source_expiry", apply=True,
                           manifest_path=tmp_path / "source.json")
    drive.files.assert_not_called()
    assert delete_submissions(sheet, drive, "sheet", ["target"], apply=True,
                              manifest_path=tmp_path / "delete.json")["applied"]
    assert all(row["submission_id"] != "target" for row in snapshot(sheet))


def test_explicit_deletion_finds_retained_ops_without_source(tmp_path):
    sheet = fixture()
    delete_submissions(sheet, Mock(), "sheet", ["target"], reason="source_expiry", apply=True,
                       manifest_path=tmp_path / "source.json")
    drive = Mock()
    delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "full.json")
    drive.files.assert_not_called()
    assert all(row["submission_id"] != "target" for row in snapshot(sheet))


@pytest.mark.parametrize("reason", ["source_expiry", "coordination_expiry"])
def test_scoped_retry_after_lost_sheet_response_keeps_original_policy(tmp_path, reason):
    sheet, drive = fixture(ended=True), Mock()
    cutoff = NOW if reason == "coordination_expiry" else None
    path = tmp_path / "receipt.json"
    original = sheet.batchUpdate
    def lost_response(**kwargs):
        def execute():
            original(**kwargs).execute()
            raise TimeoutError("lost response")
        return Mock(execute=execute)
    sheet.batchUpdate = lost_response
    with pytest.raises(DeletionIncomplete, match="SHEETS_DELETE_FAILED"):
        delete_submissions(sheet, drive, "sheet", ["target"], reason=reason,
                           approved_coordination_cutoff=cutoff, apply=True, manifest_path=path)
    assert load_manifest(path)["reason"] == reason
    drive.reset_mock()
    assert delete_submissions(sheet, drive, "sheet", ["target"], reason=reason,
                              approved_coordination_cutoff=cutoff, apply=True, manifest_path=path)["applied"]
    drive.files.assert_not_called()
    with pytest.raises(ManifestError, match="MANIFEST_MISMATCH"):
        delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)


def test_orphan_cleanup_preserves_even_unassessed_or_malformed_ops_roots():
    sheet = Sheet()
    sheet.add("ops", submission_id="legacy")
    sheet.add("ops", submission_id="broken", coordination="bad")
    sheet.add("parser_results", submission_id="legacy")
    sheet.add("errors", submission_id="broken")
    sheet.add("parser_results", submission_id="true-orphan")
    assert orphan_submission_ids(read_inventory(sheet, "sheet")) == {"true-orphan"}


def test_duplicate_ops_block_expiry_but_full_deletion_removes_every_row(tmp_path):
    sheet, drive = fixture(), Mock()
    sheet.rows["ops"].append(sheet.rows["ops"][1].copy())
    with pytest.raises(DeletionIncomplete, match="LIFECYCLE_REVIEW_REQUIRED"):
        delete_submissions(sheet, drive, "sheet", ["target"], reason="source_expiry",
                           apply=True, manifest_path=tmp_path / "source.json")
    drive.files.assert_not_called()
    delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=tmp_path / "full.json")
    assert all("target" not in row for row in sheet.rows["ops"])


def test_source_expiry_without_ops_requires_no_invented_coordination(tmp_path):
    sheet, drive = Sheet(), Mock()
    sheet.add("submissions", submission_id="target", resume_status="missing")
    assert delete_submissions(sheet, drive, "sheet", ["target"], reason="source_expiry",
                              apply=True, manifest_path=tmp_path / "source.json")["applied"]
    drive.files.assert_not_called()
    assert len(sheet.rows["ops"]) == 1
    assert snapshot(sheet) == []


def test_multi_id_coordination_expiry_is_all_or_nothing_when_one_is_active(tmp_path):
    sheet, drive = fixture(ended=True), Mock()
    # The existing 'other' ops row is unassessed and must not be swept along.
    before = deepcopy(sheet.rows)
    with pytest.raises(DeletionIncomplete, match="LIFECYCLE_REVIEW_REQUIRED"):
        delete_submissions(sheet, drive, "sheet", ["target", "other"], reason="coordination_expiry",
                           approved_coordination_cutoff=NOW, apply=True, manifest_path=tmp_path / "coord.json")
    assert sheet.rows == before
    drive.files.assert_not_called()


def test_receipt_cutoff_cannot_be_changed_after_coordination_removal(tmp_path):
    sheet, drive = fixture(ended=True), Mock()
    path = tmp_path / "coord.json"
    delete_submissions(sheet, drive, "sheet", ["target"], reason="coordination_expiry",
                       approved_coordination_cutoff=NOW, apply=True, manifest_path=path)
    with pytest.raises(ManifestError, match="MANIFEST_MISMATCH"):
        delete_submissions(sheet, drive, "sheet", ["target"], reason="coordination_expiry",
                           approved_coordination_cutoff=NOW + timedelta(days=1), apply=True, manifest_path=path)


def test_legacy_receipt_can_resume_full_deletion_but_never_source_expiry(tmp_path):
    import json
    sheet, drive = fixture(), Mock()
    path = tmp_path / "old.json"
    delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)
    data = load_manifest(path)
    data["version"] = 1
    data.pop("reason")
    data.pop("coordination_cutoff")
    path.write_text(json.dumps(data))
    assert delete_submissions(sheet, drive, "sheet", ["target"], apply=True, manifest_path=path)["applied"]
    with pytest.raises(ManifestError, match="MANIFEST_MISMATCH"):
        delete_submissions(sheet, drive, "sheet", ["target"], reason="source_expiry", apply=True, manifest_path=path)
