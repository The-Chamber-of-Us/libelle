from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import intake
from services.rate_limit import InMemoryIntakeRateLimiter


PDF_BYTES = b"%PDF-1.4\nstub"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(intake.router)
    return TestClient(app)


def _upload(client: TestClient, email: str = "test@example.com"):
    return client.post(
        "/api/upload",
        data={
            "full_name": "Test User",
            "email": email,
            "location": "Remote",
            "interests": "Engineering",
            "availability": "Weekly",
            "experience_level": "Mid",
            "consent": "true",
        },
        files={"file": ("resume.pdf", PDF_BYTES, "application/pdf")},
    )


def test_rate_limited_request_returns_429_before_external_writes(monkeypatch):
    calls = {"finalize": 0}

    def fake_finalize(**kwargs):
        calls["finalize"] += 1
        return {
            "submission_id": "sub_001",
            "drive_file_id": "drive-file-id",
            "drive_file_url": "https://drive.example/resume",
            "pre_text": "resume text",
        }

    monkeypatch.setattr(intake, "finalize_submission", fake_finalize)
    monkeypatch.setattr(intake, "parse_and_update", lambda *args: None)
    monkeypatch.setattr(
        intake,
        "intake_rate_limiter",
        InMemoryIntakeRateLimiter(
            enabled=True,
            per_ip_limit=1,
            per_email_limit=10,
            global_limit=10,
            clock=lambda: 100.0,
        ),
    )

    client = _client()
    first = _upload(client, email="first@example.com")
    second = _upload(client, email="second@example.com")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "RATE_LIMITED"
    assert second.json()["scope"] == "ip"
    assert second.headers["retry-after"] == "60"
    assert calls["finalize"] == 1
