import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from services.intake_service import IntakeError, finalize_submission, validate_intake
from services.parser_service import parse_and_update

router = APIRouter()


def _intake_error_to_http(err: IntakeError) -> HTTPException:
    detail: Dict[str, Any] = {"status": "error", "code": err.code}
    if err.fields is not None:
        detail["fields"] = err.fields
    else:
        detail["message"] = err.message
    return HTTPException(status_code=err.status_code, detail=detail)


@router.post("/api/upload")
async def upload_volunteer_application(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    full_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    interests: Optional[str] = Form(None),
    availability: Optional[str] = Form(None),
    experience_level: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    github_url: Optional[str] = Form(None),
    motivation: Optional[str] = Form(None),
    consent: Optional[bool] = Form(None),
):
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "code": "FILE_REQUIRED",
                "message": "A resume file is required to complete this submission.",
            },
        )

    try:
        normalized = validate_intake(
            filename=file.filename,
            content_type=file.content_type,
            full_name=full_name,
            email=email,
            location=location,
            interests=interests,
            availability=availability,
            experience_level=experience_level,
            consent=consent,
        )
        pdf_bytes = await file.read()
        result = finalize_submission(
            pdf_bytes=pdf_bytes,
            normalized=normalized,
            linkedin_url=linkedin_url,
            github_url=github_url,
            motivation=motivation,
        )
    except IntakeError as e:
        raise _intake_error_to_http(e)
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "code": "PROCESSING_FAILED",
                "message": "We hit a snag while processing your submission. Please try again or reach out to support.",
            },
        )

    background_tasks.add_task(
        parse_and_update,
        result["submission_id"],
        result["drive_file_id"],
        result["pre_text"],
    )

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "submission_id": result["submission_id"],
            "drive_file_url": result["drive_file_url"],
            "message": "Your application has been received",
        },
    )
