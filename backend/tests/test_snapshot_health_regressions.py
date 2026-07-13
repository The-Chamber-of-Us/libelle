"""Regression cases for /snapshot health derivation over contradictory sources.

Issue #309. These tests pin the snapshot trust behavior from #294/#279 and the
precedence rules from #295 for source states that are contradictory, partial,
or degraded. Health must always come from derive_submission_health_state();
degraded parser/resolver/error state must never hide a submission.
"""

from core.state_contract import SubmissionHealthState
from services.dashboard_service import assemble_snapshot_records


def _submission(submission_id: str, resume_status: str = "uploaded") -> dict:
    return {
        "submission_id": submission_id,
        "full_name": f"Person {submission_id}",
        "email": f"{submission_id}@example.org",
        "resume_status": resume_status,
    }


def _parser_row(submission_id: str, with_resolver: bool = True) -> dict:
    row = {
        "submission_id": submission_id,
        "parser_run_id": "run-1",
        "created_at": "2026-07-01T10:00:00",
        "parser_version": "parser-v1",
        "parsed_skills_raw": '["Python"]',
        "parsed_location_raw": "Raleigh, NC",
        "parser_confidence": "0.90",
        "resolver_version": "",
        "aliases_version": "",
        "resolved_skill_ids": "",
        "unknown_skills": "",
        "resolver_coverage": "",
    }
    if with_resolver:
        row.update(
            {
                "resolver_version": "resolver-v1",
                "aliases_version": "aliases-v1",
                "resolved_skill_ids": '["python"]',
                "unknown_skills": "[]",
                "resolver_coverage": "1.0",
            }
        )
    return row


def _error_row(submission_id: str, stage: str, error_code: str) -> dict:
    return {
        "submission_id": submission_id,
        "created_at": "2026-07-01T11:00:00",
        "stage": stage,
        "error_code": error_code,
        "error_summary": f"{stage} issue",
        "error_details": "do not expose",
    }


def test_parser_warning_with_full_output_stays_complete_and_error_visible() -> None:
    submissions = {"sub_001": _submission("sub_001")}
    parser_rows = [_parser_row("sub_001")]
    error_rows = [_error_row("sub_001", "parser", "PARSE_WARN")]

    records = assemble_snapshot_records(submissions, parser_rows, [], error_rows)

    record = records[0]
    assert record["submission_health_state"] == SubmissionHealthState.COMPLETE.value
    assert record["parsed"]["parser_result_state"] == "available"
    assert record["resolved"]["resolver_result_state"] == "available"
    assert record["errors"]["has_error"] is True
    assert record["errors"]["latest_error_code"] == "PARSE_WARN"


def test_fatal_parser_error_without_parser_output_is_parser_failed_not_hidden() -> None:
    submissions = {"sub_001": _submission("sub_001")}
    error_rows = [_error_row("sub_001", "parser", "PARSER_FAILED")]

    records = assemble_snapshot_records(submissions, [], [], error_rows)

    assert len(records) == 1
    record = records[0]
    assert record["submission_health_state"] == SubmissionHealthState.PARSER_FAILED.value
    assert record["parsed"]["parser_result_state"] == "failed"
    assert record["resolved"]["resolver_result_state"] == "unavailable_upstream"
    assert record["raw"]["full_name"] == "Person sub_001"


def test_parser_output_present_alongside_fatal_parser_error_prefers_selected_output() -> None:
    """Contradiction: a fatal parser error row exists, but a selected
    parser_results row also exists (e.g. a later retry succeeded). The selected
    output is the parser system of record; the error stays reviewer-visible."""
    submissions = {"sub_001": _submission("sub_001")}
    parser_rows = [_parser_row("sub_001")]
    error_rows = [_error_row("sub_001", "parser", "PARSER_FAILED")]

    records = assemble_snapshot_records(submissions, parser_rows, [], error_rows)

    record = records[0]
    assert record["submission_health_state"] == SubmissionHealthState.COMPLETE.value
    assert record["parsed"]["parser_result_state"] == "available"
    assert record["parsed"]["parsed_skills_raw"] == '["Python"]'
    assert record["errors"]["has_error"] is True


