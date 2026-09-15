from types import SimpleNamespace

from services import parser_worker
from services.parser_worker import ParserWorker, ParserWorkerConfig


def _worker(run_id="run-1"):
    return ParserWorker(
        ParserWorkerConfig(worker_id="worker-1", lease_seconds=900),
        parser_run_id_factory=lambda: run_id,
    )


def _job(**overrides):
    job = {
        "job_id": "parse_resume:sub-1",
        "submission_id": "sub-1",
        "drive_file_id": "drive-1",
        "status": "running",
        "locked_by": "worker-1",
        "lock_expires_at": "09-01-2027 10:31:00 UTC",
        "last_parser_run_id": "run-1",
        "attempt_count": "1",
        "max_attempts": "3",
        "authoritative_parser_run_id": "",
        "parser_started_at": "",
    }
    job.update(overrides)
    return job


def _patch_claimed_job(monkeypatch, job, calls):
    monkeypatch.setattr(parser_worker, "list_claimable_jobs", lambda limit: [job])
    monkeypatch.setattr(
        parser_worker,
        "claim_job",
        lambda **kwargs: SimpleNamespace(claimed=True, job=job),
    )
    monkeypatch.setattr(parser_worker, "get_job", lambda job_id: job)
    monkeypatch.setattr(
        parser_worker,
        "update_job",
        lambda job_id, fields: calls.append(("job_update", job_id, fields)) or job,
    )


def _patch_parser_success(monkeypatch):
    monkeypatch.setattr(parser_worker, "download_file", lambda drive_file_id: b"%PDF")
    monkeypatch.setattr(
        parser_worker,
        "extract_text_from_pdf_bytes",
        lambda pdf: "resume text",
    )
    monkeypatch.setattr(
        parser_worker,
        "parse_resume",
        lambda text: {"skills": {"value": ["Python"]}, "locations": {"value": []}},
    )


def test_worker_executes_queued_job_and_finalizes_authoritative_parser_run(monkeypatch):
    calls = []
    job = _job()
    _patch_claimed_job(monkeypatch, job, calls)
    _patch_parser_success(monkeypatch)
    monkeypatch.setattr(
        parser_worker,
        "persist_parser_result_if_missing",
        lambda **kwargs: calls.append(("parser_result", kwargs)),
    )
    monkeypatch.setattr(
        parser_worker,
        "_add_resolver_output",
        lambda parsed, submission_id: parsed.update(
            {
                "resolver_version": "v1",
                "resolved_skill_ids": ["python"],
                "unknown_skills": [],
                "resolver_coverage": 1.0,
            }
        ),
    )
    monkeypatch.setattr(
        parser_worker,
        "persist_resolver_output_for_parser_result",
        lambda **kwargs: calls.append(("resolver", kwargs)),
    )

    assert _worker().run_once() == 1

    assert [name for name, *_ in calls] == [
        "job_update",
        "parser_result",
        "resolver",
        "job_update",
    ]
    assert calls[0][2]["parser_started_at"] != ""
    assert calls[1][1]["parser_run_id"] == "run-1"
    assert calls[-1][2]["status"] == "succeeded"
    assert calls[-1][2]["authoritative_parser_run_id"] == "run-1"


def test_worker_preserves_parser_success_when_resolver_fails(monkeypatch):
    calls = []
    job = _job()
    _patch_claimed_job(monkeypatch, job, calls)
    _patch_parser_success(monkeypatch)
    monkeypatch.setattr(
        parser_worker,
        "persist_parser_result_if_missing",
        lambda **kwargs: calls.append(("parser_result", kwargs)),
    )
    monkeypatch.setattr(
        parser_worker,
        "_add_resolver_output",
        lambda parsed, submission_id: (_ for _ in ()).throw(RuntimeError("resolver down")),
    )
    monkeypatch.setattr(
        parser_worker,
        "append_error_row",
        lambda **kwargs: calls.append(("error", kwargs)),
    )

    _worker().run_once()

    assert [name for name, *_ in calls] == [
        "job_update",
        "parser_result",
        "error",
        "job_update",
    ]
    assert calls[2][1]["stage"] == "resolver"
    assert calls[2][1]["parser_run_id"] == "run-1"
    assert calls[-1][2]["status"] == "succeeded"


def test_worker_schedules_retry_when_parser_fails(monkeypatch):
    calls = []
    job = _job()
    _patch_claimed_job(monkeypatch, job, calls)
    monkeypatch.setattr(parser_worker, "download_file", lambda drive_file_id: b"%PDF")
    monkeypatch.setattr(
        parser_worker,
        "extract_text_from_pdf_bytes",
        lambda pdf: "resume text",
    )
    monkeypatch.setattr(
        parser_worker,
        "parse_resume",
        lambda text: (_ for _ in ()).throw(RuntimeError("parser down")),
    )
    monkeypatch.setattr(
        parser_worker,
        "append_error_row",
        lambda **kwargs: calls.append(("error", kwargs)),
    )

    _worker().run_once()

    assert [name for name, *_ in calls] == ["job_update", "error", "job_update"]
    assert calls[1][1]["stage"] == "parser"
    assert calls[2][2]["status"] == "retry_scheduled"
    assert calls[2][2]["last_error_code"] == "PARSER_FAILED"


