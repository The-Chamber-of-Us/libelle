from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from typing import Optional, Dict, Any, List, Union
import fitz
import traceback
import os
import json
import uuid
import re
from datetime import datetime, timezone

from parser import parse_resume
from sheets_sync import write_base_row, update_resume_in_sheet
from drive_sync import get_target_folder_id, upload_pdf
from google_auth_oauthlib.flow import Flow


app = FastAPI(title="Libelle Backend API")

# -----------------------------
# Env + Config
# -----------------------------
MAX_PDF_MB = int(os.getenv("MAX_PDF_MB", "5"))
ALLOWED_PDF_MIMES = {"application/pdf", "application/x-pdf"}
APP_REDIRECT_URI = os.getenv("APP_REDIRECT_URI", "http://127.0.0.1:8000/oauth2callback")

_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]

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
# Helpers
# -----------------------------
EMAIL_IN_TEXT_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _is_placeholder_email(value: str) -> bool:
    if not value:
        return True
    v = value.strip().lower()
    return v in {"string", "email", "example", "test", "none", "null", "undefined", "-"}


def _validate_email(email: str) -> bool:
    if not email or _is_placeholder_email(email):
        return False
    return EMAIL_IN_TEXT_RE.search(email.strip()) is not None


def _normalize_email(email: str) -> str:
    if not email:
        return ""
    m = EMAIL_IN_TEXT_RE.search(email.strip())
    return m.group(0) if m else email.strip()


def _parse_interests(raw: Union[str, List[str], None]) -> str:
    if raw is None:
        return ""

    if isinstance(raw, list):
        return ", ".join([str(x).strip() for x in raw if str(x).strip()])

    s = str(raw).strip()
    if not s:
        return ""

    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return ", ".join([str(x).strip() for x in arr if str(x).strip()])
        except Exception:
            pass

    parts = [p.strip() for p in s.split(",") if p.strip()]
    return ", ".join(parts) if parts else s


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join([p.get_text("text") for p in doc])
        doc.close()
        return text
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "code": "PDF_PARSE_FAILED", "message": "PDF parsing failed"},
        )


def _make_resume_id() -> int:
    """
    Safer than a global counter: unique-ish and monotonic in practice.
    """
    return int(datetime.now(timezone.utc).timestamp() * 1000)


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
    return {
        "status": "ok",
        "MAX_PDF_MB": MAX_PDF_MB,
        "ALLOWED_ORIGINS": ALLOWED_ORIGINS,
        "has_google_oauth_client": bool(os.getenv("GOOGLE_OAUTH_CLIENT")),
        "has_token_file": bool(os.getenv("TOKEN_FILE")),
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
    # 1) Missing file -> 400 FILE_REQUIRED
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "code": "FILE_REQUIRED",
                "message": "A resume file is required to complete this submission.",
            },
        )

    # 2) Validate required fields (INCLUDING email; no PDF fallback)
    fields: Dict[str, str] = {}

    if not full_name or not full_name.strip():
        fields["full_name"] = "Required"

    normalized_email = _normalize_email(email or "")
    if not _validate_email(normalized_email):
        fields["email"] = "Required and must be a valid email address"

    if not location or not location.strip():
        fields["location"] = "Required"

    normalized_interests = _parse_interests(interests)
    if not normalized_interests.strip():
        fields["interests"] = "Required"

    if not availability or not availability.strip():
        fields["availability"] = "Required"

    if not experience_level or not experience_level.strip():
        fields["experience_level"] = "Required"

    if consent is not True:
        fields["consent"] = "Must be true to submit"

    if fields:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "code": "VALIDATION_ERROR", "fields": fields},
        )

    # 3) File validation
    if file.content_type not in ALLOWED_PDF_MIMES and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "code": "INVALID_FILE_TYPE", "message": "Only PDF files supported"},
        )

    submission_id = str(uuid.uuid4())[:8]
    resume_id = _make_resume_id()

    try:
        pdf_bytes = await file.read()

        if len(pdf_bytes) > MAX_PDF_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "code": "FILE_TOO_LARGE", "message": f"PDF too large (>{MAX_PDF_MB}MB)"},
            )

        # 4) Extract text once (needed for parsing)
        pre_text = _extract_text_from_pdf(pdf_bytes)
        if not pre_text.strip():
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "code": "NO_TEXT_EXTRACTED", "message": "PDF has no extractable text"},
            )

        # 5) Upload to Drive
        print(f"[UPLOAD] submission_id={submission_id} resume_id={resume_id} uploading to Drive...")
        folder_id = get_target_folder_id()
        drive_file_id, drive_file_url = upload_pdf(pdf_bytes, f"{submission_id}-resume.pdf", folder_id)
        print(f"[UPLOAD] Drive uploaded: file_id={drive_file_id}")

        # 6) Write base row (Sheets)
        ui_data = {
            "name": full_name.strip(),
            "email": normalized_email,  # always from form input
            "location": location.strip(),
            "areas": normalized_interests,
            "capacity": availability.strip(),
            "experience": experience_level.strip(),
            "linkedin": (linkedin_url or "").strip(),
            "github": (github_url or "").strip(),
            "motivation": (motivation or "").strip(),
        }

        print(f"[SHEETS] Writing base row resume_id={resume_id} ...")
        write_base_row(resume_id, drive_file_id, drive_file_url, submission_id, ui_data)
        print(f"[SHEETS] Base row written resume_id={resume_id}")

        # 7) Background parsing (async)
        background_tasks.add_task(_parse_and_update, resume_id, drive_file_id, pre_text)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "submission_id": submission_id,
                "resume_id": resume_id,
                "drive_file_url": drive_file_url,
                "message": "Your application has been received",
            },
        )

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


def _parse_and_update(resume_id: int, drive_file_id: str, pre_extracted_text: str = ""):
    try:
        print(f"[JOB] Parsing resume_id={resume_id} ...")
        parsed = parse_resume(pre_extracted_text or "")
        parsed["drive_file_id"] = drive_file_id
        update_resume_in_sheet(resume_id, parsed)
        print(f"[JOB] Parsed + updated sheet resume_id={resume_id}")
    except Exception as e:
        print(f"[JOB] Error parsing resume_id={resume_id}: {e}")
        traceback.print_exc()


# -----------------------------
# Optional OAuth endpoints
# -----------------------------
@app.get("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        os.getenv("GOOGLE_OAUTH_CLIENT", "org_oauth_client.json"),
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri=APP_REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return {"status": "ok", "auth_url": auth_url}


@app.get("/oauth2callback")
def oauth2callback(code: str):
    flow = Flow.from_client_secrets_file(
        os.getenv("GOOGLE_OAUTH_CLIENT", "org_oauth_client.json"),
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri=APP_REDIRECT_URI,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    with open(os.getenv("TOKEN_FILE", "token.json"), "w") as token:
        token.write(creds.to_json())
    return {"status": "success", "message": "Authorization complete. token.json saved."}
