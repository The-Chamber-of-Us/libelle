import services.ops_write_service as ops_write_service
from services.ops_write_service import (
    create_first_ops_workflow_state,
    OpsSubmissionNotFoundError,
    update_existing_ops_workflow_state,
    update_or_create_ops_workflow_state,
)
from storage import sheets_repo


class _FakeAppendRequest:
    def execute(self):
        return {}


class _FakeGetRequest:
    def __init__(self, rows):
        self.rows = rows

    def execute(self):
        return {"values": self.rows}


class _FakeUpdateRequest:
    def execute(self):
        return {}


class _FakeValues:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.append_calls = []
        self.get_calls = []
        self.update_calls = []

    def append(self, **kwargs):
        self.append_calls.append(kwargs)
        return _FakeAppendRequest()

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return _FakeGetRequest(self.rows)

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        return _FakeUpdateRequest()


class _FakeSheet:
    def __init__(self, rows=None):
        self.values_api = _FakeValues(rows)

    def values(self):
        return self.values_api


def _ops_appends(fake_sheet):
    return [
        call
        for call in fake_sheet.values_api.append_calls
        if call["range"] == "ops!A2"
    ]


def _event_appends(fake_sheet):
    return [
        call
        for call in fake_sheet.values_api.append_calls
        if call["range"] == "ops_events!A2"
    ]


def _event_rows(fake_sheet):
    """Flatten appended ops_events rows as (submission_id, actor_email, action,
    field_changed, old_value, new_value, created_at, source) tuples, dropping
    the generated event_id."""
    rows = []
    for call in _event_appends(fake_sheet):
        for row in call["body"]["values"]:
            rows.append(tuple(row[1:]))
    return rows


def test_create_first_ops_workflow_state_appends_schema_aligned_ops_row(monkeypatch) -> None:
    fake_sheet = _FakeSheet()

    monkeypatch.setattr(sheets_repo, "load_ops_rows", lambda: [])
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")

    created = create_first_ops_workflow_state(
        " sub_001 ",
        {
            "status": "contacted",
            "notes": "Left voicemail",
            "tags": "priority",
            "contact_tracking": "call",
            "updated_by": "reviewer@example.org",
        },
    )

    assert created == {
        "submission_id": "sub_001",
        "status": "contacted",
        "notes": "Left voicemail",
        "tags": "priority",
        "contact_tracking": "call",
        "updated_at": "05-26-2026 10:00:00 UTC",
        "updated_by": "reviewer@example.org",
    }
    assert _ops_appends(fake_sheet) == [
        {
            "spreadsheetId": "test-sheet-id",
            "range": "ops!A2",
            "valueInputOption": "RAW",
            "insertDataOption": "INSERT_ROWS",
            "body": {
                "values": [
                    [
                        "sub_001",
                        "contacted",
                        "Left voicemail",
                        "priority",
                        "call",
                        "05-26-2026 10:00:00 UTC",
                        "reviewer@example.org",
                    ]
                ]
            },
        }
    ]
    assert _event_rows(fake_sheet) == [
        ("sub_001", "reviewer@example.org", "create", "status", "", "contacted", "05-26-2026 10:00:00 UTC", "dashboard"),
        ("sub_001", "reviewer@example.org", "create", "notes", "", "Left voicemail", "05-26-2026 10:00:00 UTC", "dashboard"),
        ("sub_001", "reviewer@example.org", "create", "tags", "", "priority", "05-26-2026 10:00:00 UTC", "dashboard"),
        ("sub_001", "reviewer@example.org", "create", "contact_tracking", "", "call", "05-26-2026 10:00:00 UTC", "dashboard"),
    ]


def test_create_first_ops_workflow_state_returns_none_when_ops_row_exists(monkeypatch) -> None:
    fake_sheet = _FakeSheet()

    monkeypatch.setattr(
        sheets_repo,
        "load_ops_rows",
        lambda: [{"submission_id": "sub_001", "status": "new"}],
    )
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)

    created = create_first_ops_workflow_state(
        "sub_001",
        {
            "status": "reviewed",
            "notes": "Do not update",
            "tags": "",
            "contact_tracking": "",
            "updated_by": "reviewer@example.org",
        },
    )

    assert created is None
    assert fake_sheet.values_api.append_calls == []


def test_create_first_ops_workflow_state_rechecks_existing_rows_before_each_append(
    monkeypatch,
) -> None:
    fake_sheet = _FakeSheet()
    stored_rows = []

    def fake_load_ops_rows():
        return list(stored_rows)

    def fake_append(**kwargs):
        if kwargs["range"] == "ops!A2":
            row = kwargs["body"]["values"][0]
            stored_rows.append({"submission_id": row[0], "status": row[1]})
        return _FakeAppendRequest()

    monkeypatch.setattr(sheets_repo, "load_ops_rows", fake_load_ops_rows)
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")
    monkeypatch.setattr(fake_sheet.values_api, "append", fake_append)

    fields = {
        "status": "reviewed",
        "notes": "",
        "tags": "",
        "contact_tracking": "",
        "updated_by": "reviewer@example.org",
    }

    assert create_first_ops_workflow_state("sub_001", fields) is not None
    assert create_first_ops_workflow_state("sub_001", fields) is None
    assert stored_rows == [{"submission_id": "sub_001", "status": "reviewed"}]


