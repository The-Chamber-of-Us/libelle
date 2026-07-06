from copy import deepcopy

from core.state_contract import SubmissionHealthState
import services.dashboard_service as dashboard_service
from services.dashboard_service import assemble_snapshot_records


def test_get_snapshot_records_loads_layers_and_assembles(monkeypatch) -> None:
    submissions = {"sub_001": {"submission_id": "sub_001", "full_name": "First Person"}}
    parser_rows = [{"submission_id": "sub_001", "parser_run_id": "1"}]
    ops_rows = [{"submission_id": "sub_001", "status": "new"}]
    error_rows = [{"submission_id": "sub_001", "error_summary": "Warning"}]
    expected = [{"submission_id": "sub_001"}]

    import storage.sheets_repo as sheets_repo

    monkeypatch.setattr(sheets_repo, "load_submission_records", lambda: submissions)
    monkeypatch.setattr(sheets_repo, "load_parser_result_rows", lambda: parser_rows)
    monkeypatch.setattr(sheets_repo, "load_ops_rows", lambda: ops_rows)
    monkeypatch.setattr(sheets_repo, "load_error_rows", lambda: error_rows)

    def fake_assemble(loaded_submissions, loaded_parser_rows, loaded_ops_rows, loaded_error_rows):
        assert loaded_submissions == submissions
        assert loaded_parser_rows == parser_rows
        assert loaded_ops_rows == ops_rows
        assert loaded_error_rows == error_rows
        return expected

    monkeypatch.setattr(dashboard_service, "assemble_snapshot_records", fake_assemble)

    assert dashboard_service.get_snapshot_records() == expected


def test_assemble_snapshot_records_returns_one_layered_record_per_submission_id() -> None:
    submissions = {
        "sub_002": {
            "submission_id": "sub_002",
            "created_at": "2026-04-20T10:00:00",
            "full_name": "Second Person",
            "email": "second@example.org",
            "location_raw": "Austin, TX",
            "timezone": "",
            "skills_raw": "design",
            "interests": "Research",
            "experience_level": "Mid",
            "availability": "4 hours",
            "motivation": "",
            "linkedin_url": "",
            "github_url": "",
            "consent_given": "TRUE",
            "resume_filename": "sub_002-resume.pdf",
            "resume_status": "uploaded",
        },
        "sub_001": {
            "submission_id": "sub_001",
            "created_at": "2026-04-19T10:00:00",
            "full_name": "First Person",
            "email": "first@example.org",
            "location_raw": "Raleigh, NC",
            "timezone": "",
            "skills_raw": "Python",
            "interests": "Engineering",
            "experience_level": "Senior",
            "availability": "6 hours",
            "motivation": "Help",
            "linkedin_url": "https://linkedin.example/first",
            "github_url": "https://github.example/first",
            "consent_given": "TRUE",
            "resume_filename": "sub_001-resume.pdf",
            "resume_status": "uploaded",
        },
    }
    parser_rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "1",
            "created_at": "2026-04-19T11:00:00",
            "parser_version": "v1",
            "parsed_skills_raw": '["old"]',
            "parsed_location_raw": "Raleigh",
            "parser_confidence": "0.55",
            "resolver_version": "",
            "aliases_version": "",
            "resolved_skill_ids": "",
            "unknown_skills": "",
            "resolver_coverage": "",
        },
        {
            "submission_id": "sub_001",
            "parser_run_id": "2",
            "created_at": "2026-04-19T12:00:00",
            "parser_version": "v1",
            "parsed_skills_raw": '["Python"]',
            "parsed_location_raw": "Raleigh, NC",
            "parser_confidence": "0.90",
            "resolver_version": "resolver-v1",
            "aliases_version": "aliases-v1",
            "resolved_skill_ids": '["python"]',
            "unknown_skills": "[]",
            "resolver_coverage": "1.0",
        },
    ]
    ops_rows = [
        {
            "submission_id": "sub_001",
            "status": "contacted",
            "notes": "Sent email",
            "tags": "python",
            "contact_tracking": "email",
            "updated_at": "2026-04-19T13:00:00",
            "updated_by": "ops@example.org",
        }
    ]
    error_rows = [
        {
            "submission_id": "sub_001",
            "created_at": "2026-04-19T14:00:00",
            "stage": "parser",
            "error_code": "PARSE_WARN",
            "error_summary": "Parser warning",
            "error_details": "do not expose",
        }
    ]

    records = assemble_snapshot_records(submissions, parser_rows, ops_rows, error_rows)

    assert [record["submission_id"] for record in records] == ["sub_001", "sub_002"]
    assert len(records) == 2

    first = records[0]
    assert set(first) == {
        "submission_id",
        "submission_health_state",
        "raw",
        "parsed",
        "resolved",
        "ops",
        "errors",
    }
    assert first["submission_health_state"] == SubmissionHealthState.COMPLETE.value
    assert first["raw"]["full_name"] == "First Person"
    assert first["raw"]["skills_raw"] == "Python"
    assert "submission_id" not in first["raw"]

    assert first["parsed"] == {
        "parser_state": "complete",
        "parser_run_id": "2",
        "created_at": "2026-04-19T12:00:00",
        "parser_version": "v1",
        "parsed_skills_raw": '["Python"]',
        "parsed_location_raw": "Raleigh, NC",
        "parser_confidence": "0.90",
    }
    assert first["resolved"] == {
        "resolver_state": "resolved",
        "resolver_version": "resolver-v1",
        "aliases_version": "aliases-v1",
        "resolved_skill_ids": '["python"]',
        "unknown_skills": "[]",
        "resolver_coverage": "1.0",
    }
    assert first["ops"]["status"] == "contacted"
    assert first["errors"] == {
        "has_error": True,
        "latest_error_summary": "Parser warning",
        "latest_error_stage": "parser",
        "latest_error_code": "PARSE_WARN",
    }

    second = records[1]
    assert second["submission_health_state"] == SubmissionHealthState.PENDING_PROCESSING.value
    assert second["parsed"]["parser_state"] == "pending"
    assert second["resolved"]["resolver_state"] == "not_run"
    assert second["ops"]["status"] == "new"
    assert second["errors"]["has_error"] is False


