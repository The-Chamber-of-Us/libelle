from datetime import datetime, timezone

import pytest

from sheet_schema import PARSER_JOBS_HEADERS, SHEET_SCHEMA
from storage import parser_jobs_repo


def _job(**overrides):
    row = {
        "job_id": "job_001",
        "submission_id": "sub_001",
        "drive_file_id": "drive_001",
        "resume_filename": "resume.pdf",
        "job_type": "parse_resume",
        "status": "queued",
        "attempt_count": "0",
        "max_attempts": "3",
        "available_at": "05-26-2026 10:00:00 UTC",
        "locked_by": "",
        "locked_at": "",
        "lock_expires_at": "",
        "last_parser_run_id": "",
        "authoritative_parser_run_id": "",
        "parser_started_at": "",
        "last_error_code": "",
        "last_error_summary": "",
        "created_at": "05-26-2026 10:00:00 UTC",
        "updated_at": "05-26-2026 10:00:00 UTC",
    }
    row.update(overrides)
    return row


class _FakeRequest:
    def __init__(self, result=None):
        self.result = result or {}

    def execute(self):
        return self.result


class _FakeValues:
    def __init__(self, rows):
        self.rows = rows
        self.append_calls = []
        self.update_calls = []

    def get(self, **kwargs):
        return _FakeRequest({"values": self.rows})

    def append(self, **kwargs):
        self.append_calls.append(kwargs)
        self.rows.extend(kwargs["body"]["values"])
        return _FakeRequest()

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        target = kwargs["range"].split("!")[1].split(":")[0]
        row_number = int(target[1:])
        self.rows[row_number - 2] = kwargs["body"]["values"][0]
        return _FakeRequest()


class _FakeSheet:
    def __init__(self, rows=None):
        self.values_api = _FakeValues(rows or [])

    def values(self):
        return self.values_api


def _sheet_row(job):
    return [job.get(header, "") for header in PARSER_JOBS_HEADERS]


def test_parser_jobs_schema_is_required_v04_contract() -> None:
    assert SHEET_SCHEMA["parser_jobs"] == [
        "job_id",
        "submission_id",
        "drive_file_id",
        "resume_filename",
        "job_type",
        "status",
        "attempt_count",
        "max_attempts",
        "available_at",
        "locked_by",
        "locked_at",
        "lock_expires_at",
        "last_parser_run_id",
        "authoritative_parser_run_id",
        "parser_started_at",
        "last_error_code",
        "last_error_summary",
        "created_at",
        "updated_at",
    ]


def test_create_parser_job_appends_schema_aligned_default_row(monkeypatch) -> None:
    fake_sheet = _FakeSheet()
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(
        parser_jobs_repo,
        "_local_timestamp",
        lambda: "05-26-2026 10:00:00 UTC",
    )

    created = parser_jobs_repo.create_parser_job(
        submission_id=" sub_001 ",
        drive_file_id=" drive_001 ",
        resume_filename=" resume.pdf ",
        job_id="job_001",
    )

    assert created["job_id"] == "job_001"
    assert created["submission_id"] == "sub_001"
    assert created["job_type"] == "parse_resume"
    assert created["status"] == "queued"
    assert created["attempt_count"] == "0"
    assert created["max_attempts"] == "3"
    assert created["parser_started_at"] == ""
    assert fake_sheet.values_api.append_calls[0]["range"] == "parser_jobs!A2"
    assert fake_sheet.values_api.append_calls[0]["body"]["values"] == [
        _sheet_row(created)
    ]


def test_create_parser_job_returns_existing_logical_job(monkeypatch) -> None:
    existing = _job()
    fake_sheet = _FakeSheet([_sheet_row(existing)])
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    returned = parser_jobs_repo.create_parser_job(
        submission_id="sub_001",
        drive_file_id="drive_new",
        resume_filename="new.pdf",
    )

    assert returned == existing
    assert fake_sheet.values_api.append_calls == []


def test_get_job_and_get_parser_job_by_submission_return_none_when_missing(
    monkeypatch,
) -> None:
    fake_sheet = _FakeSheet([])
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    assert parser_jobs_repo.get_job("missing_job") is None
    assert parser_jobs_repo.get_parser_job_by_submission("missing_sub") is None


