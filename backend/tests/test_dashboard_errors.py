from services.dashboard_errors import summarize_submission_errors


def test_summarize_submission_errors_returns_no_error_summary_when_empty() -> None:
    summary = summarize_submission_errors("sub_001", [])

    assert summary == {
        "has_error": False,
        "latest_error_summary": "",
        "latest_error_stage": "",
        "latest_error_code": "",
    }


def test_summarize_submission_errors_returns_no_error_summary_when_no_match() -> None:
    rows = [
        {
            "submission_id": "sub_999",
            "created_at": "04-20-2026 10:00:00 UTC",
            "stage": "parser",
            "error_code": "PARSE_FAILED",
            "error_summary": "Parser failed",
            "error_details": "stack trace should not be exposed",
        }
    ]

    summary = summarize_submission_errors("sub_001", rows)

    assert summary["has_error"] is False
    assert summary["latest_error_summary"] == ""
    assert summary["latest_error_stage"] == ""
    assert summary["latest_error_code"] == ""


def test_summarize_submission_errors_selects_latest_error_by_created_at() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "created_at": "04-20-2026 10:00:00 UTC",
            "stage": "upload",
            "error_code": "UPLOAD_FAILED",
            "error_summary": "Older upload error",
            "error_details": "old stack trace",
        },
        {
            "submission_id": "sub_001",
            "created_at": "04-20-2026 12:00:00 UTC",
            "stage": "parser",
            "error_code": "PARSE_FAILED",
            "error_summary": "Latest parser error",
            "error_details": "new stack trace",
        },
    ]

    summary = summarize_submission_errors("sub_001", rows)

    assert summary["has_error"] is True
    assert summary["latest_error_summary"] == "Latest parser error"
    assert summary["latest_error_stage"] == "parser"
    assert summary["latest_error_code"] == "PARSE_FAILED"


def test_summarize_submission_errors_filters_by_submission_id() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "created_at": "04-20-2026 10:00:00 UTC",
            "stage": "parser",
            "error_code": "PARSE_FAILED",
            "error_summary": "Correct submission error",
        },
        {
            "submission_id": "sub_002",
            "created_at": "04-20-2026 12:00:00 UTC",
            "stage": "resolver",
            "error_code": "RESOLVE_FAILED",
            "error_summary": "Wrong submission newer error",
        },
    ]

    summary = summarize_submission_errors("sub_001", rows)

    assert summary["has_error"] is True
    assert summary["latest_error_summary"] == "Correct submission error"
    assert summary["latest_error_stage"] == "parser"
    assert summary["latest_error_code"] == "PARSE_FAILED"


def test_summarize_submission_errors_does_not_expose_error_details_or_history() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "created_at": "04-20-2026 10:00:00 UTC",
            "stage": "parser",
            "error_code": "PARSE_FAILED",
            "error_summary": "Parser failed",
            "error_details": "sensitive stack trace",
        }
    ]

    summary = summarize_submission_errors("sub_001", rows)

    assert "error_details" not in summary
    assert "errors" not in summary
    assert "history" not in summary


def test_summarize_submission_errors_normalizes_timezone_aware_and_naive_timestamps() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "created_at": "2026-04-20T10:00:00",
            "stage": "parser",
            "error_code": "OLDER",
            "error_summary": "Older naive timestamp",
        },
        {
            "submission_id": "sub_001",
            "created_at": "2026-04-20T12:00:00+0000",
            "stage": "resolver",
            "error_code": "NEWER",
            "error_summary": "Newer aware timestamp",
        },
    ]

    summary = summarize_submission_errors("sub_001", rows)

    assert summary["latest_error_summary"] == "Newer aware timestamp"
    assert summary["latest_error_stage"] == "resolver"
    assert summary["latest_error_code"] == "NEWER"