def test_assemble_snapshot_records_derives_no_resume_health_from_missing_resume() -> None:
    submissions = {
        "sub_001": {
            "submission_id": "sub_001",
            "full_name": "No Resume",
            "resume_status": "missing",
        }
    }

    records = assemble_snapshot_records(submissions, [], [], [])

    assert records[0]["submission_health_state"] == SubmissionHealthState.NO_RESUME_OK.value


def test_assemble_snapshot_records_distinguishes_resolver_not_run_from_zero_matches() -> None:
    submissions = {
        "sub_001": {"submission_id": "sub_001", "full_name": "First Person"},
        "sub_002": {"submission_id": "sub_002", "full_name": "Second Person"},
    }
    parser_rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "1",
            "resolved_skill_ids": "",
            "unknown_skills": "",
            "resolver_coverage": "",
        },
        {
            "submission_id": "sub_002",
            "parser_run_id": "1",
            "resolver_version": "resolver-v1",
            "aliases_version": "aliases-v1",
            "resolved_skill_ids": "[]",
            "unknown_skills": '["made up skill"]',
            "resolver_coverage": "0.0",
        },
    ]

    records = assemble_snapshot_records(submissions, parser_rows, [], [])

    assert records[0]["resolved"]["resolver_state"] == "not_run"
    assert records[1]["resolved"]["resolver_state"] == "zero_matches"


