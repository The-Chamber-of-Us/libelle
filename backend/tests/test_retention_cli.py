"""Exercise the operator entry point without Google credentials or network."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.test_retention_repo import Sheet, populated
from storage import sheets_repo, drive_repo
from storage.deletion_manifest import load_manifest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "delete_volunteer_data.py"
spec = importlib.util.spec_from_file_location("retention_cli", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_cli_resolves_credentials_from_backend_and_receipt_from_caller(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    sheet, drive = populated(), Mock()
    def get_sheet():
        assert Path.cwd() == cli.BACKEND_DIR
        return sheet
    monkeypatch.setattr(sheets_repo, "_get_sheet", get_sheet)
    monkeypatch.setattr(drive_repo, "get_drive_service", lambda: drive)
    assert cli.main(["--submission-id", "target", "--apply", "--writers-and-readers-stopped",
                     "--manifest", "receipt.json"]) == 0
    assert Path.cwd() == tmp_path
    assert load_manifest(tmp_path / "receipt.json")["submission_ids"] == ["target"]
    assert "target" not in capsys.readouterr().out
    assert cli.main(["--resume", "receipt.json", "--apply", "--writers-and-readers-stopped"]) == 0


def test_cli_safe_diagnostics_and_preview_does_not_use_drive(monkeypatch, capsys):
    sheet = Sheet()
    sheet.add("submissions", email="private@example.org")
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: sheet)
    drive = Mock(side_effect=RuntimeError("private credential details"))
    monkeypatch.setattr(drive_repo, "get_drive_service", drive)
    assert cli.main(["--orphans"]) == 1
    output = capsys.readouterr().out
    assert "UNKEYED_RECORD" in output and "private" not in output
    sheet.rows["submissions"].pop()
    sheet.add("submissions", submission_id="private", created_at="bad")
    assert cli.main(["--submission-id", "private"]) == 0
    drive.assert_not_called()


def test_cli_orphan_receipt_preserves_selected_ids(monkeypatch, tmp_path, capsys):
    sheet = Sheet()
    sheet.add("submissions", submission_id="old", created_at="2020-01-01T00:00:00Z")
    sheet.add("ops", submission_id="old", status="in_progress", notes="Ongoing relationship")
    sheet.add("parser_results", submission_id="orphan")
    preserved = {tab: [row.copy() for row in sheet.rows[tab]] for tab in ("submissions", "ops")}
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: sheet)
    monkeypatch.setattr(drive_repo, "get_drive_service", Mock())
    path = tmp_path / "receipt.json"
    assert cli.main(["--orphans", "--apply", "--writers-and-readers-stopped",
                     "--manifest", str(path)]) == 0
    assert load_manifest(path)["submission_ids"] == ["orphan"]
    summary = json.loads(capsys.readouterr().out)
    assert summary["external_cleanup_required"]
    for tab, rows in preserved.items():
        assert sheet.rows[tab] == rows


@pytest.mark.parametrize("arguments", [
    ["--orphans", "--apply"],
    ["--orphans", "--apply", "--writers-and-readers-stopped"],
])
def test_cli_requires_maintenance_and_manifest(arguments):
    with pytest.raises(SystemExit) as exc:
        cli.main(arguments)
    assert exc.value.code == 2


def test_removed_age_expiry_flag_is_rejected_before_access(monkeypatch):
    get_sheet = Mock()
    monkeypatch.setattr(sheets_repo, "_get_sheet", get_sheet)
    with pytest.raises(SystemExit) as exc:
        cli.main(["--expired", "--apply", "--writers-and-readers-stopped", "--manifest", "unused.json"])
    assert exc.value.code == 2
    get_sheet.assert_not_called()