def test_duplicate_logical_jobs_resolve_to_earliest_with_diagnostics(monkeypatch) -> None:
    later = _job(job_id="job_later", created_at="05-26-2026 11:00:00 UTC")
    earlier = _job(job_id="job_earlier", created_at="05-26-2026 09:00:00 UTC")
    fake_sheet = _FakeSheet([_sheet_row(later), _sheet_row(earlier)])
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    returned = parser_jobs_repo.get_parser_job_by_submission("sub_001")

    assert returned["job_id"] == "job_earlier"
    assert returned["_duplicate_count"] == "1"
    assert returned["_duplicate_job_ids"] == "job_later"


def test_list_claimable_jobs_filters_by_status_and_available_at(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        [
            _sheet_row(_job(job_id="queued_due", submission_id="sub_001")),
            _sheet_row(
                _job(
                    job_id="future",
                    submission_id="sub_002",
                    available_at="05-26-2026 12:00:00 UTC",
                )
            ),
            _sheet_row(
                _job(job_id="running", submission_id="sub_003", status="running")
            ),
            _sheet_row(
                _job(
                    job_id="retry_due",
                    submission_id="sub_004",
                    status="retry_scheduled",
                )
            ),
        ]
    )
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    jobs = parser_jobs_repo.list_claimable_jobs(
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    )

    assert [job["job_id"] for job in jobs] == ["queued_due", "retry_due"]


def test_expired_running_job_under_max_attempts_is_claimable(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        [
            _sheet_row(
                _job(
                    job_id="stale_running",
                    status="running",
                    attempt_count="2",
                    max_attempts="3",
                    locked_by="worker-old",
                    lock_expires_at="05-26-2026 10:15:00 UTC",
                )
            ),
        ]
    )
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    jobs = parser_jobs_repo.list_claimable_jobs(
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    )

    assert [job["job_id"] for job in jobs] == ["stale_running"]


def test_expired_running_job_at_max_attempts_is_not_claimable(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        [
            _sheet_row(
                _job(
                    job_id="final_attempt_crashed",
                    status="running",
                    attempt_count="3",
                    max_attempts="3",
                    locked_by="worker-old",
                    lock_expires_at="05-26-2026 10:15:00 UTC",
                )
            ),
        ]
    )
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    jobs = parser_jobs_repo.list_claimable_jobs(
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    )

    assert jobs == []


def test_list_claimable_jobs_excludes_malformed_available_at(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        [
            _sheet_row(
                _job(
                    job_id="malformed_available",
                    available_at="not a timestamp",
                )
            ),
            _sheet_row(
                _job(
                    job_id="blank_available",
                    submission_id="sub_002",
                    available_at="",
                )
            ),
        ]
    )
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    jobs = parser_jobs_repo.list_claimable_jobs(
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    )

    assert [job["job_id"] for job in jobs] == ["blank_available"]


@pytest.mark.parametrize(
    "terminal_status",
    ["succeeded", "failed", "enqueue_failed"],
)
def test_list_claimable_jobs_excludes_terminal_jobs(monkeypatch, terminal_status) -> None:
    fake_sheet = _FakeSheet(
        [_sheet_row(_job(job_id=f"job_{terminal_status}", status=terminal_status))]
    )
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    jobs = parser_jobs_repo.list_claimable_jobs(
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    )

    assert jobs == []


def test_list_claimable_jobs_collapses_duplicate_logical_jobs(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        [
            _sheet_row(_job(job_id="job_later", created_at="05-26-2026 11:00:00 UTC")),
            _sheet_row(_job(job_id="job_earlier", created_at="05-26-2026 09:00:00 UTC")),
        ]
    )
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    jobs = parser_jobs_repo.list_claimable_jobs(
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    )

    assert [job["job_id"] for job in jobs] == ["job_earlier"]
    assert jobs[0]["_duplicate_count"] == "1"


def test_claim_job_updates_lease_fields_and_confirms_after_reread(monkeypatch) -> None:
    fake_sheet = _FakeSheet([_sheet_row(_job())])
    now = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    result = parser_jobs_repo.claim_job(
        job_id="job_001",
        worker_id="worker-a",
        parser_run_id="run_001",
        lease_seconds=60,
        now=now,
    )

    assert result.claimed is True
    assert result.job["status"] == "running"
    assert result.job["attempt_count"] == "1"
    assert result.job["locked_by"] == "worker-a"
    assert result.job["locked_at"] == "05-26-2026 10:30:00 UTC"
    assert result.job["lock_expires_at"] == "05-26-2026 10:31:00 UTC"
    assert result.job["last_parser_run_id"] == "run_001"
    assert result.job["parser_started_at"] == ""
    assert fake_sheet.values_api.update_calls[0]["range"] == "parser_jobs!A2:S2"