def test_assemble_snapshot_records_uses_one_latest_parser_result_row() -> None:
    submissions = {"sub_001": {"submission_id": "sub_001", "full_name": "First Person"}}
    parser_rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "zzzzzzzz",
            "created_at": "2026-04-20T10:00:00",
            "parser_version": "parser-old",
            "parsed_skills_raw": '["old parsed skill"]',
            "parsed_location_raw": "Old City",
            "parser_confidence": "0.20",
            "resolver_version": "resolver-old",
            "aliases_version": "aliases-old",
            "resolved_skill_ids": '["old-resolved-skill"]',
            "unknown_skills": "[]",
            "resolver_coverage": "1.0",
        },
        {
            "submission_id": "sub_001",
            "parser_run_id": "aaaaaaaa",
            "created_at": "2026-04-20T11:00:00",
            "parser_version": "parser-new",
            "parsed_skills_raw": '["new parsed skill"]',
            "parsed_location_raw": "New City",
            "parser_confidence": "0.95",
            "resolver_version": "resolver-new",
            "aliases_version": "aliases-new",
            "resolved_skill_ids": '["new-resolved-skill"]',
            "unknown_skills": "[]",
            "resolver_coverage": "1.0",
        },
    ]

    records = assemble_snapshot_records(submissions, parser_rows, [], [])

    assert records[0]["parsed"] == {
        "parser_state": "complete",
        "parser_run_id": "aaaaaaaa",
        "created_at": "2026-04-20T11:00:00",
        "parser_version": "parser-new",
        "parsed_skills_raw": '["new parsed skill"]',
        "parsed_location_raw": "New City",
        "parser_confidence": "0.95",
    }
    assert records[0]["resolved"] == {
        "resolver_state": "resolved",
        "resolver_version": "resolver-new",
        "aliases_version": "aliases-new",
        "resolved_skill_ids": '["new-resolved-skill"]',
        "unknown_skills": "[]",
        "resolver_coverage": "1.0",
    }


def test_assemble_snapshot_records_preserves_parser_output_when_resolver_failed() -> None:
    submissions = {
        "sub_001": {
            "submission_id": "sub_001",
            "full_name": "First Person",
            "resume_status": "uploaded",
        }
    }
    parser_rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "run-1",
            "created_at": "2026-04-20T11:00:00",
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
    ]
    error_rows = [
        {
            "submission_id": "sub_001",
            "created_at": "2026-04-20T11:01:00",
            "stage": "resolver",
            "error_code": "RESOLVER_FAILED",
            "error_summary": "Resolver failed",
            "error_details": "do not expose",
        }
    ]

    records = assemble_snapshot_records(submissions, parser_rows, [], error_rows)

    assert records[0]["submission_health_state"] == SubmissionHealthState.RESOLVER_FAILED.value
    assert records[0]["parsed"]["parser_state"] == "complete"
    assert records[0]["parsed"]["parsed_skills_raw"] == '["Python"]'
    assert records[0]["resolved"]["resolver_state"] == "not_run"
    assert records[0]["errors"] == {
        "has_error": True,
        "latest_error_summary": "Resolver failed",
        "latest_error_stage": "resolver",
        "latest_error_code": "RESOLVER_FAILED",
    }


def test_assemble_snapshot_records_derives_parser_failed_health_from_parser_error() -> None:
    submissions = {
        "sub_001": {
            "submission_id": "sub_001",
            "full_name": "Parser Failed",
            "resume_status": "uploaded",
        }
    }
    error_rows = [
        {
            "submission_id": "sub_001",
            "created_at": "2026-04-20T11:00:00",
            "stage": "parser",
            "error_code": "PARSER_FAILED",
            "error_summary": "Parser failed",
            "error_details": "do not expose",
        }
    ]

    records = assemble_snapshot_records(submissions, [], [], error_rows)

    assert records[0]["submission_health_state"] == SubmissionHealthState.PARSER_FAILED.value


def test_assemble_snapshot_records_does_not_mutate_inputs() -> None:
    submissions = {"sub_001": {"submission_id": "sub_001", "full_name": "First Person"}}
    parser_rows = [{"submission_id": "sub_001", "parser_run_id": "1"}]
    ops_rows = [{"submission_id": "sub_001", "status": "new"}]
    error_rows = [{"submission_id": "sub_001", "error_summary": "Warning"}]
    original = deepcopy((submissions, parser_rows, ops_rows, error_rows))

    records = assemble_snapshot_records(submissions, parser_rows, ops_rows, error_rows)
    records[0]["raw"]["full_name"] = "Changed"
    records[0]["parsed"]["parser_run_id"] = "999"
    records[0]["ops"]["status"] = "contacted"
    records[0]["errors"]["latest_error_summary"] = "Changed"

    assert (submissions, parser_rows, ops_rows, error_rows) == original
