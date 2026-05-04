from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import dashboard


def test_get_snapshot_returns_dashboard_service_payload(monkeypatch) -> None:
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
    client = TestClient(app)

    response = client.get("/snapshot")

    assert response.status_code == 200
    assert response.json() == payload
