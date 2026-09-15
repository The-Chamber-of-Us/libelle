from services import parser_job_reconciliation


def _submission(submission_id: str, **overrides):
    row = {
        "submission_id": submission_id,
        "created_at": "05-26-2026 10:00:00 UTC",
        "full_name": "Test User",
        "email": "test@example.com",
        "location_raw": "Remote",
        "timezone": "",
        "skills_raw": "",
        "interests": "ai",
        "experience_level": "beginner",
        "availability": "weekly",
        "motivation": "",
        "linkedin_url": "",
        "github_url": "",
        "consent_given": "TRUE",
        "drive_file_id": f"drive_{submission_id}",
        "resume_filename": f"{submission_id}_resume.pdf",
        "resume_status": "uploaded",
    }
    row.update(overrides)
    return row


def _result(submission_id: str):
    return {
        "submission_id": submission_id,
        "parser_run_id": "run_001",
        "created_at": "05-26-2026 10:01:00 UTC",
    }


def test_uploaded_submission_with_missing_parser_job_is_recovered(monkeypatch):
    created = []
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_submission_records",
        lambda: {"sub_001": _submission("sub_001")},
    )
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_parser_result_rows",
        lambda: [],
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "get_parser_job_by_submission",
        lambda submission_id: None,
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "create_parser_job",
        lambda **kwargs: created.append(kwargs) or {"job_id": "job_001"},
    )

    summary = parser_job_reconciliation.reconcile_missing_parser_jobs()

    assert summary.scanned == 1
    assert summary.eligible == 1
    assert summary.recovered == 1
    assert summary.failures == []
    assert created == [
        {
            "submission_id": "sub_001",
            "drive_file_id": "drive_sub_001",
            "resume_filename": "sub_001_resume.pdf",
        }
    ]


def test_existing_parser_job_is_not_recreated(monkeypatch):
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_submission_records",
        lambda: {"sub_001": _submission("sub_001")},
    )
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_parser_result_rows",
        lambda: [],
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "get_parser_job_by_submission",
        lambda submission_id: {"job_id": "job_001"},
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "create_parser_job",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not create")),
    )

    summary = parser_job_reconciliation.reconcile_missing_parser_jobs()

    assert summary.recovered == 0
    assert summary.skipped_existing_job == 1


def test_successful_parser_result_prevents_reconciliation(monkeypatch):
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_submission_records",
        lambda: {"sub_001": _submission("sub_001")},
    )
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_parser_result_rows",
        lambda: [_result("sub_001")],
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "get_parser_job_by_submission",
        lambda submission_id: None,
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "create_parser_job",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not create")),
    )

    summary = parser_job_reconciliation.reconcile_missing_parser_jobs()

    assert summary.recovered == 0
    assert summary.skipped_successful_result == 1


def test_repeated_reconciliation_remains_logically_idempotent(monkeypatch):
    created = []
    existing_jobs = {}
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_submission_records",
        lambda: {"sub_001": _submission("sub_001")},
    )
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_parser_result_rows",
        lambda: [],
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "get_parser_job_by_submission",
        lambda submission_id: existing_jobs.get(submission_id),
    )

    def fake_create_parser_job(**kwargs):
        created.append(kwargs)
        job = {"job_id": "job_001", "submission_id": kwargs["submission_id"]}
        existing_jobs[kwargs["submission_id"]] = job
        return job

    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "create_parser_job",
        fake_create_parser_job,
    )

    first = parser_job_reconciliation.reconcile_missing_parser_jobs()
    second = parser_job_reconciliation.reconcile_missing_parser_jobs()

    assert first.recovered == 1
    assert second.recovered == 0
    assert second.skipped_existing_job == 1
    assert len(created) == 1


def test_reconciliation_survives_partial_failures(monkeypatch):
    created = []
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_submission_records",
        lambda: {
            "sub_bad": _submission("sub_bad", drive_file_id=""),
            "sub_good": _submission("sub_good"),
        },
    )
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_parser_result_rows",
        lambda: [],
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "get_parser_job_by_submission",
        lambda submission_id: None,
    )

    def fake_create_parser_job(**kwargs):
        if kwargs["submission_id"] == "sub_bad":
            raise ValueError("drive_file_id is required")
        created.append(kwargs["submission_id"])
        return {"job_id": "job_good"}

    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "create_parser_job",
        fake_create_parser_job,
    )

    summary = parser_job_reconciliation.reconcile_missing_parser_jobs()

    assert summary.eligible == 2
    assert summary.recovered == 1
    assert created == ["sub_good"]
    assert len(summary.failures) == 1
    assert summary.failures[0].submission_id == "sub_bad"
    assert summary.failures[0].logical_job_key == "parse_resume:sub_bad"
    assert summary.failures[0].reason == "ValueError"


def test_historical_uploaded_submission_can_be_reconciled(monkeypatch):
    created = []
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_submission_records",
        lambda: {
            "legacy_sub": _submission(
                "legacy_sub",
                created_at="03-01-2026 09:00:00 UTC",
                resume_filename="legacy.pdf",
            )
        },
    )
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_parser_result_rows",
        lambda: [],
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "get_parser_job_by_submission",
        lambda submission_id: None,
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "create_parser_job",
        lambda **kwargs: created.append(kwargs) or {"job_id": "legacy_job"},
    )

    summary = parser_job_reconciliation.reconcile_missing_parser_jobs()

    assert summary.recovered == 1
    assert created[0]["submission_id"] == "legacy_sub"
    assert created[0]["resume_filename"] == "legacy.pdf"


def test_reconciliation_never_modifies_submission_rows(monkeypatch):
    submissions = {"sub_001": _submission("sub_001")}
    before = {key: dict(value) for key, value in submissions.items()}
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_submission_records",
        lambda: submissions,
    )
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_parser_result_rows",
        lambda: [],
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "get_parser_job_by_submission",
        lambda submission_id: None,
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "create_parser_job",
        lambda **kwargs: {"job_id": "job_001"},
    )

    parser_job_reconciliation.reconcile_missing_parser_jobs()

    assert submissions == before


def test_non_uploaded_submission_is_ignored(monkeypatch):
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_submission_records",
        lambda: {
            "sub_missing": _submission("sub_missing", resume_status="missing"),
            "sub_failed": _submission("sub_failed", resume_status="failed"),
        },
    )
    monkeypatch.setattr(
        parser_job_reconciliation.sheets_repo,
        "load_parser_result_rows",
        lambda: [],
    )
    monkeypatch.setattr(
        parser_job_reconciliation.parser_jobs_repo,
        "create_parser_job",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not create")),
    )

    summary = parser_job_reconciliation.reconcile_missing_parser_jobs()

    assert summary.scanned == 2
    assert summary.skipped_not_uploaded == 2
    assert summary.recovered == 0
