from copy import deepcopy
from datetime import datetime, timezone

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

    parser_jobs = [{"submission_id": "sub_001", "status": "queued"}]
    import storage.parser_jobs_repo as parser_jobs_repo

    monkeypatch.setattr(parser_jobs_repo, "list_parser_jobs", lambda: parser_jobs)

    def fake_assemble(
        loaded_submissions,
        loaded_parser_rows,
        loaded_ops_rows,
        loaded_error_rows,
        loaded_parser_jobs,
    ):
        assert loaded_submissions == submissions
        assert loaded_parser_rows == parser_rows
        assert loaded_ops_rows == ops_rows
        assert loaded_error_rows == error_rows
        assert loaded_parser_jobs == parser_jobs
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
            "drive_file_id": "drive-file-2",
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
            "drive_file_id": "drive-file-1",
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
        "parser_job",
        "ops",
        "errors",
    }
    assert first["submission_health_state"] == SubmissionHealthState.COMPLETE.value
    assert first["raw"]["full_name"] == "First Person"
    assert first["raw"]["skills_raw"] == "Python"
    assert "submission_id" not in first["raw"]
    assert "drive_file_id" not in first["raw"]

    assert first["parsed"] == {
        "parser_state": "complete",
        "parser_result_state": "available",
        "parser_run_id": "2",
        "created_at": "2026-04-19T12:00:00",
        "parser_version": "v1",
        "parsed_skills_raw": '["Python"]',
        "parsed_location_raw": "Raleigh, NC",
        "parser_confidence": "0.90",
        "parser_confidence_score": 0.9,
    }
    assert first["resolved"] == {
        "resolver_state": "resolved",
        "resolver_result_state": "available",
        "resolver_version": "resolver-v1",
        "aliases_version": "aliases-v1",
        "resolved_skill_ids": '["python"]',
        "unknown_skills": "[]",
        "resolver_coverage": "1.0",
        "resolver_coverage_score": 1.0,
    }
    assert first["parser_job"] is None
    assert first["ops"]["status"] == "contacted"
    assert first["errors"] == {
        "error_state": "present",
        "has_error": True,
        "latest_error_summary": "Parser warning",
        "latest_error_stage": "parser",
        "latest_error_code": "PARSE_WARN",
    }

    second = records[1]
    assert second["submission_health_state"] == SubmissionHealthState.PENDING_PROCESSING.value
    assert second["parsed"]["parser_state"] == "pending"
    assert second["resolved"]["resolver_state"] == "not_run"
    assert second["parser_job"] is None
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
    assert records[0]["parsed"]["parser_result_state"] == "skipped"
    assert records[0]["resolved"]["resolver_result_state"] == "unavailable_upstream"


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
    assert records[0]["resolved"]["resolver_result_state"] == "not_yet_run"
    assert records[1]["resolved"]["resolver_state"] == "zero_matches"
    assert records[1]["resolved"]["resolver_result_state"] == "empty_success"
    assert records[1]["resolved"]["resolver_coverage_score"] == 0.0


def test_assemble_snapshot_records_marks_parser_not_yet_run() -> None:
    submissions = {
        "sub_001": {
            "submission_id": "sub_001",
            "full_name": "Pending Parser",
            "resume_status": "uploaded",
        }
    }

    records = assemble_snapshot_records(submissions, [], [], [])

    assert records[0]["parsed"]["parser_state"] == "pending"
    assert records[0]["parsed"]["parser_result_state"] == "not_yet_run"
    assert records[0]["parsed"]["parser_confidence_score"] is None


def test_assemble_snapshot_records_marks_parser_empty_success() -> None:
    submissions = {
        "sub_001": {
            "submission_id": "sub_001",
            "full_name": "Empty Parser",
            "resume_status": "uploaded",
        }
    }
    parser_rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "run-empty",
            "created_at": "2026-04-20T11:00:00",
            "parser_version": "parser-v1",
            "parsed_skills_raw": "",
            "parsed_location_raw": "",
            "parser_confidence": "0.0",
        }
    ]

    records = assemble_snapshot_records(submissions, parser_rows, [], [])

    assert records[0]["parsed"]["parser_state"] == "complete"
    assert records[0]["parsed"]["parser_result_state"] == "empty_success"
    assert records[0]["parsed"]["parser_confidence_score"] == 0.0