def test_worker_abandons_attempt_when_lease_is_lost_before_persistence(monkeypatch):
    calls = []
    job = _job()
    stale_job = _job(locked_by="worker-2")
    lease_checks = iter([job, stale_job])

    monkeypatch.setattr(parser_worker, "list_claimable_jobs", lambda limit: [job])
    monkeypatch.setattr(
        parser_worker,
        "claim_job",
        lambda **kwargs: SimpleNamespace(claimed=True, job=job),
    )
    monkeypatch.setattr(parser_worker, "get_job", lambda job_id: next(lease_checks))
    monkeypatch.setattr(parser_worker, "update_job", lambda job_id, fields: job)
    _patch_parser_success(monkeypatch)
    monkeypatch.setattr(
        parser_worker,
        "persist_parser_result_if_missing",
        lambda **kwargs: calls.append(("parser_result", kwargs)),
    )

    _worker().run_once()

    assert calls == []


def test_worker_abandons_before_resolver_when_newer_attempt_owns_job(monkeypatch):
    calls = []
    original_job = _job(last_parser_run_id="run-old")
    newer_job = _job(
        locked_by="worker-new",
        last_parser_run_id="run-new",
    )
    lease_checks = iter([original_job, original_job, original_job, newer_job])

    monkeypatch.setattr(parser_worker, "list_claimable_jobs", lambda limit: [original_job])
    monkeypatch.setattr(
        parser_worker,
        "claim_job",
        lambda **kwargs: SimpleNamespace(claimed=True, job=original_job),
    )
    monkeypatch.setattr(parser_worker, "get_job", lambda job_id: next(lease_checks))
    monkeypatch.setattr(
        parser_worker,
        "update_job",
        lambda job_id, fields: calls.append(("job_update", job_id, fields)) or original_job,
    )
    _patch_parser_success(monkeypatch)
    monkeypatch.setattr(
        parser_worker,
        "persist_parser_result_if_missing",
        lambda **kwargs: calls.append(("parser_result", kwargs)),
    )
    monkeypatch.setattr(
        parser_worker,
        "_add_resolver_output",
        lambda parsed, submission_id: calls.append(("resolver_run", parsed)),
    )
    monkeypatch.setattr(
        parser_worker,
        "persist_resolver_output_for_parser_result",
        lambda **kwargs: calls.append(("resolver_persist", kwargs)),
    )

    ParserWorker(
        ParserWorkerConfig(worker_id="worker-1", lease_seconds=900),
        parser_run_id_factory=lambda: "run-old",
    ).run_once()

    assert [name for name, *_ in calls] == ["job_update", "parser_result"]
    assert calls[1][1]["parser_run_id"] == "run-old"
    assert not any(
        call[0] == "job_update" and call[2].get("authoritative_parser_run_id")
        for call in calls
    )


def test_worker_retry_claim_receives_new_parser_run_id(monkeypatch):
    calls = []
    claim_run_ids = []
    run_ids = iter(["run-1", "run-2"])
    parse_calls = {"count": 0}
    current_job = _job(last_parser_run_id="run-1")

    def fake_claim_job(**kwargs):
        nonlocal current_job
        claim_run_ids.append(kwargs["parser_run_id"])
        current_job = _job(
            last_parser_run_id=kwargs["parser_run_id"],
            attempt_count=str(len(claim_run_ids)),
        )
        return SimpleNamespace(claimed=True, job=current_job)

    def fake_get_job(job_id):
        return current_job

    def fake_update_job(job_id, fields):
        current_job.update({key: str(value) for key, value in fields.items()})
        calls.append(("job_update", job_id, dict(fields)))
        return current_job

    def fake_parse_resume(text):
        parse_calls["count"] += 1
        if parse_calls["count"] == 1:
            raise RuntimeError("parser down")
        return {"skills": {"value": ["Python"]}, "locations": {"value": []}}

    monkeypatch.setattr(parser_worker, "list_claimable_jobs", lambda limit: [current_job])
    monkeypatch.setattr(parser_worker, "claim_job", fake_claim_job)
    monkeypatch.setattr(parser_worker, "get_job", fake_get_job)
    monkeypatch.setattr(parser_worker, "update_job", fake_update_job)
    monkeypatch.setattr(parser_worker, "download_file", lambda drive_file_id: b"%PDF")
    monkeypatch.setattr(
        parser_worker,
        "extract_text_from_pdf_bytes",
        lambda pdf: "resume text",
    )
    monkeypatch.setattr(parser_worker, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(
        parser_worker,
        "append_error_row",
        lambda **kwargs: calls.append(("error", kwargs)),
    )
    monkeypatch.setattr(
        parser_worker,
        "persist_parser_result_if_missing",
        lambda **kwargs: calls.append(("parser_result", kwargs)),
    )
    monkeypatch.setattr(parser_worker, "_add_resolver_output", lambda parsed, submission_id: None)
    monkeypatch.setattr(
        parser_worker,
        "persist_resolver_output_for_parser_result",
        lambda **kwargs: calls.append(("resolver", kwargs)),
    )

    worker = ParserWorker(
        ParserWorkerConfig(worker_id="worker-1", lease_seconds=900),
        parser_run_id_factory=lambda: next(run_ids),
    )

    assert worker.run_once() == 1
    assert worker.run_once() == 1

    assert claim_run_ids == ["run-1", "run-2"]
    assert claim_run_ids[0] != claim_run_ids[1]
    parser_result_calls = [call for call in calls if call[0] == "parser_result"]
    assert parser_result_calls[0][1]["parser_run_id"] == "run-2"
