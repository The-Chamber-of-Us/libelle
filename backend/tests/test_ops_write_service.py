from services.ops_write_service import create_first_ops_workflow_state
from storage import sheets_repo


class _FakeAppendRequest:
    def execute(self):
        return {}


class _FakeValues:
    def __init__(self):
        self.append_calls = []

    def append(self, **kwargs):
        self.append_calls.append(kwargs)
        return _FakeAppendRequest()


class _FakeSheet:
    def __init__(self):
        self.values_api = _FakeValues()

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