def test_update_existing_ops_workflow_state_updates_row_in_place(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        rows=[
            [
                "sub_001",
                "new",
                "Original note",
                "priority",
                "email",
                "05-25-2026 09:00:00 UTC",
                "old@example.org",
            ]
        ]
    )

    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")

    updated = update_existing_ops_workflow_state(
        " sub_001 ",
        {
            "status": "reviewed",
            "notes": "Looks good",
            "updated_by": "reviewer@example.org",
        },
    )

    assert updated == {
        "submission_id": "sub_001",
        "status": "reviewed",
        "notes": "Looks good",
        "tags": "priority",
        "contact_tracking": "email",
        "updated_at": "05-26-2026 10:00:00 UTC",
        "updated_by": "reviewer@example.org",
    }
    assert _ops_appends(fake_sheet) == []
    assert _event_rows(fake_sheet) == [
        ("sub_001", "reviewer@example.org", "update", "status", "new", "reviewed", "05-26-2026 10:00:00 UTC", "dashboard"),
        ("sub_001", "reviewer@example.org", "update", "notes", "Original note", "Looks good", "05-26-2026 10:00:00 UTC", "dashboard"),
    ]
    assert fake_sheet.values_api.update_calls == [
        {
            "spreadsheetId": "test-sheet-id",
            "range": "ops!A2:G2",
            "valueInputOption": "RAW",
            "body": {
                "values": [
                    [
                        "sub_001",
                        "reviewed",
                        "Looks good",
                        "priority",
                        "email",
                        "05-26-2026 10:00:00 UTC",
                        "reviewer@example.org",
                    ]
                ]
            },
        }
    ]


def test_update_existing_ops_workflow_state_preserves_non_updated_fields(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        rows=[
            [
                "sub_001",
                "contacted",
                "Original note",
                "priority",
                "call",
                "05-25-2026 09:00:00 UTC",
                "old@example.org",
            ]
        ]
    )

    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")

    updated = update_existing_ops_workflow_state(
        "sub_001",
        {
            "notes": "Updated note only",
            "updated_by": "reviewer@example.org",
        },
    )

    assert updated["status"] == "contacted"
    assert updated["notes"] == "Updated note only"
    assert updated["tags"] == "priority"
    assert updated["contact_tracking"] == "call"
    assert updated["updated_at"] == "05-26-2026 10:00:00 UTC"
    assert updated["updated_by"] == "reviewer@example.org"


def test_update_existing_ops_workflow_state_returns_none_when_row_missing(monkeypatch) -> None:
    fake_sheet = _FakeSheet(rows=[["sub_002", "new"]])

    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)

    updated = update_existing_ops_workflow_state(
        "sub_001",
        {
            "status": "reviewed",
            "updated_by": "reviewer@example.org",
        },
    )

    assert updated is None
    assert fake_sheet.values_api.append_calls == []
    assert fake_sheet.values_api.update_calls == []


def test_update_or_create_ops_workflow_state_creates_missing_status_row(monkeypatch) -> None:
    fake_sheet = _FakeSheet(rows=[])

    monkeypatch.setattr(sheets_repo, "load_ops_rows", lambda: [])
    monkeypatch.setattr(
        sheets_repo,
        "load_submission_records",
        lambda: {"sub_001": {"submission_id": "sub_001"}},
    )
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")

    upserted = update_or_create_ops_workflow_state(
        "sub_001",
        {
            "status": "reviewed",
            "updated_by": "reviewer@example.org",
        },
    )

    assert upserted == {
        "submission_id": "sub_001",
        "status": "reviewed",
        "notes": "",
        "tags": "",
        "contact_tracking": "",
        "updated_at": "05-26-2026 10:00:00 UTC",
        "updated_by": "reviewer@example.org",
    }
    assert fake_sheet.values_api.update_calls == []
    assert _event_rows(fake_sheet) == [
        ("sub_001", "reviewer@example.org", "create", "status", "", "reviewed", "05-26-2026 10:00:00 UTC", "dashboard"),
    ]
    assert _ops_appends(fake_sheet) == [
        {
            "spreadsheetId": "test-sheet-id",
            "range": "ops!A2",
            "valueInputOption": "RAW",
            "insertDataOption": "INSERT_ROWS",
            "body": {
                "values": [
                    [
                        "sub_001",
                        "reviewed",
                        "",
                        "",
                        "",
                        "05-26-2026 10:00:00 UTC",
                        "reviewer@example.org",
                    ]
                ]
            },
        }
    ]


def test_update_or_create_ops_workflow_state_creates_missing_notes_row_with_new_status(
    monkeypatch,
) -> None:
    fake_sheet = _FakeSheet(rows=[])

    monkeypatch.setattr(sheets_repo, "load_ops_rows", lambda: [])
    monkeypatch.setattr(
        sheets_repo,
        "load_submission_records",
        lambda: {"sub_001": {"submission_id": "sub_001"}},
    )
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")

    upserted = update_or_create_ops_workflow_state(
        "sub_001",
        {
            "notes": "First note",
            "updated_by": "reviewer@example.org",
        },
    )

    assert upserted["status"] == "new"
    assert upserted["notes"] == "First note"
    assert upserted["updated_by"] == "reviewer@example.org"


