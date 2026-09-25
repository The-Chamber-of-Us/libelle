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
    sheet.add("submissions", submission_id="private", created_at="bad")
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: sheet)
    drive = Mock(side_effect=RuntimeError("private credential details"))
    monkeypatch.setattr(drive_repo, "get_drive_service", drive)
    assert cli.main(["--expired"]) == 1
    output = capsys.readouterr().out
    assert "timestamp" in output and "private" not in output
    assert cli.main(["--submission-id", "private"]) == 0
    drive.assert_not_called()


def test_cli_expiry_receipt_preserves_selected_ids(monkeypatch, tmp_path, capsys):
    sheet = Sheet()
    sheet.add("submissions", submission_id="expired", created_at="2020-01-01T00:00:00Z")
    sheet.add("parser_results", submission_id="orphan")
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: sheet)
    monkeypatch.setattr(drive_repo, "get_drive_service", Mock())
    path = tmp_path / "receipt.json"
    assert cli.main(["--expired", "--apply", "--writers-and-readers-stopped",
                     "--manifest", str(path)]) == 0
    assert load_manifest(path)["submission_ids"] == ["expired", "orphan"]
    summary = json.loads(capsys.readouterr().out)
    assert summary["external_cleanup_required"]


@pytest.mark.parametrize("arguments", [
    ["--expired", "--apply"],
    ["--expired", "--apply", "--writers-and-readers-stopped"],
])
def test_cli_requires_maintenance_and_manifest(arguments):
    with pytest.raises(SystemExit) as exc:
        cli.main(arguments)
    assert exc.value.code == 2
