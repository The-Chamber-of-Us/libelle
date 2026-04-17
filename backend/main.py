import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import ALLOWED_ORIGINS, APP_REDIRECT_URI, MAX_PDF_MB
from services.intake_service import IntakeError, process_submission
from services.parser_service import parse_and_update
from storage.drive_repo import build_auth_url, exchange_code


app = FastAPI(title="Libelle Backend API")


if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


@app.on_event("startup")
def _startup_log():
    print("[STARTUP] Libelle backend booted")
    print(f"[STARTUP] MAX_PDF_MB={MAX_PDF_MB}")
    print(f"[STARTUP] ALLOWED_ORIGINS={ALLOWED_ORIGINS}")


# -----------------------------
# Error Handling (JSON only)
# -----------------------------
def _json_error(status_code: int, payload: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload)


def _intake_error_to_http(err: IntakeError) -> HTTPException:
    detail: Dict[str, Any] = {"status": "error", "code": err.code}
    if err.fields is not None:
        detail["fields"] = err.fields
    else:
        detail["message"] = err.message
    return HTTPException(status_code=err.status_code, detail=detail)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return _json_error(exc.status_code, exc.detail)
    return _json_error(
        exc.status_code,
        {"status": "error", "code": "HTTP_EXCEPTION", "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    fields: Dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc", [])
        msg = err.get("msg", "Invalid")
        if len(loc) >= 2:
            fields[str(loc[-1])] = msg
        else:
            fields["request"] = msg

    return _json_error(
        422,
        {"status": "error", "code": "VALIDATION_ERROR", "fields": fields or {"request": "Invalid request"}},
    )


# -----------------------------
# Endpoints
# -----------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "libelle-backend",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@app.get("/debug/config")
def debug_config():
    """
    Returns non-sensitive config to confirm your env is wired.
    Do NOT include secrets here.
    """
    from config import GOOGLE_OAUTH_CLIENT, TOKEN_FILE
    return {
        "status": "ok",
        "MAX_PDF_MB": MAX_PDF_MB,
        "ALLOWED_ORIGINS": ALLOWED_ORIGINS,
        "APP_REDIRECT_URI": APP_REDIRECT_URI,
        "has_google_oauth_client": bool(GOOGLE_OAUTH_CLIENT),
        "has_token_file": bool(TOKEN_FILE),
    }


@app.post("/api/upload")
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
        pdf_bytes = await file.read()
        result = process_submission(
            filename=file.filename,
            content_type=file.content_type,
            pdf_bytes=pdf_bytes,
            full_name=full_name,
            email=email,
            location=location,
            interests=interests,
            availability=availability,
            experience_level=experience_level,
            linkedin_url=linkedin_url,
            github_url=github_url,
            motivation=motivation,
            consent=consent,
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

    background_tasks.add_task(parse_and_update, result["drive_file_id"], result["pre_text"])

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "submission_id": result["submission_id"],
            "drive_file_url": result["drive_file_url"],
            "message": "Your application has been received",
        },
    )


# -----------------------------
# Optional OAuth endpoints
# -----------------------------
@app.get("/authorize")
def authorize():
    auth_url = build_auth_url(APP_REDIRECT_URI)
    return {"status": "ok", "auth_url": auth_url}


@app.get("/oauth2callback")
def oauth2callback(code: str):
    exchange_code(code, APP_REDIRECT_URI)
    return {"status": "success", "message": "Authorization complete. token.json saved."}
