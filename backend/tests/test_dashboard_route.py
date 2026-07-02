from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.models.dashboard import ReviewerSubmissionSnapshot
from api.routes import dashboard
from ops_schema import VALID_OPS_STATUSES

ACTOR_HEADERS = {"cf-access-authenticated-user-email": "Reviewer@Example.Org"}


def _snapshot_payload() -> list[dict]:
    return [
        {
            "submission_id": "sub_001",
            "submission_health_state": "pending_processing",
            "raw": {
                "created_at": "2026-04-19T10:00:00",
                "full_name": "First Person",
                "email": "first@example.org",
                "location_raw": "Raleigh, NC",
                "timezone": "",
                "skills_raw": "Python",
                "interests": "Engineering",
                "experience_level": "Senior",
                "availability": "6 hours",
                "motivation": "",
                "linkedin_url": "",
                "github_url": "",
                "consent_given": "TRUE",
                "resume_filename": "sub_001-resume.pdf",
                "resume_status": "uploaded",
            },
            "parsed": {
                "parser_state": "pending",
                "parser_run_id": "",
                "created_at": "",
                "parser_version": "",
                "parsed_skills_raw": "",
                "parsed_location_raw": "",
                "parser_confidence": "",
            },
            "resolved": {
                "resolver_state": "not_run",
                "resolver_version": "",
                "aliases_version": "",
                "resolved_skill_ids": "",
                "unknown_skills": "",
                "resolver_coverage": "",
            },
            "ops": {
                "status": "new",
                "notes": "",
                "tags": "",
                "contact_tracking": "",
                "updated_at": "",
                "updated_by": "",
            },
            "errors": {
                "has_error": False,
                "latest_error_summary": "",
                "latest_error_stage": "",
                "latest_error_code": "",
            },
        }
    ]


def test_get_snapshot_declares_reviewer_snapshot_response_model() -> None:
    route = next(route for route in dashboard.router.routes if route.path == "/snapshot")

    assert route.response_model == list[ReviewerSubmissionSnapshot]


def test_get_snapshot_returns_typed_dashboard_service_payload(monkeypatch) -> None:
    payload = _snapshot_payload()

    monkeypatch.setattr(dashboard, "get_snapshot_records", lambda: payload)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.get("/snapshot")

    assert response.status_code == 200
    assert response.json() == payload


def test_get_snapshot_response_model_rejects_missing_required_fields(monkeypatch) -> None:
    payload = [
        {
            "submission_id": "sub_001",
            "raw": {"full_name": "First Person"},
            "parsed": {"parser_state": "pending"},
            "resolved": {"resolver_state": "not_run"},
            "ops": {"status": "new"},
            "errors": {"has_error": False},
        }
    ]

    monkeypatch.setattr(dashboard, "get_snapshot_records", lambda: payload)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/snapshot")

    assert response.status_code == 500


def test_create_ops_workflow_state_creates_first_ops_row(monkeypatch) -> None:
    created_row = {
        "submission_id": "sub_001",
        "status": "contacted",
        "notes": "Left voicemail",
        "tags": "priority",
        "contact_tracking": "call",
        "updated_at": "05-26-2026 10:00:00 UTC",
        "updated_by": "reviewer@example.org",
    }

    captured = {}

    def fake_create(submission_id, workflow_fields):
        captured["submission_id"] = submission_id
        captured["workflow_fields"] = workflow_fields
        return created_row

    monkeypatch.setattr(dashboard, "create_first_ops_workflow_state", fake_create)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/submissions/sub_001/ops",
        headers=ACTOR_HEADERS,
        json={
            "status": "contacted",
            "notes": "Left voicemail",
            "tags": "priority",
            "contact_tracking": "call",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "status": "created",
        "submission_id": "sub_001",
        "ops": {
            "status": "contacted",
            "notes": "Left voicemail",
            "tags": "priority",
            "contact_tracking": "call",
            "updated_at": "05-26-2026 10:00:00 UTC",
            "updated_by": "reviewer@example.org",
        },
    }
    assert captured == {
        "submission_id": "sub_001",
        "workflow_fields": {
            "status": "contacted",
            "notes": "Left voicemail",
            "tags": "priority",
            "contact_tracking": "call",
            "updated_by": "reviewer@example.org",
        },
    }


