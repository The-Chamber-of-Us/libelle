from copy import deepcopy

from services.dashboard_service import assemble_snapshot_records


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
    assert set(first) == {"submission_id", "raw", "parsed", "resolved", "ops", "errors"}
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
    assert second["parsed"]["parser_state"] == "pending"
    assert second["resolved"]["resolver_state"] == "not_run"
    assert second["ops"]["status"] == "new"
    assert second["errors"]["has_error"] is False


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
