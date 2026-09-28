from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.models.dashboard import ReviewerSubmissionSnapshot
from api.routes import dashboard
from core.coordination_lifecycle import (
    CoordinationIntent, apply_intent, read_coordination, retention_scope,
)
from services.dashboard_service import assemble_snapshot_records
from sheet_schema import build_row, get_headers
from storage import sheets_repo

NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)
ACTOR = {"cf-access-authenticated-user-email": "Reviewer@Example.Org"}


def intent(action="preserve", **fields):
    return CoordinationIntent(action=action, purpose="Coordinate an ongoing project",
                              context_reviewed=True, **fields)


def test_only_explicit_end_begins_clock_and_repeated_end_does_not_extend_it():
    active = apply_intent(None, intent(), "reviewer@example.org", NOW)
    edited = apply_intent(active, intent(takeaway="Follow up"), "reviewer@example.org", NOW + timedelta(days=1))
    assert edited.purpose_started_at == NOW
    ended = apply_intent(edited, intent("end"), "reviewer@example.org", NOW + timedelta(days=2))
    repeated = apply_intent(ended, intent("end"), "reviewer@example.org", NOW + timedelta(days=3))
    assert repeated.purpose_ended_at == ended.purpose_ended_at
    reopened = apply_intent(repeated, intent(), "reviewer@example.org", NOW + timedelta(days=4))
    assert reopened.purpose_ended_at is None
    assert reopened.purpose_started_at == NOW + timedelta(days=4)


@pytest.mark.parametrize("value", ["", "bad JSON", '{"state":"active"}'])
def test_source_expiry_never_cascades_current_coordination(value):
    assert retention_scope("source_expiry", value) == ("intake_evidence", "reviewer_history")
    assert set(retention_scope("volunteer_deletion", value)) == {
        "intake_evidence", "coordination_context", "reviewer_history"
    }


def test_coordination_expiry_requires_ended_purpose_and_approved_cutoff():
    active = apply_intent(None, intent(), "reviewer@example.org", NOW)
    ended = apply_intent(active, intent("end"), "reviewer@example.org", NOW + timedelta(days=1))
    assert retention_scope("coordination_expiry", active.model_dump_json(), approved_coordination_cutoff=NOW + timedelta(days=99)) == ()
    assert retention_scope("coordination_expiry", ended.model_dump_json()) == ()
    assert retention_scope("coordination_expiry", ended.model_dump_json(), approved_coordination_cutoff=NOW) == ()
    assert retention_scope("coordination_expiry", ended.model_dump_json(), approved_coordination_cutoff=NOW + timedelta(days=1)) == ("coordination_context", "reviewer_history")
    with pytest.raises(ValueError):
        retention_scope("coordination_expiry", "bad JSON", approved_coordination_cutoff=NOW)


def test_invalid_intent_and_forged_timestamps_rejected():
    with pytest.raises(ValueError):
        CoordinationIntent(action="preserve", purpose=" ", context_reviewed=True)
    with pytest.raises(ValueError):
        CoordinationIntent(action="preserve", purpose="Coordination", context_reviewed=False)
    with pytest.raises(ValueError):
        CoordinationIntent(action="preserve", purpose="Coordination", context_reviewed=True, purpose_ended_at=NOW)
    with pytest.raises(ValueError):
        apply_intent(None, intent("end"), "reviewer@example.org", NOW)


@pytest.mark.parametrize("stored,quality", [("", "unassessed"), ("broken", "malformed"), (None, "active")])
def test_coordination_survives_source_removal_without_exposing_leftover_evidence(stored, quality):
    record = apply_intent(None, intent(takeaway="Schedule a conversation"), "reviewer@example.org", NOW)
    row = {"submission_id": "s1", "status": "paused", "notes": "Call next week",
           "coordination": record.model_dump_json() if stored is None else stored}
    evidence = {"submission_id": "s1", "parsed_skills_raw": "secret", "error_summary": "secret", "drive_file_id": "secret"}
    result = assemble_snapshot_records({}, [evidence], [row], [evidence], [evidence])[0]
    ReviewerSubmissionSnapshot.model_validate(result)
    assert result["source_state"] == "unavailable"
    assert result["coordination_state"] == quality
    assert result["submission_health_state"] == "coordination_only"
    assert result["ops"]["notes"] == "Call next week"
    assert result["parser_job"] is None
    assert all(v == "" for v in result["raw"].values())
    assert "secret" not in str(result)
    assert result["parsed"]["parser_result_state"] == "source_unavailable"
    if stored is None:
        assert result["coordination"]["takeaway"] == "Schedule a conversation"