def test_create_ops_workflow_state_does_not_update_existing_ops_row(monkeypatch) -> None:
    monkeypatch.setattr(dashboard, "create_first_ops_workflow_state", lambda *args: None)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/submissions/sub_001/ops",
        headers=ACTOR_HEADERS,
        json={
            "status": "reviewed",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "already_exists",
        "submission_id": "sub_001",
        "ops": None,
    }


def test_create_ops_workflow_state_rejects_invalid_status_before_write(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dashboard, "create_first_ops_workflow_state", lambda *args: calls.append(args))

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/submissions/sub_001/ops",
        headers=ACTOR_HEADERS,
        json={
            "status": "pending",
        },
    )

    assert response.status_code == 400
    assert calls == []


def test_update_ops_workflow_state_updates_existing_ops_row(monkeypatch) -> None:
    updated_row = {
        "submission_id": "sub_001",
        "status": "reviewed",
        "notes": "Updated note",
        "tags": "priority",
        "contact_tracking": "call",
        "updated_at": "05-26-2026 10:00:00 UTC",
        "updated_by": "reviewer@example.org",
    }
    captured = {}

    def fake_update(submission_id, workflow_fields):
        captured["submission_id"] = submission_id
        captured["workflow_fields"] = workflow_fields
        return updated_row

    monkeypatch.setattr(dashboard, "update_existing_ops_workflow_state", fake_update)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.patch(
        "/submissions/sub_001/ops",
        headers=ACTOR_HEADERS,
        json={
            "status": "reviewed",
            "notes": "Updated note",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "updated",
        "submission_id": "sub_001",
        "ops": {
            "status": "reviewed",
            "notes": "Updated note",
            "tags": "priority",
            "contact_tracking": "call",
            "updated_at": "05-26-2026 10:00:00 UTC",
            "updated_by": "reviewer@example.org",
        },
    }
    assert captured == {
        "submission_id": "sub_001",
        "workflow_fields": {
            "updated_by": "reviewer@example.org",
            "status": "reviewed",
            "notes": "Updated note",
        },
    }


def test_update_ops_workflow_state_does_not_create_missing_ops_row(monkeypatch) -> None:
    monkeypatch.setattr(dashboard, "update_existing_ops_workflow_state", lambda *args: None)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.patch(
        "/submissions/sub_001/ops",
        headers=ACTOR_HEADERS,
        json={
            "status": "reviewed",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "OPS_ROW_NOT_FOUND"


def test_update_ops_workflow_state_rejects_invalid_status_before_write(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dashboard, "update_existing_ops_workflow_state", lambda *args: calls.append(args))

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.patch(
        "/submissions/sub_001/ops",
        headers=ACTOR_HEADERS,
        json={
            "status": "pending",
        },
    )

    assert response.status_code == 400
    assert calls == []


def test_update_ops_dashboard_state_accepts_structured_status_update(monkeypatch) -> None:
    updated_row = {
        "submission_id": "sub_001",
        "status": "reviewed",
        "notes": "Original note",
        "tags": "priority",
        "contact_tracking": "call",
        "updated_at": "05-26-2026 10:00:00 UTC",
        "updated_by": "reviewer@example.org",
    }
    captured = {}

    def fake_update(submission_id, workflow_fields):
        captured["submission_id"] = submission_id
        captured["workflow_fields"] = workflow_fields
        return updated_row

    monkeypatch.setattr(dashboard, "update_or_create_ops_workflow_state", fake_update)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/ops/update",
        headers=ACTOR_HEADERS,
        json={
            "submission_id": "sub_001",
            "status": "reviewed",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "updated",
        "submission_id": "sub_001",
        "ops": {
            "status": "reviewed",
            "notes": "Original note",
            "tags": "priority",
            "contact_tracking": "call",
            "updated_at": "05-26-2026 10:00:00 UTC",
            "updated_by": "reviewer@example.org",
        },
    }
    assert captured == {
        "submission_id": "sub_001",
        "workflow_fields": {
            "updated_by": "reviewer@example.org",
            "status": "reviewed",
        },
    }


def test_get_ops_statuses_returns_repo_owned_status_list() -> None:
    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.get("/ops/statuses")

    assert response.status_code == 200
    assert response.json() == {"statuses": list(VALID_OPS_STATUSES)}


def test_update_ops_dashboard_state_accepts_structured_notes_update(monkeypatch) -> None:
    updated_row = {
        "submission_id": "sub_001",
        "status": "contacted",
        "notes": "Updated note only",
        "tags": "priority",
        "contact_tracking": "call",
        "updated_at": "05-26-2026 10:00:00 UTC",
        "updated_by": "reviewer@example.org",
    }
    captured = {}

    def fake_update(submission_id, workflow_fields):
        captured["submission_id"] = submission_id
        captured["workflow_fields"] = workflow_fields
        return updated_row

    monkeypatch.setattr(dashboard, "update_or_create_ops_workflow_state", fake_update)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/ops/update",
        headers=ACTOR_HEADERS,
        json={
            "submission_id": "sub_001",
            "notes": "Updated note only",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "submission_id": "sub_001",
        "workflow_fields": {
            "updated_by": "reviewer@example.org",
            "notes": "Updated note only",
        },
    }


def test_update_ops_dashboard_state_rejects_missing_mutable_fields(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dashboard, "update_or_create_ops_workflow_state", lambda *args: calls.append(args))

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/ops/update",
        headers=ACTOR_HEADERS,
        json={
            "submission_id": "sub_001",
        },
    )

    assert response.status_code == 422
    assert calls == []


def test_update_ops_dashboard_state_rejects_invalid_status_before_write(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dashboard, "update_or_create_ops_workflow_state", lambda *args: calls.append(args))

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/ops/update",
        headers=ACTOR_HEADERS,
        json={
            "submission_id": "sub_001",
            "status": "pending",
        },
    )

    assert response.status_code == 400
    assert calls == []


def test_update_ops_dashboard_state_rejects_missing_actor_identity(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dashboard, "update_or_create_ops_workflow_state", lambda *args: calls.append(args))

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/ops/update",
        json={
            "submission_id": "sub_001",
            "notes": "Updated note",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "status": "error",
        "code": "INTERNAL_ACTOR_REQUIRED",
        "message": "Authenticated internal actor identity is required.",
    }
    assert calls == []


def test_update_ops_dashboard_state_does_not_trust_client_actor_fields(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dashboard, "update_or_create_ops_workflow_state", lambda *args: calls.append(args))

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/ops/update",
        headers=ACTOR_HEADERS,
        json={
            "submission_id": "sub_001",
            "notes": "Updated note",
            "updated_by": "reviewer@example.org",
        },
    )

    assert response.status_code == 422
    assert calls == []


