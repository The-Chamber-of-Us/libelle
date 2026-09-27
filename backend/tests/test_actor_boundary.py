"""All actor-protected routes reject untrusted identity before service work."""
import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import dashboard, resumes

_payload = base64.urlsafe_b64encode(json.dumps({"email": "forged@example.org"}).encode()).decode().rstrip("=")
_forged_jwt = f"header.{_payload}.signature"


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/ops/update", {"submission_id": "sub_001", "notes": "test"}),
    ("POST", "/submissions/sub_001/ops", {"status": "new"}),
    ("PATCH", "/submissions/sub_001/ops", {"notes": "test"}),
    ("GET", "/resumes/sub_001", None),
])
@pytest.mark.parametrize("headers", [
    {},
    {"cf-access-jwt-assertion": _forged_jwt},
    {"cf-access-authenticated-user-email": "not-an-email", "cf-access-jwt-assertion": _forged_jwt},
    {"cf-access-authenticated-user-email": " "},
])
def test_invalid_identity_never_reaches_service(monkeypatch, method, path, body, headers):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid identity reached protected service")

    for name in ["create_first_ops_workflow_state", "update_existing_ops_workflow_state", "update_or_create_ops_workflow_state"]:
        monkeypatch.setattr(dashboard, name, unexpected)
    monkeypatch.setattr(resumes, "get_mediated_resume", unexpected)
    app = FastAPI()
    app.include_router(dashboard.router)
    app.include_router(resumes.router)
    response = TestClient(app).request(method, path, json=body, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INTERNAL_ACTOR_REQUIRED"