def test_same_email_does_not_merge_roots():
    rows = assemble_snapshot_records({"a": {"email": "same@example.org"}, "b": {"email": "same@example.org"}}, [], [], [])
    assert [r["submission_id"] for r in rows] == ["a", "b"]


class Request:
    def __init__(self, value=None):
        self.value = value or {}

    def execute(self):
        return self.value


class Sheet:
    def __init__(self, rows):
        self.rows = rows
        self.writes = []

    def values(self):
        return self

    def get(self, **kwargs):
        return Request({"values": self.rows})

    def update(self, **kwargs):
        self.writes.append(kwargs)
        self.rows = kwargs["body"]["values"]
        return Request()

    def append(self, **kwargs):
        self.writes.append(kwargs)
        self.rows += kwargs["body"]["values"]
        return Request()


def sheet_fixture(monkeypatch, rows):
    sheet = Sheet(rows)
    monkeypatch.setattr(sheets_repo, "_get_sheet", lambda: sheet)
    monkeypatch.setattr(sheets_repo, "append_ops_event_rows", lambda **kw: None)
    return sheet


def test_workflow_edits_preserve_lifecycle_and_can_update_without_intake(monkeypatch):
    active = apply_intent(None, intent(), "reviewer@example.org", NOW)
    ended = apply_intent(active, intent("end"), "reviewer@example.org", NOW)
    sheet = sheet_fixture(monkeypatch, [build_row("ops", {"submission_id": "s1", "status": "paused", "coordination": ended.model_dump_json()})])
    from services.ops_write_service import update_or_create_ops_workflow_state
    monkeypatch.setattr(sheets_repo, "load_submission_records", lambda: pytest.fail("Existing ops must not require intake"))
    update_or_create_ops_workflow_state("s1", {"status": "in_progress", "notes": "Changed", "updated_by": "reviewer@example.org"})
    saved = dict(zip(get_headers("ops"), sheet.rows[0]))
    assert saved["coordination"] == ended.model_dump_json()


def test_intent_route_uses_actor_and_persists_first_state(monkeypatch):
    sheet = sheet_fixture(monkeypatch, [])
    monkeypatch.setattr(sheets_repo, "load_submission_records", lambda: {"s1": {}})
    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)
    response = client.post("/submissions/s1/coordination", json=intent().model_dump(mode="json"), headers=ACTOR)
    assert response.status_code == 200
    assert response.json()["decided_by"] == "reviewer@example.org"
    saved = dict(zip(get_headers("ops"), sheet.rows[0]))
    assert read_coordination(saved["coordination"]).state == "active"
    assert saved["status"] == "new"


@pytest.mark.parametrize("rows", [[], [build_row("ops", {"submission_id": "s1", "coordination": "broken"})], [build_row("ops", {"submission_id": "s1"})] * 2])
def test_unknown_malformed_or_duplicate_roots_do_not_write(monkeypatch, rows):
    sheet = sheet_fixture(monkeypatch, rows)
    monkeypatch.setattr(sheets_repo, "load_submission_records", lambda: {})
    app = FastAPI()
    app.include_router(dashboard.router)
    response = TestClient(app).post("/submissions/s1/coordination", json=intent().model_dump(mode="json"), headers=ACTOR)
    assert response.status_code == 409
    assert sheet.writes == []


def test_duplicate_ops_never_projects_a_valid_lifecycle():
    active = apply_intent(None, intent(), "reviewer@example.org", NOW)
    row = {"submission_id": "s1", "coordination": active.model_dump_json()}
    result = assemble_snapshot_records({}, [], [row, row], [])[0]
    assert result["coordination_state"] == "malformed"
    assert result["coordination"] is None


def test_first_preserve_never_copies_intake_into_coordination(monkeypatch):
    sheet = sheet_fixture(monkeypatch, [])
    monkeypatch.setattr(sheets_repo, "load_submission_records", lambda: {
        "s1": {"full_name": "Source name", "email": "source@example.org", "skills_raw": "Source skills"}
    })
    sheets_repo.set_coordination_intent("s1", intent(), "reviewer@example.org")
    assert "Source name" not in str(sheet.rows)
    assert "source@example.org" not in str(sheet.rows)
    assert "Source skills" not in str(sheet.rows)