def test_assemble_snapshot_records_marks_errors_none_present_and_unavailable() -> None:
    submissions = {
        "sub_001": {"submission_id": "sub_001", "full_name": "No Error"},
        "sub_002": {"submission_id": "sub_002", "full_name": "Has Error"},
    }
    error_rows = [
        {
            "submission_id": "sub_002",
            "created_at": "2026-04-20T11:00:00",
            "stage": "parser",
            "error_code": "PARSER_FAILED",
            "error_summary": "Parser failed",
            "error_details": "do not expose",
        }
    ]

    records = assemble_snapshot_records(submissions, [], [], error_rows)
    unavailable_records = assemble_snapshot_records(submissions, [], [], None)

    assert records[0]["errors"]["error_state"] == "none"
    assert records[0]["errors"]["has_error"] is False
    assert records[1]["errors"]["error_state"] == "present"
    assert records[1]["errors"]["has_error"] is True
    assert unavailable_records[0]["errors"]["error_state"] == "unavailable"
    assert unavailable_records[0]["errors"]["has_error"] is False


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
        "parser_result_state": "available",
        "parser_run_id": "aaaaaaaa",
        "created_at": "2026-04-20T11:00:00",
        "parser_version": "parser-new",
        "parsed_skills_raw": '["new parsed skill"]',
        "parsed_location_raw": "New City",
        "parser_confidence": "0.95",
        "parser_confidence_score": 0.95,
    }
    assert records[0]["resolved"] == {
        "resolver_state": "resolved",
        "resolver_result_state": "available",
        "resolver_version": "resolver-new",
        "aliases_version": "aliases-new",
        "resolved_skill_ids": '["new-resolved-skill"]',
        "unknown_skills": "[]",
        "resolver_coverage": "1.0",
        "resolver_coverage_score": 1.0,
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
    assert records[0]["resolved"]["resolver_result_state"] == "failed"
    assert records[0]["errors"] == {
        "error_state": "present",
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
    assert records[0]["parsed"]["parser_result_state"] == "failed"
    assert records[0]["resolved"]["resolver_result_state"] == "unavailable_upstream"


def test_assemble_snapshot_records_does_not_mutate_inputs() -> None:
    submissions = {"sub_001": {"submission_id": "sub_001", "full_name": "First Person"}}
    parser_rows = [{"submission_id": "sub_001", "parser_run_id": "1"}]
    ops_rows = [{"submission_id": "sub_001", "status": "new"}]
    error_rows = [{"submission_id": "sub_001", "error_summary": "Warning"}]
    original = deepcopy((submissions, parser_rows, ops_rows, error_rows))

    records = assemble_snapshot_records(submissions, parser_rows, ops_rows, error_rows)
    records[0]["raw"]["full_name"] = "Changed"
    records[0]["parsed"]["parser_run_id"] = "999"
    records[0]["parser_job"] = {"parser_job_status": "running"}
    records[0]["ops"]["status"] = "contacted"
    records[0]["errors"]["latest_error_summary"] = "Changed"

    assert (submissions, parser_rows, ops_rows, error_rows) == original


def test_assemble_snapshot_records_surfaces_queued_parser_job_safely() -> None:
    submissions = {
        "sub_001": {
            "submission_id": "sub_001",
            "full_name": "Queued Person",
            "email": "queued@example.org",
            "drive_file_id": "drive-secret",
            "resume_status": "uploaded",
        }
    }
    parser_jobs = [
        {
            "job_id": "job-secret",
            "submission_id": "sub_001",
            "drive_file_id": "drive-secret",
            "resume_filename": "resume.pdf",
            "job_type": "parse_resume",
            "status": "queued",
            "attempt_count": "0",
            "max_attempts": "3",
            "available_at": "05-26-2026 10:00:00 UTC",
            "locked_by": "worker-secret",
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
    ]

    records = assemble_snapshot_records(
        submissions,
        [],
        [],
        [],
        parser_jobs,
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
    )

    parser_job = records[0]["parser_job"]
    assert parser_job == {
        "submission_id": "sub_001",
        "parser_job_status": "queued",
        "attempt_count": 0,
        "max_attempts": 3,
        "parser_run_id": "",
        "is_stale": False,
        "parser_job_state_quality": "valid",
        "last_error_code": None,
        "last_error_summary": None,
        "available_at": "05-26-2026 10:00:00 UTC",
        "parser_started_at": "",
        "created_at": "05-26-2026 10:00:00 UTC",
        "updated_at": "05-26-2026 10:00:00 UTC",
    }
    assert "drive_file_id" not in parser_job
    assert "resume_filename" not in parser_job
    assert "locked_by" not in parser_job
    assert "lock_expires_at" not in parser_job


def test_assemble_snapshot_records_surfaces_running_job_without_lease_details() -> None:
    records = assemble_snapshot_records(
        {"sub_001": {"submission_id": "sub_001", "resume_status": "uploaded"}},
        [],
        [],
        [],
        [
            {
                "submission_id": "sub_001",
                "status": "running",
                "attempt_count": "1",
                "max_attempts": "3",
                "last_parser_run_id": "run-current",
                "lock_expires_at": "05-26-2026 11:00:00 UTC",
            }
        ],
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
    )

    parser_job = records[0]["parser_job"]
    assert parser_job["parser_job_status"] == "running"
    assert parser_job["attempt_count"] == 1
    assert parser_job["parser_run_id"] == "run-current"
    assert parser_job["is_stale"] is False
    assert "locked_at" not in parser_job


def test_assemble_snapshot_records_surfaces_retry_failure_and_stale_states() -> None:
    submissions = {
        "sub_retry": {"submission_id": "sub_retry", "resume_status": "uploaded"},
        "sub_failed": {"submission_id": "sub_failed", "resume_status": "uploaded"},
        "sub_stale": {"submission_id": "sub_stale", "resume_status": "uploaded"},
    }
    parser_jobs = [
        {
            "submission_id": "sub_retry",
            "status": "retry_scheduled",
            "attempt_count": "2",
            "max_attempts": "3",
            "last_parser_run_id": "run-retry",
            "last_error_code": "parser_timeout",
            "last_error_summary": " Parser timed out\nwill retry ",
        },
        {
            "submission_id": "sub_failed",
            "status": "failed",
            "attempt_count": "3",
            "max_attempts": "3",
            "last_parser_run_id": "run-failed",
            "last_error_code": "PARSER_VALIDATION_FAILED",
            "last_error_summary": "Parser validation failed",
        },
        {
            "submission_id": "sub_stale",
            "status": "running",
            "attempt_count": "1",
            "max_attempts": "3",
            "last_parser_run_id": "run-stale",
            "lock_expires_at": "05-26-2026 10:00:00 UTC",
        },
    ]

    records = assemble_snapshot_records(
        submissions,
        [],
        [],
        [],
        parser_jobs,
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
    )
    by_submission_id = {record["submission_id"]: record for record in records}

    assert by_submission_id["sub_retry"]["parser_job"]["parser_job_status"] == "retry_scheduled"
    assert by_submission_id["sub_retry"]["parser_job"]["attempt_count"] == 2
    assert by_submission_id["sub_retry"]["parser_job"]["last_error_code"] == "PARSER_TIMEOUT"
    assert (
        by_submission_id["sub_retry"]["parser_job"]["last_error_summary"]
        == "Parser timed out will retry"
    )
    assert by_submission_id["sub_failed"]["parser_job"]["parser_job_status"] == "failed"
    assert by_submission_id["sub_failed"]["parser_job"]["last_error_code"] == (
        "PARSER_VALIDATION_FAILED"
    )
    assert by_submission_id["sub_stale"]["parser_job"]["parser_job_status"] == "running"
    assert by_submission_id["sub_stale"]["parser_job"]["is_stale"] is True


def test_assemble_snapshot_records_uses_authoritative_parser_run_for_succeeded_job() -> None:
    records = assemble_snapshot_records(
        {"sub_001": {"submission_id": "sub_001", "resume_status": "uploaded"}},
        [
            {
                "submission_id": "sub_001",
                "parser_run_id": "run-authoritative",
                "created_at": "2026-04-20T10:00:00",
                "parser_version": "parser-v1",
                "parsed_skills_raw": '["authoritative"]',
                "parsed_location_raw": "Authoritative City",
                "parser_confidence": "0.80",
                "resolver_version": "resolver-v1",
                "aliases_version": "aliases-v1",
                "resolved_skill_ids": '["authoritative"]',
                "unknown_skills": "[]",
                "resolver_coverage": "1.0",
            },
            {
                "submission_id": "sub_001",
                "parser_run_id": "run-newer-nonauthoritative",
                "created_at": "2026-04-20T11:00:00",
                "parser_version": "parser-v1",
                "parsed_skills_raw": '["newer"]',
                "parsed_location_raw": "Newer City",
                "parser_confidence": "0.90",
                "resolver_version": "resolver-v1",
                "aliases_version": "aliases-v1",
                "resolved_skill_ids": '["newer"]',
                "unknown_skills": "[]",
                "resolver_coverage": "1.0",
            },
        ],
        [],
        [],
        [
            {
                "submission_id": "sub_001",
                "status": "succeeded",
                "attempt_count": "2",
                "max_attempts": "3",
                "last_parser_run_id": "run-newer-nonauthoritative",
                "authoritative_parser_run_id": "run-authoritative",
            }
        ],
    )

    assert records[0]["parser_job"]["parser_job_status"] == "succeeded"
    assert records[0]["parser_job"]["parser_run_id"] == "run-authoritative"
    assert records[0]["parsed"]["parser_run_id"] == "run-authoritative"
    assert records[0]["parsed"]["parsed_skills_raw"] == '["authoritative"]'
    assert records[0]["resolved"]["resolved_skill_ids"] == '["authoritative"]'


def test_assemble_snapshot_records_derives_parser_failed_health_from_terminal_job() -> None:
    records = assemble_snapshot_records(
        {"sub_001": {"submission_id": "sub_001", "resume_status": "uploaded"}},
        [],
        [],
        [],
        [
            {
                "submission_id": "sub_001",
                "status": "failed",
                "attempt_count": "3",
                "max_attempts": "3",
                "last_parser_run_id": "run-failed",
            }
        ],
    )

    assert records[0]["submission_health_state"] == SubmissionHealthState.PARSER_FAILED.value
    assert records[0]["parsed"]["parser_result_state"] == "failed"
    assert records[0]["resolved"]["resolver_result_state"] == "unavailable_upstream"
    assert records[0]["parser_job"]["parser_job_status"] == "failed"


def test_assemble_snapshot_records_preserves_malformed_parser_job_state_as_unknown() -> None:
    records = assemble_snapshot_records(
        {"sub_001": {"submission_id": "sub_001", "resume_status": "uploaded"}},
        [],
        [],
        [],
        [
            {
                "submission_id": "sub_001",
                "status": "running",
                "attempt_count": "oops",
                "max_attempts": "0",
                "last_parser_run_id": "run-current",
                "lock_expires_at": "not a timestamp",
            }
        ],
        now=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
    )

    parser_job = records[0]["parser_job"]
    assert parser_job["parser_job_status"] == "running"
    assert parser_job["attempt_count"] is None
    assert parser_job["max_attempts"] is None
    assert parser_job["is_stale"] is None
    assert parser_job["parser_job_state_quality"] == "malformed"


def test_assemble_snapshot_records_marks_unknown_for_invalid_parser_job_status() -> None:
    records = assemble_snapshot_records(
        {"sub_001": {"submission_id": "sub_001", "resume_status": "uploaded"}},
        [],
        [],
        [],
        [
            {
                "submission_id": "sub_001",
                "status": "definitely_not_valid",
                "attempt_count": "1",
                "max_attempts": "3",
            }
        ],
    )

    parser_job = records[0]["parser_job"]
    assert parser_job["parser_job_status"] == "unknown"
    assert parser_job["parser_job_state_quality"] == "malformed"
