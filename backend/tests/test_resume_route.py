from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import resumes
from services.resume_access_service import MediatedResume, ResumeAccessError

ACTOR_HEADERS = {"cf-access-authenticated-user-email": "Reviewer@Example.Org"}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(resumes.router)
    return TestClient(app)


def test_get_resume_requires_internal_actor_before_service_lookup(monkeypatch) -> None:
    def fail_if_called(submission_id, actor):
        raise AssertionError("resume service must not run without internal actor identity")

    monkeypatch.setattr(resumes, "get_mediated_resume", fail_if_called)

    response = _client().get("/resumes/sub_001")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INTERNAL_ACTOR_REQUIRED"


def test_get_resume_proxies_pdf_for_authenticated_actor(monkeypatch) -> None:
    captured = {}

    def fake_get_mediated_resume(submission_id, actor):
        captured["submission_id"] = submission_id
        captured["actor"] = actor
        return MediatedResume(
            submission_id="sub_001",
            filename="sub_001-resume.pdf",
            content=b"%PDF test",
        )

    monkeypatch.setattr(resumes, "get_mediated_resume", fake_get_mediated_resume)

    response = _client().get("/resumes/sub_001", headers=ACTOR_HEADERS)

    assert response.status_code == 200
    assert response.content == b"%PDF test"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-submission-id"] == "sub_001"
    assert response.headers["content-disposition"] == "inline; filename*=UTF-8''sub_001-resume.pdf"
    assert captured == {
        "submission_id": "sub_001",
        "actor": "reviewer@example.org",
    }


def test_get_resume_maps_service_errors(monkeypatch) -> None:
    def fake_get_mediated_resume(submission_id, actor):
        raise ResumeAccessError(
            status_code=404,
            code="RESUME_NOT_AVAILABLE",
            message="No uploaded resume is available for this submission.",
        )

    monkeypatch.setattr(resumes, "get_mediated_resume", fake_get_mediated_resume)

    response = _client().get("/resumes/sub_001", headers=ACTOR_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "status": "error",
        "code": "RESUME_NOT_AVAILABLE",
        "message": "No uploaded resume is available for this submission.",
    }
