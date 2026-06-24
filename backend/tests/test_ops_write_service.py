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
    assert fake_sheet.values_api.append_calls == [
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
    assert fake_sheet.values_api.append_calls == []
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
    assert fake_sheet.values_api.append_calls == [
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
    assert fake_sheet.values_api.append_calls == []
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