@pytest.mark.parametrize("attempt_count", ["oops", "-1"])
def test_claim_job_fails_closed_for_malformed_attempt_count(
    monkeypatch,
    attempt_count,
) -> None:
    fake_sheet = _FakeSheet([_sheet_row(_job(attempt_count=attempt_count))])
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    result = parser_jobs_repo.claim_job(
        job_id="job_001",
        worker_id="worker-a",
        parser_run_id="run_001",
        lease_seconds=60,
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
    )

    assert result.claimed is False
    assert result.job["attempt_count"] == attempt_count
    assert fake_sheet.values_api.update_calls == []


def test_claim_job_fails_closed_for_malformed_available_at(monkeypatch) -> None:
    fake_sheet = _FakeSheet([_sheet_row(_job(available_at="not a timestamp"))])
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    result = parser_jobs_repo.claim_job(
        job_id="job_001",
        worker_id="worker-a",
        parser_run_id="run_001",
        lease_seconds=60,
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
    )

    assert result.claimed is False
    assert result.job["available_at"] == "not a timestamp"
    assert fake_sheet.values_api.update_calls == []


def test_claim_job_refuses_expired_running_job_at_max_attempts(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        [
            _sheet_row(
                _job(
                    status="running",
                    attempt_count="3",
                    max_attempts="3",
                    locked_by="worker-old",
                    lock_expires_at="05-26-2026 10:15:00 UTC",
                )
            )
        ]
    )
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)

    result = parser_jobs_repo.claim_job(
        job_id="job_001",
        worker_id="worker-a",
        parser_run_id="run_004",
        lease_seconds=60,
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
    )

    assert result.claimed is False
    assert result.job["attempt_count"] == "3"
    assert fake_sheet.values_api.update_calls == []


def test_claim_job_reports_false_if_reread_observes_different_claim(monkeypatch) -> None:
    original = _job()
    hijacked = _job(
        status="running",
        attempt_count="1",
        locked_by="worker-b",
        locked_at="05-26-2026 10:30:00 UTC",
        lock_expires_at="05-26-2026 10:31:00 UTC",
        last_parser_run_id="run_002",
    )
    calls = {"count": 0}

    def fake_rows():
        calls["count"] += 1
        if calls["count"] == 1:
            return [(2, dict(original))]
        return [(2, dict(hijacked))]

    monkeypatch.setattr(
        parser_jobs_repo,
        "_load_parser_job_rows_with_sheet_row_numbers",
        fake_rows,
    )
    monkeypatch.setattr(
        parser_jobs_repo,
        "_update_job_row",
        lambda row_number, row_data: None,
    )

    result = parser_jobs_repo.claim_job(
        job_id="job_001",
        worker_id="worker-a",
        parser_run_id="run_001",
        lease_seconds=60,
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
    )

    assert result.claimed is False
    assert result.job["locked_by"] == "worker-b"


def test_update_job_rejects_unknown_fields_and_invalid_status() -> None:
    with pytest.raises(ValueError, match="Unsupported parser job update field"):
        parser_jobs_repo.update_job("job_001", {"submission_id": "sub_002"})

    with pytest.raises(ValueError, match="Unsupported parser job status"):
        parser_jobs_repo.update_job("job_001", {"status": "done"})


def test_update_job_changes_mutable_state_and_preserves_identity(monkeypatch) -> None:
    original = _job()
    fake_sheet = _FakeSheet([_sheet_row(original)])
    monkeypatch.setattr(parser_jobs_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(
        parser_jobs_repo,
        "_local_timestamp",
        lambda: "05-26-2026 11:00:00 UTC",
    )

    updated = parser_jobs_repo.update_job(
        "job_001",
        {
            "status": "retry_scheduled",
            "attempt_count": 2,
            "available_at": "05-26-2026 12:00:00 UTC",
            "last_error_code": "PARSER_TIMEOUT",
            "last_error_summary": "Parser timed out",
        },
    )

    assert updated["job_id"] == original["job_id"]
    assert updated["submission_id"] == original["submission_id"]
    assert updated["drive_file_id"] == original["drive_file_id"]
    assert updated["job_type"] == original["job_type"]
    assert updated["created_at"] == original["created_at"]
    assert updated["status"] == "retry_scheduled"
    assert updated["attempt_count"] == "2"
    assert updated["available_at"] == "05-26-2026 12:00:00 UTC"
    assert updated["last_error_code"] == "PARSER_TIMEOUT"
    assert updated["last_error_summary"] == "Parser timed out"
    assert updated["updated_at"] == "05-26-2026 11:00:00 UTC"
