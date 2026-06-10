from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from api.internal_actor import require_internal_actor
from services.resume_access_service import ResumeAccessError, get_mediated_resume

router = APIRouter()


@router.get("/resumes/{submission_id}")
def get_resume(submission_id: str, request: Request):
    actor = require_internal_actor(request)

    try:
        resume = get_mediated_resume(submission_id, actor)
    except ResumeAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())

    quoted_filename = quote(resume.filename)
    return Response(
        content=resume.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quoted_filename}",
            "X-Submission-Id": resume.submission_id,
        },
    )