def test_update_ops_dashboard_state_creates_missing_ops_row(monkeypatch) -> None:
    created_row = {
        "submission_id": "sub_001",
        "status": "new",
        "notes": "Updated note",
        "tags": "",
        "contact_tracking": "",
        "updated_at": "05-26-2026 10:00:00 UTC",
        "updated_by": "reviewer@example.org",
    }
    captured = {}

    def fake_upsert(submission_id, workflow_fields):
        captured["submission_id"] = submission_id
        captured["workflow_fields"] = workflow_fields
        return created_row

    monkeypatch.setattr(dashboard, "update_or_create_ops_workflow_state", fake_upsert)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/ops/update",
        headers=ACTOR_HEADERS,
        json={
            "submission_id": "sub_001",
            "notes": "Updated note",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "updated",
        "submission_id": "sub_001",
        "ops": {
            "status": "new",
            "notes": "Updated note",
            "tags": "",
            "contact_tracking": "",
            "updated_at": "05-26-2026 10:00:00 UTC",
            "updated_by": "reviewer@example.org",
        },
    }
    assert captured == {
        "submission_id": "sub_001",
        "workflow_fields": {
            "updated_by": "reviewer@example.org",
            "notes": "Updated note",
        },
    }


def test_update_ops_dashboard_state_returns_not_found_for_unknown_submission(monkeypatch) -> None:
    def fake_upsert(*args):
        raise dashboard.OpsSubmissionNotFoundError("No submission found for submission_id.")

    monkeypatch.setattr(dashboard, "update_or_create_ops_workflow_state", fake_upsert)

    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)

    response = client.post(
        "/ops/update",
        headers=ACTOR_HEADERS,
        json={
            "submission_id": "sub_404",
            "notes": "Updated note",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "status": "error",
        "code": "SUBMISSION_NOT_FOUND",
        "message": "No submission found for submission_id.",
    }
