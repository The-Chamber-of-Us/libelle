import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.ops_status_validation import (
    INVALID_OPS_STATUS_CODE,
    validate_incoming_ops_status,
)
from main import http_exception_handler
from ops_schema import VALID_OPS_STATUSES


@pytest.mark.parametrize("status", VALID_OPS_STATUSES)
def test_validate_incoming_ops_status_accepts_valid_contract_values(status: str) -> None:
    assert validate_incoming_ops_status(status) == status


@pytest.mark.parametrize(
    "status",
    [
        "pending",
        "NEW",
        "in progress",
        "paused ",
        "",
        None,
        123,
    ],
)
def test_validate_incoming_ops_status_rejects_invalid_values(status) -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_incoming_ops_status(status)

    exc = exc_info.value
    assert exc.status_code == 400
    assert exc.detail["code"] == INVALID_OPS_STATUS_CODE
    assert "Expected one of: new, reviewed, contacted, in_progress, paused, closed." in exc.detail[
        "message"
    ]


def test_validate_incoming_ops_status_returns_clear_400_response_before_write() -> None:
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)

    persisted_statuses: list[str] = []

    @app.post("/test-ops-status")
    def test_ops_status(payload: dict):
        status = validate_incoming_ops_status(payload.get("status"))
        persisted_statuses.append(status)
        return {"status": "success"}

    client = TestClient(app)

    response = client.post("/test-ops-status", json={"status": "pending"})

    assert response.status_code == 400
    assert response.json() == {
        "status": "error",
        "code": INVALID_OPS_STATUS_CODE,
        "message": "Invalid ops status. Expected one of: new, reviewed, contacted, in_progress, paused, closed.",
        "fields": {
            "status": "Must be one of the repo-owned ops workflow statuses.",
        },
    }
    assert persisted_statuses == []


def test_validate_incoming_ops_status_allows_write_path_to_continue_for_valid_status() -> None:
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)

    persisted_statuses: list[str] = []

    @app.post("/test-ops-status")
    def test_ops_status(payload: dict):
        status = validate_incoming_ops_status(payload.get("status"))
        persisted_statuses.append(status)
        return {"status": "success"}

    client = TestClient(app)

    response = client.post("/test-ops-status", json={"status": "contacted"})

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert persisted_statuses == ["contacted"]
