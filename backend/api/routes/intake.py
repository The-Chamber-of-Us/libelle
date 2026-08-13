import traceback
from ipaddress import ip_address, ip_network
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from config import (
    ENABLE_INTAKE_RATE_LIMITING,
    INTAKE_RATE_LIMIT_GLOBAL_PER_MINUTE,
    INTAKE_RATE_LIMIT_PER_EMAIL_PER_HOUR,
    INTAKE_RATE_LIMIT_PER_IP_PER_MINUTE,
    INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS,
    INTAKE_TRUSTED_FORWARD_PROXY_CIDRS,
)
from services.intake_service import IntakeError, finalize_submission, validate_intake
from services.rate_limit import InMemoryIntakeRateLimiter
from services.parser_service import parse_and_update

router = APIRouter()
intake_rate_limiter = InMemoryIntakeRateLimiter(
    enabled=ENABLE_INTAKE_RATE_LIMITING,
    per_ip_limit=INTAKE_RATE_LIMIT_PER_IP_PER_MINUTE,
    per_email_limit=INTAKE_RATE_LIMIT_PER_EMAIL_PER_HOUR,
    global_limit=INTAKE_RATE_LIMIT_GLOBAL_PER_MINUTE,
)


def _is_ip_in_cidrs(value: Optional[str], cidrs: list[str]) -> bool:
    if not value:
        return False

    try:
        candidate = ip_address(value)
    except ValueError:
        return False

    for cidr in cidrs:
        try:
            if candidate in ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def _normalized_ip(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    try:
        return str(ip_address(value.strip()))
    except ValueError:
        return None


def _intake_error_to_http(err: IntakeError) -> HTTPException:
    detail: Dict[str, Any] = {"status": "error", "code": err.code}
    if err.fields is not None:
        detail["fields"] = err.fields
    else:
        detail["message"] = err.message
    return HTTPException(status_code=err.status_code, detail=detail)


def _client_ip(request: Request) -> str:
    socket_ip = request.client.host if request.client else None

    if _is_ip_in_cidrs(socket_ip, INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS):
        cf_ip = _normalized_ip(request.headers.get("cf-connecting-ip"))
        if cf_ip:
            return cf_ip

    if _is_ip_in_cidrs(socket_ip, INTAKE_TRUSTED_FORWARD_PROXY_CIDRS):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            forwarded_ip = _normalized_ip(forwarded_for.split(",", 1)[0])
            if forwarded_ip:
                return forwarded_ip

    return socket_ip or "unknown"


@router.post("/api/upload")
async def upload_volunteer_application(
    request: Request,
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
    try:
        normalized = validate_intake(
            filename=file.filename if file else None,
            content_type=file.content_type if file else None,
            full_name=full_name,
            email=email,
            location=location,
            interests=interests,
            availability=availability,
            experience_level=experience_level,
            consent=consent,
        )
        decision = intake_rate_limiter.check(
            ip_address=_client_ip(request),
            email=normalized.get("email"),
        )
        if not decision.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "code": "RATE_LIMITED",
                    "message": "Too many intake submissions. Please wait and try again.",
                    "scope": decision.scope,
                    "retry_after_seconds": decision.retry_after_seconds,
                },
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )
        pdf_bytes = await file.read() if file and file.filename else None
        result = finalize_submission(
            pdf_bytes=pdf_bytes,
            original_filename=file.filename if file and file.filename else None,
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

    if result["resume_status"] == "uploaded":
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
            "resume_filename": result["resume_filename"],
            "resume_status": result["resume_status"],
            "message": (
                "Your application was received, but the resume upload failed. "
                "Please keep your submission ID for follow-up."
                if result["resume_status"] == "failed"
                else "Your application has been received"
            ),
        },
    )