def test_update_or_create_ops_workflow_state_updates_existing_row(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        rows=[
            [
                "sub_001",
                "contacted",
                "Original note",
                "priority",
                "call",
                "05-25-2026 09:00:00 UTC",
                "old@example.org",
            ]
        ]
    )

    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")

    upserted = update_or_create_ops_workflow_state(
        "sub_001",
        {
            "notes": "Updated note",
            "updated_by": "reviewer@example.org",
        },
    )

    assert upserted["status"] == "contacted"
    assert upserted["notes"] == "Updated note"
    assert upserted["tags"] == "priority"
    assert upserted["contact_tracking"] == "call"
    assert _ops_appends(fake_sheet) == []
    assert _event_rows(fake_sheet) == [
        ("sub_001", "reviewer@example.org", "update", "notes", "Original note", "Updated note", "05-26-2026 10:00:00 UTC", "dashboard"),
    ]
    assert len(fake_sheet.values_api.update_calls) == 1


def test_update_or_create_ops_workflow_state_rejects_unknown_submission(monkeypatch) -> None:
    fake_sheet = _FakeSheet(rows=[])

    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "load_submission_records", lambda: {})

    try:
        update_or_create_ops_workflow_state(
            "sub_404",
            {
                "status": "reviewed",
                "updated_by": "reviewer@example.org",
            },
        )
    except OpsSubmissionNotFoundError as exc:
        assert str(exc) == "No submission found for submission_id."
    else:
        raise AssertionError("Expected unknown submission to be rejected")

    assert fake_sheet.values_api.append_calls == []
    assert fake_sheet.values_api.update_calls == []


def test_update_or_create_ops_workflow_state_uses_normalized_id_for_update_paths(
    monkeypatch,
) -> None:
    update_calls = []

    def fake_update(submission_id, workflow_fields):
        update_calls.append((submission_id, workflow_fields))
        if len(update_calls) == 2:
            return {"submission_id": submission_id, "status": "reviewed"}
        return None

    monkeypatch.setattr(
        ops_write_service,
        "update_existing_ops_workflow_state",
        fake_update,
    )
    monkeypatch.setattr(
        sheets_repo,
        "load_submission_records",
        lambda: {"sub_001": {"submission_id": "sub_001"}},
    )
    monkeypatch.setattr(
        ops_write_service,
        "create_first_ops_workflow_state",
        lambda *args: None,
    )

    upserted = update_or_create_ops_workflow_state(
        " sub_001 ",
        {
            "status": "reviewed",
            "updated_by": "reviewer@example.org",
        },
    )

    assert upserted == {"submission_id": "sub_001", "status": "reviewed"}
    assert [call[0] for call in update_calls] == ["sub_001", "sub_001"]


def test_update_with_unchanged_values_emits_no_ops_events(monkeypatch) -> None:
    fake_sheet = _FakeSheet(
        rows=[
            [
                "sub_001",
                "reviewed",
                "Same note",
                "",
                "",
                "05-25-2026 09:00:00 UTC",
                "old@example.org",
            ]
        ]
    )

    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")

    updated = update_existing_ops_workflow_state(
        "sub_001",
        {
            "status": "reviewed",
            "notes": "Same note",
            "updated_by": "reviewer@example.org",
        },
    )

    assert updated is not None
    assert _event_appends(fake_sheet) == []


def test_ops_event_append_failure_does_not_block_ops_write(monkeypatch, capsys) -> None:
    fake_sheet = _FakeSheet(
        rows=[
            [
                "sub_001",
                "new",
                "",
                "",
                "",
                "05-25-2026 09:00:00 UTC",
                "old@example.org",
            ]
        ]
    )

    real_append = fake_sheet.values_api.append

    def failing_event_append(**kwargs):
        if kwargs["range"] == "ops_events!A2":
            raise RuntimeError("ops_events tab missing")
        return real_append(**kwargs)

    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(sheets_repo, "_local_timestamp", lambda: "05-26-2026 10:00:00 UTC")
    monkeypatch.setattr(fake_sheet.values_api, "append", failing_event_append)

    updated = update_existing_ops_workflow_state(
        "sub_001",
        {
            "status": "reviewed",
            "updated_by": "reviewer@example.org",
        },
    )

    assert updated is not None
    assert updated["status"] == "reviewed"
    assert len(fake_sheet.values_api.update_calls) == 1
    assert "WARNING: ops_events append failed" in capsys.readouterr().out


def test_append_ops_event_rows_skips_when_no_changes(monkeypatch) -> None:
    fake_sheet = _FakeSheet()
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)

    sheets_repo.append_ops_event_rows(
        submission_id="sub_001",
        actor_email="reviewer@example.org",
        action="update",
        changes=[],
    )

    assert fake_sheet.values_api.append_calls == []
