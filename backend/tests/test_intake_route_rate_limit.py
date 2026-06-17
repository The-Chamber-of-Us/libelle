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
            "resume_filename": "sub_001-resume.pdf",
            "resume_status": "uploaded",
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


def test_submission_without_resume_succeeds_without_parser_job(monkeypatch):
    captured = {"parsed": False}

    def fake_finalize(**kwargs):
        assert kwargs["pdf_bytes"] is None
        return {
            "submission_id": "sub_missing",
            "drive_file_id": "",
            "drive_file_url": "",
            "pre_text": "",
            "resume_filename": "",
            "resume_status": "missing",
        }

    monkeypatch.setattr(intake, "finalize_submission", fake_finalize)
    monkeypatch.setattr(
        intake,
        "parse_and_update",
        lambda *args: captured.update(parsed=True),
    )
    monkeypatch.setattr(
        intake,
        "intake_rate_limiter",
        InMemoryIntakeRateLimiter(
            enabled=False,
            per_ip_limit=0,
            per_email_limit=0,
            global_limit=0,
        ),
    )

    response = _client().post(
        "/api/upload",
        data={
            "full_name": "Test User",
            "email": "test@example.com",
            "location": "Remote",
            "interests": "Engineering",
            "availability": "Weekly",
            "experience_level": "Mid",
            "consent": "true",
        },
    )

    assert response.status_code == 200
    assert response.json()["submission_id"] == "sub_missing"
    assert response.json()["resume_status"] == "missing"
    assert response.json()["resume_filename"] == ""
    assert captured["parsed"] is False


def test_failed_resume_upload_succeeds_without_parser_job(monkeypatch):
    captured = {"parsed": False}

    monkeypatch.setattr(
        intake,
        "finalize_submission",
        lambda **_: {
            "submission_id": "sub_failed",
            "drive_file_id": "",
            "drive_file_url": "",
            "pre_text": "",
            "resume_filename": "",
            "resume_status": "failed",
        },
    )
    monkeypatch.setattr(
        intake,
        "parse_and_update",
        lambda *args: captured.update(parsed=True),
    )
    monkeypatch.setattr(
        intake,
        "intake_rate_limiter",
        InMemoryIntakeRateLimiter(
            enabled=False,
            per_ip_limit=0,
            per_email_limit=0,
            global_limit=0,
        ),
    )

    response = _upload(_client())

    assert response.status_code == 200
    assert response.json()["submission_id"] == "sub_failed"
    assert response.json()["resume_status"] == "failed"
    assert "resume upload failed" in response.json()["message"]
    assert captured["parsed"] is False
