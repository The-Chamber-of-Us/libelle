"""Offline retention operations. All application writers MUST be stopped."""
from datetime import datetime, timedelta, timezone

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


def expired_submission_ids(inventory, now=None):
    """365-day maximum; malformed timestamps block the sweep, never imply fresh."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=365)
    result = set()
    for _, row in inventory["submissions"][1]:
        sid = str(row["submission_id"]).strip()
        if not sid:
            continue
        value = str(row["created_at"]).strip()
        try:
            try:
                created = datetime.strptime(value, "%m-%d-%Y %H:%M:%S UTC").replace(tzinfo=timezone.utc)
            except ValueError:
                created = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if created.tzinfo is None:
                raise ValueError()
        except ValueError:
            raise DeletionIncomplete("Invalid submission timestamp; repair before sweep") from None
        if created <= cutoff:
            result.add(sid)
    # Orphan derived rows have no valid source purpose and expire immediately.
    sources = {str(row["submission_id"]).strip() for _, row in inventory["submissions"][1]}
    result.update(str(row["submission_id"]).strip()
                  for _, rows in inventory.values() for _, row in rows
                  if str(row.get("submission_id", "")).strip() not in sources)
    result.discard("")
    return result


def _matches(row, ids):
    return str(row.get("submission_id", "")).strip() in ids


def delete_submissions(sheet, drive, spreadsheet_id, ids, *, apply=False,
                       confirmed_absent=(), manifest_path=None):
    """Drive first, then a single atomic Sheets batch; re-read to verify.

    confirmed_absent is an operator attestation for permanently absent
    Drive IDs verified by the owner. A 404 alone is not proof of deletion (it can mean lost access).
    """
    ids = {str(s).strip() for s in ids if str(s).strip()}
    if not ids:
        raise DeletionIncomplete("No submissions selected")
    inventory = read_inventory(sheet, spreadsheet_id)
    files = set()
    for tab in ("submissions", "parser_jobs"):
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
        matched = [(index, row) for index, row in rows if _matches(row, ids)]
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
        submission_ids=ids, drive_file_ids=files, counts=counts)
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
        if any(_matches(row, ids) for _, rows in remaining.values() for _, row in rows):
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
