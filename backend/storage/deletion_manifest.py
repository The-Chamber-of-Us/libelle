"""Restricted, local recovery receipt for offline deletion, not application state."""
import json
import os
from pathlib import Path
import stat
import tempfile
from datetime import datetime, timezone


class ManifestError(RuntimeError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def load_manifest(path):
    """Do not follow symlinks or accept group/world-readable recovery data."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
                raise ValueError()
            data = json.load(stream)
        if (data["version"] != 1 or not isinstance(data["submission_ids"], list)
                or not data["submission_ids"]
                or not all(isinstance(s, str) and s.strip() for s in data["submission_ids"])
                or not isinstance(data["drive_file_ids"], list)
                or not all(isinstance(s, str) and s.strip() for s in data["drive_file_ids"])
                or not isinstance(data["deleted_drive_ids"], list)
                or not set(data["deleted_drive_ids"]) <= set(data["drive_file_ids"])
                or not isinstance(data["spreadsheet_id"], str)
                or data["state"] not in {"prepared", "deleting", "stores_deleted"}):
            raise ValueError()
        return data
    except Exception:
        raise ManifestError("MANIFEST_READ_FAILED: use an intact mode-0600 recovery manifest") from None


class DeletionManifest:
    def __init__(self, path, *, spreadsheet_id, submission_ids, drive_file_ids, counts):
        self.path = Path(path)
        try:
            if self.path.exists() or self.path.is_symlink():
                self.data = load_manifest(self.path)
                if (self.data["spreadsheet_id"] != spreadsheet_id
                        or set(self.data["submission_ids"]) != set(submission_ids)
                        or not set(drive_file_ids) <= set(self.data["drive_file_ids"])):
                    raise ManifestError("MANIFEST_MISMATCH: selection, store or file references changed")
            else:
                self.data = {
                    "version": 1, "created_at": timestamp(), "updated_at": timestamp(),
                    "spreadsheet_id": spreadsheet_id,
                    "submission_ids": sorted(submission_ids),
                    "drive_file_ids": sorted(drive_file_ids), "deleted_drive_ids": [],
                    "rows": counts, "state": "prepared",
                }
                # Exclusive creation prevents accidental overwrite of another receipt.
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as stream:
                    json.dump(self.data, stream, sort_keys=True)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._sync_directory()
        except ManifestError:
            raise
        except Exception:
            raise ManifestError("MANIFEST_WRITE_FAILED: prepare a writable private receipt directory") from None

    def _sync_directory(self):
        fd = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def save(self):
        self.data["updated_at"] = timestamp()
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".deletion-")
            with os.fdopen(fd, "w") as stream:
                json.dump(self.data, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self._sync_directory()
        except Exception:
            raise ManifestError("MANIFEST_WRITE_FAILED: keep services stopped; inspect the receipt before retry") from None
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
