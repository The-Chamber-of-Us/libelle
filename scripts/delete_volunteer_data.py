#!/usr/bin/env python3
"""Offline administrator retention/deletion command; preview by default."""
import argparse
from datetime import datetime
import contextlib
import json
import os
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from storage.deletion_manifest import ManifestError, load_manifest
from storage.retention_repo import DeletionIncomplete, delete_submissions, read_inventory, orphan_submission_ids


def aware_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed
    except ValueError:
        raise argparse.ArgumentTypeError("Use an ISO timestamp with a timezone") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--submission-id", action="append")
    selection.add_argument("--orphans", action="store_true", help="Select artifacts with neither an intake nor an ops root; no age-based expiry")
    selection.add_argument("--resume", type=Path, help="Resume the exact selection in a recovery manifest")
    parser.add_argument("--manifest", type=Path, help="Required private recovery receipt for a new apply")
    parser.add_argument("--reason", choices=["volunteer_deletion", "source_expiry", "coordination_expiry"],
                        help="Default: explicit volunteer deletion; resume inherits the receipt reason")
    parser.add_argument("--approved-coordination-cutoff", type=aware_timestamp,
                        help="Approved purpose-ended cutoff, only for coordination expiry; no default duration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--writers-and-readers-stopped", action="store_true")
    parser.add_argument("--confirmed-absent-drive-id", action="append", default=[])
    args = parser.parse_args(argv)
    if args.orphans and args.reason not in {None, "volunteer_deletion"}:
        parser.error("--orphans cannot select lifecycle expiry")
    if not args.resume:
        if args.reason == "coordination_expiry" and args.approved_coordination_cutoff is None:
            parser.error("coordination_expiry requires --approved-coordination-cutoff")
        if args.reason != "coordination_expiry" and args.approved_coordination_cutoff is not None:
            parser.error("The cutoff is only valid for coordination_expiry")
    if args.apply and not args.writers_and_readers_stopped:
        parser.error("--apply requires --writers-and-readers-stopped; see retention runbook")
    if args.apply and not (args.manifest or args.resume):
        parser.error("--apply requires --manifest or --resume")
    if args.resume and args.manifest:
        parser.error("--resume already supplies the manifest path")
    # Preserve operator-relative receipt paths before using backend credential defaults.
    path = args.resume or args.manifest
    manifest_path = path.absolute() if path else None
    phase = "CONFIGURATION_FAILED: check backend environment and credential configuration"
    previous_directory = Path.cwd()
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            os.chdir(BACKEND_DIR)
            from config import GOOGLE_SHEET_ID
            from storage.sheets_repo import _get_sheet
            from storage.drive_repo import get_drive_service
            phase = "SHEETS_ACCESS_FAILED: check service-account credentials, spreadsheet access and connectivity"
            sheet = _get_sheet()
            reason = args.reason or "volunteer_deletion"
            cutoff = args.approved_coordination_cutoff
            if args.resume:
                manifest = load_manifest(manifest_path)
                if manifest["spreadsheet_id"] != GOOGLE_SHEET_ID:
                    raise DeletionIncomplete("MANIFEST_MISMATCH: configured spreadsheet differs from receipt")
                ids = manifest["submission_ids"]
                reason = args.reason or manifest["reason"]
                if cutoff is None and manifest["coordination_cutoff"] is not None:
                    cutoff = datetime.fromisoformat(manifest["coordination_cutoff"])
            else:
                ids = args.submission_id or orphan_submission_ids(read_inventory(sheet, GOOGLE_SHEET_ID))
            if not ids:
                summary = {"orphan_submissions": 0, "applied": False}
            else:
                # Preview never requires or refreshes Drive credentials.
                drive = None
                if args.apply and reason != "coordination_expiry":
                    phase = "DRIVE_AUTH_FAILED: check backend OAuth token and bootstrap configuration"
                    drive = get_drive_service()
                phase = "SHEETS_ACCESS_FAILED: check spreadsheet access and connectivity; keep maintenance enabled"
                summary = delete_submissions(sheet, drive, GOOGLE_SHEET_ID, ids,
                    apply=args.apply, confirmed_absent=args.confirmed_absent_drive_id,
                    manifest_path=manifest_path, reason=reason,
                    approved_coordination_cutoff=cutoff)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (DeletionIncomplete, ManifestError) as exc:
        # These classes contain only repository-owned messages, never API details.
        print(str(exc))
        return 1
    except Exception:
        print(phase)
        return 1
    finally:
        os.chdir(previous_directory)


if __name__ == "__main__":
    raise SystemExit(main())