def test_resolver_failure_preserves_parser_output_and_stays_visible() -> None:
    submissions = {"sub_001": _submission("sub_001")}
    parser_rows = [_parser_row("sub_001", with_resolver=False)]
    error_rows = [_error_row("sub_001", "resolver", "RESOLVER_FAILED")]

    records = assemble_snapshot_records(submissions, parser_rows, [], error_rows)

    record = records[0]
    assert record["submission_health_state"] == SubmissionHealthState.RESOLVER_FAILED.value
    assert record["parsed"]["parser_result_state"] == "available"
    assert record["parsed"]["parsed_skills_raw"] == '["Python"]'
    assert record["parsed"]["parser_confidence_score"] == 0.9
    assert record["resolved"]["resolver_result_state"] == "failed"


def test_ops_state_survives_degraded_pipeline_state() -> None:
    """Reviewer workflow state is reviewer-owned truth: an existing ops row is
    composed unchanged even when the pipeline behind it is degraded."""
    submissions = {"sub_001": _submission("sub_001")}
    ops_rows = [
        {
            "submission_id": "sub_001",
            "status": "contacted",
            "notes": "Spoke on the phone",
            "tags": "priority",
            "contact_tracking": "call",
            "updated_at": "2026-07-01T12:00:00",
            "updated_by": "reviewer@example.org",
        }
    ]
    error_rows = [_error_row("sub_001", "parser", "PARSER_FAILED")]

    records = assemble_snapshot_records(submissions, [], ops_rows, error_rows)

    record = records[0]
    assert record["submission_health_state"] == SubmissionHealthState.PARSER_FAILED.value
    assert record["ops"]["status"] == "contacted"
    assert record["ops"]["notes"] == "Spoke on the phone"
    assert record["ops"]["updated_by"] == "reviewer@example.org"


def test_error_rows_never_remove_submissions_from_snapshot() -> None:
    submissions = {
        "sub_001": _submission("sub_001"),
        "sub_002": _submission("sub_002"),
        "sub_003": _submission("sub_003", resume_status="missing"),
    }
    error_rows = [
        _error_row("sub_001", "parser", "PARSER_FAILED"),
        _error_row("sub_002", "file_upload", "UPLOAD_FAILED"),
    ]

    records = assemble_snapshot_records(submissions, [], [], error_rows)

    assert [record["submission_id"] for record in records] == [
        "sub_001",
        "sub_002",
        "sub_003",
    ]


def test_no_resume_submission_is_not_treated_as_parser_failure() -> None:
    submissions = {"sub_001": _submission("sub_001", resume_status="missing")}

    records = assemble_snapshot_records(submissions, [], [], [])

    record = records[0]
    assert record["submission_health_state"] == SubmissionHealthState.NO_RESUME_OK.value
    assert record["parsed"]["parser_result_state"] == "skipped"
    assert record["errors"]["has_error"] is False


def test_no_resume_submission_with_unrelated_error_row_keeps_no_resume_health() -> None:
    """An intake-stage warning must not reclassify a valid no-resume submission
    as a parser failure."""
    submissions = {"sub_001": _submission("sub_001", resume_status="missing")}
    error_rows = [_error_row("sub_001", "intake", "SHEETS_RETRY")]

    records = assemble_snapshot_records(submissions, [], [], error_rows)

    record = records[0]
    assert record["submission_health_state"] == SubmissionHealthState.NO_RESUME_OK.value
    assert record["parsed"]["parser_result_state"] == "skipped"
    assert record["errors"]["has_error"] is True


def test_unknown_resume_status_degrades_to_broken_pipeline_but_stays_listed() -> None:
    submissions = {"sub_001": _submission("sub_001", resume_status="corrupted!!")}

    records = assemble_snapshot_records(submissions, [], [], [])

    assert len(records) == 1
    record = records[0]
    assert record["submission_health_state"] == SubmissionHealthState.BROKEN_PIPELINE.value
    assert record["raw"]["full_name"] == "Person sub_001"
