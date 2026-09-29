"""Offline retention operations. All application writers MUST be stopped."""

from pathlib import Path

from core.coordination_lifecycle import retention_scope
from storage.deletion_manifest import load_manifest, ManifestError
from sheet_schema import SHEET_SCHEMA, OPTIONAL_TABS
from storage.deletion_manifest import DeletionManifest


class DeletionIncomplete(RuntimeError):
    """Keep maintenance mode enabled and retry; never expose raw API errors."""


def read_inventory(sheet, spreadsheet_id):
    meta = sheet.get(spreadsheetId=spreadsheet_id,
                     fields="sheets.properties").execute()
    tabs = {s["properties"]["title"]: s["properties"]["sheetId"]
            for s in meta["sheets"]}
    if set(tabs) - set(SHEET_SCHEMA):
        raise DeletionIncomplete("Uninventoried tabs require operator review")
    inventory = {}
    for tab, headers in SHEET_SCHEMA.items():
        if tab not in tabs:
            if tab in OPTIONAL_TABS:
                continue
            raise DeletionIncomplete("Required tab missing")
        rows = sheet.values().get(spreadsheetId=spreadsheet_id,
                                  range=f"'{tab}'").execute().get("values", [])
        if not rows or rows[0] != headers:
            raise DeletionIncomplete("Schema mismatch")
        if any(len(row) > len(headers) for row in rows[1:]):
            raise DeletionIncomplete("Uninventoried columns require operator review")
        inventory[tab] = (tabs[tab], [
            (i, dict(zip(headers, row + [""] * (len(headers) - len(row)))))
            for i, row in enumerate(rows[1:], start=1)])
    for tab, (_, rows) in inventory.items():
        for _, row in rows:
            if not str(row.get("submission_id", "")).strip() and any(row.values()):
                minimized_event = (tab == "ops_events"
                    and row.get("action") in {"create", "update", "anonymized"}
                    and all(not value for key, value in row.items() if key != "action"))
                if not minimized_event:
                    raise DeletionIncomplete("UNKEYED_RECORD: reconcile nonempty rows without submission IDs")
    return inventory


def orphan_submission_ids(inventory):
    """Select IDs without either intake or coordination roots, never by age/activity."""
    sources = {str(row["submission_id"]).strip()
               for tab in ("submissions", "ops") for _, row in inventory[tab][1]}
    return {str(row["submission_id"]).strip()
            for _, rows in inventory.values() for _, row in rows
            if str(row.get("submission_id", "")).strip()
            and str(row["submission_id"]).strip() not in sources}


def _matches(row, ids):
    return str(row.get("submission_id", "")).strip() in ids


