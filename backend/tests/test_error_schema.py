import re

from error_schema import build_error_event
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


def test_build_error_event_returns_required_prd_keys() -> None:
    event = build_error_event(
        submission_id="sub_123",
        stage="upload",
        error_code="PDF_READ_FAILED",
        error_summary="Failed to read uploaded PDF",
        error_details="PyMuPDF could not extract text",
        created_at="2026-04-21T13:45:00Z",
    )

    assert event == {
        "submission_id": "sub_123",
        "created_at": "2026-04-21T13:45:00Z",
        "stage": "upload",
        "error_code": "PDF_READ_FAILED",
        "error_summary": "Failed to read uploaded PDF",
        "error_details": "PyMuPDF could not extract text",
    }


def test_build_error_event_auto_generates_utc_timestamp() -> None:
    event = build_error_event(
        submission_id="sub_456",
        stage="parser",
        error_code="PARSER_EXCEPTION",
        error_summary="Unhandled parser exception",
    )

    assert isinstance(event["created_at"], str)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", event["created_at"]) is not None


def test_build_error_event_handles_missing_optional_error_details() -> None:
    event = build_error_event(
        submission_id="sub_789",
        stage="storage",
        error_code="SHEETS_APPEND_FAILED",
        error_summary="Failed to append row to sheet",
    )

    assert event["error_details"] == ""


def test_build_error_event_normalizes_none_error_details_to_empty_string() -> None:
    event = build_error_event(
        submission_id="sub_999",
        stage="resolver",
        error_code="RESOLVER_FAILURE",
        error_summary="Resolver failed unexpectedly",
        error_details=None,  # type: ignore[arg-type]
    )

    assert event["error_details"] == ""


def test_append_error_row_writes_schema_aligned_errors_row(monkeypatch) -> None:
    fake_sheet = _FakeSheet()

    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: fake_sheet)
    monkeypatch.setattr(
        sheets_repo,
        "build_error_event",
        lambda **kwargs: {
            **kwargs,
            "created_at": "2026-04-21T13:45:00Z",
        },
    )

    event = sheets_repo.append_error_row(
        submission_id=" sub_123 ",
        stage="resolver",
        error_code="RESOLVER_FAILED",
        error_summary="Resolver failed",
        error_details="RuntimeError: resolver blew up",
    )

    assert event == {
        "submission_id": "sub_123",
        "stage": "resolver",
        "error_code": "RESOLVER_FAILED",
        "error_summary": "Resolver failed",
        "error_details": "RuntimeError: resolver blew up",
        "created_at": "2026-04-21T13:45:00Z",
    }
    assert fake_sheet.values_api.append_calls == [
        {
            "spreadsheetId": "test-sheet-id",
            "range": "errors!A2",
            "valueInputOption": "RAW",
            "insertDataOption": "INSERT_ROWS",
            "body": {
                "values": [
                    [
                        "sub_123",
                        "2026-04-21T13:45:00Z",
                        "resolver",
                        "RESOLVER_FAILED",
                        "Resolver failed",
                        "RuntimeError: resolver blew up",
                    ]
                ]
            },
        }
    ]
