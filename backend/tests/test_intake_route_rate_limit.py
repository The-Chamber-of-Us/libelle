from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.datastructures import Headers
from starlette.requests import HTTPConnection

from api.routes import intake
from services import intake_service
from services.rate_limit import InMemoryIntakeRateLimiter


def _pdf_bytes() -> bytes:
    import fitz

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "resume")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


PDF_BYTES = _pdf_bytes()


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


def _request_with_client(host: str, headers: dict[str, str]) -> HTTPConnection:
    return HTTPConnection(
        {
            "type": "http",
            "headers": Headers(headers).raw,
            "client": (host, 12345),
        }
    )


def test_client_ip_ignores_forwarded_headers_from_untrusted_socket(monkeypatch):
    monkeypatch.setattr(intake, "INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS", [])
    monkeypatch.setattr(intake, "INTAKE_TRUSTED_FORWARD_PROXY_CIDRS", [])

    request = _request_with_client(
        "198.51.100.10",
        {
            "cf-connecting-ip": "203.0.113.77",
            "x-forwarded-for": "203.0.113.88",
        },
    )

    assert intake._client_ip(request) == "198.51.100.10"


def test_client_ip_prefers_cloudflare_header_from_trusted_cloudflare_boundary(monkeypatch):
    monkeypatch.setattr(intake, "INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS", ["127.0.0.1/32"])
    monkeypatch.setattr(intake, "INTAKE_TRUSTED_FORWARD_PROXY_CIDRS", ["127.0.0.1/32"])

    request = _request_with_client(
        "127.0.0.1",
        {
            "cf-connecting-ip": "203.0.113.77",
            "x-forwarded-for": "198.51.100.99",
        },
    )

    assert intake._client_ip(request) == "203.0.113.77"


def test_client_ip_uses_forwarded_for_only_from_trusted_forward_proxy(monkeypatch):
    monkeypatch.setattr(intake, "INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS", [])
    monkeypatch.setattr(intake, "INTAKE_TRUSTED_FORWARD_PROXY_CIDRS", ["10.0.0.0/8"])

    trusted_request = _request_with_client(
        "10.1.2.3",
        {"x-forwarded-for": "203.0.113.88, 10.1.2.3"},
    )
    untrusted_request = _request_with_client(
        "198.51.100.10",
        {"x-forwarded-for": "203.0.113.88, 198.51.100.10"},
    )

    assert intake._client_ip(trusted_request) == "203.0.113.88"
    assert intake._client_ip(untrusted_request) == "198.51.100.10"


def test_client_ip_falls_back_to_socket_when_trusted_header_is_invalid(monkeypatch):
    monkeypatch.setattr(intake, "INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS", ["127.0.0.1/32"])
    monkeypatch.setattr(intake, "INTAKE_TRUSTED_FORWARD_PROXY_CIDRS", ["127.0.0.1/32"])

    request = _request_with_client(
        "127.0.0.1",
        {
            "cf-connecting-ip": "not-an-ip",
            "x-forwarded-for": "also-not-an-ip",
        },
    )

    assert intake._client_ip(request) == "127.0.0.1"


def test_rate_limited_request_returns_429_before_external_writes(monkeypatch):
    calls = {"finalize": 0}

    def fake_finalize(**kwargs):
        calls["finalize"] += 1
        return {
            "submission_id": "sub_001",
            "drive_file_id": "drive-file-id",
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


def test_invalid_resume_is_rejected_before_drive_or_parser(monkeypatch):
    captured = {"drive": False, "parsed": False, "row": False}

    monkeypatch.setattr(
        intake_service,
        "upload_pdf",
        lambda *_: captured.update(drive=True),
    )
    monkeypatch.setattr(
        intake_service,
        "write_base_row",
        lambda **_: captured.update(row=True),
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
        files={"file": ("resume.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_PDF"
    assert captured == {"drive": False, "parsed": False, "row": False}


def test_empty_present_upload_is_rejected(monkeypatch):
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
        files={"file": ("resume.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "EMPTY_FILE"