def delete_submissions(sheet, drive, spreadsheet_id, ids, *, apply=False,
                       confirmed_absent=(), manifest_path=None,
                       reason="volunteer_deletion", approved_coordination_cutoff=None):
    """Drive first, then a single atomic Sheets batch; re-read to verify.

    confirmed_absent is an operator attestation for permanently absent
    Drive IDs verified by the owner. A 404 alone is not proof of deletion (it can mean lost access).
    """
    ids = {str(s).strip() for s in ids if str(s).strip()}
    if not ids:
        raise DeletionIncomplete("No submissions selected")
    cutoff = (approved_coordination_cutoff.isoformat()
              if approved_coordination_cutoff is not None else None)
    if reason != "coordination_expiry" and cutoff is not None:
        raise DeletionIncomplete("Cutoff is only valid for coordination expiry")
    previous = None
    if manifest_path and (Path(manifest_path).exists() or Path(manifest_path).is_symlink()):
        previous = load_manifest(manifest_path)
        if (previous["spreadsheet_id"] != spreadsheet_id
                or set(previous["submission_ids"]) != ids
                or previous["reason"] != reason
                or previous["coordination_cutoff"] != cutoff):
            raise ManifestError("MANIFEST_MISMATCH: selection, store or retention policy changed")
    inventory = read_inventory(sheet, spreadsheet_id)
    domains = None
    for sid in ids:
        ops = [row for _, row in inventory["ops"][1] if _matches(row, {sid})]
        try:
            if reason != "volunteer_deletion" and len(ops) > 1:
                raise ValueError("Duplicate coordination roots")
            stored = ops[0].get("coordination", "") if ops else ""
            selected = retention_scope(reason, stored,
                approved_coordination_cutoff=approved_coordination_cutoff,
                coordination_present=bool(ops))
            if reason == "coordination_expiry" and not selected:
                # A lost Sheets response can leave no ops after the batch applied.
                # Only the same durable receipt authorizes finishing that retry.
                if not ops and previous is not None:
                    selected = ("coordination_context", "reviewer_history")
                else:
                    raise ValueError("Coordination is not eligible")
        except ValueError:
            raise DeletionIncomplete("LIFECYCLE_REVIEW_REQUIRED: verify purpose and approved cutoff") from None
        domains = selected
    target_tabs = set()
    if "intake_evidence" in domains:
        target_tabs.update(("submissions", "parser_jobs", "parser_results", "errors"))
    if "coordination_context" in domains:
        target_tabs.add("ops")
    if "reviewer_history" in domains:
        target_tabs.add("ops_events")
    files = set()
    for tab in ({"submissions", "parser_jobs"} & target_tabs):
        for _, row in inventory[tab][1]:
            if _matches(row, ids):
                file_id = str(row.get("drive_file_id", "")).strip()
                if file_id:
                    files.add(file_id)
                elif tab == "submissions" and row.get("resume_status") == "uploaded":
                    raise DeletionIncomplete("Uploaded resume lacks a reference; reconcile Drive first")
    for tab in ("submissions", "parser_jobs"):
        for _, row in inventory[tab][1]:
            if not _matches(row, ids) and str(row.get("drive_file_id", "")).strip() in files:
                raise DeletionIncomplete("Drive reference shared with an unselected submission")
    requests = []
    counts = {}
    for tab, (sheet_id, rows) in inventory.items():
        matched = [(index, row) for index, row in rows
                   if tab in target_tabs and _matches(row, ids)]
        counts[tab] = len(matched)
        for index, row in reversed(matched):
            if tab == "ops_events":
                # Keep action counts only: no IDs, actors, free text, exact times,
                # field names, or values that could identify the volunteer.
                safe = [""] * len(SHEET_SCHEMA[tab])
                safe[SHEET_SCHEMA[tab].index("action")] = (
                    row["action"] if row["action"] in {"create", "update"} else "anonymized"
                )
                requests.append({"updateCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": index,
                              "endRowIndex": index + 1, "startColumnIndex": 0,
                              "endColumnIndex": len(safe)},
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": v}}
                                          for v in safe]}],
                    "fields": "*"}})
            else:
                requests.append({"deleteDimension": {"range": {
                    "sheetId": sheet_id, "dimension": "ROWS",
                    "startIndex": index, "endIndex": index + 1}}})
    summary = {"rows": counts, "drive_files": len(files), "applied": False}
    if not apply:
        return summary
    if not manifest_path:
        raise DeletionIncomplete("MANIFEST_REQUIRED: supply a private recovery manifest path")
    manifest = DeletionManifest(manifest_path, spreadsheet_id=spreadsheet_id,
        submission_ids=ids, drive_file_ids=files, counts=counts,
        reason=reason, coordination_cutoff=cutoff)
    if set(confirmed_absent) - set(manifest.data["drive_file_ids"]):
        raise DeletionIncomplete("Absent-file attestation is outside selected references")
    # Persist selection and progress before external deletion; resume uses these
    # references even if a Sheets response was lost after the batch applied.
    manifest.data["state"] = "deleting"
    manifest.save()
    completed = set(manifest.data["deleted_drive_ids"])
    for file_id in sorted(set(manifest.data["drive_file_ids"]) - completed):
        if file_id not in confirmed_absent:
            try:
                drive.files().delete(fileId=file_id).execute()
            except Exception:
                raise DeletionIncomplete(
                    "DRIVE_DELETE_FAILED: deletion incomplete; keep services stopped. "
                    "Resume with the manifest; verify ambiguous missing files with the owner."
                ) from None
        completed.add(file_id)
        manifest.data["deleted_drive_ids"] = sorted(completed)
        manifest.save()
    try:
        if requests:
            sheet.batchUpdate(spreadsheetId=spreadsheet_id,
                              body={"requests": requests}).execute()
        remaining = read_inventory(sheet, spreadsheet_id)
        if any(_matches(row, ids) for tab, (_, rows) in remaining.items()
               if tab in target_tabs for _, row in rows):
            raise DeletionIncomplete("Verification found remaining records")
    except DeletionIncomplete:
        raise
    except Exception:
        raise DeletionIncomplete(
            "SHEETS_DELETE_FAILED: deletion incomplete; keep services stopped and resume with the manifest"
        ) from None
    manifest.data["state"] = "stores_deleted"
    manifest.save()
    summary["applied"] = True
    summary["external_cleanup_required"] = True
    return summary
