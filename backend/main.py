from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from typing import Optional, Dict, Any, List, Union
import fitz, traceback, os, json
from parser import parse_resume
from sheets_sync import write_base_row, update_resume_in_sheet
from drive_sync import get_target_folder_id, upload_pdf
from google_auth_oauthlib.flow import Flow
from datetime import datetime, timezone
import uuid


app = FastAPI(title="Libelle Backend API")

# -----------------------------
# Env + Config
# -----------------------------
MAX_PDF_MB = int(os.getenv("MAX_PDF_MB", "5"))
ALLOWED_PDF_MIMES = {"application/pdf", "application/x-pdf"}

# CORS: restricted to approved origins
# Example: ALLOWED_ORIGINS=http://localhost:5173,https://libelle.io
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

# A simple monotonic counter for Drive filenames (not part of API contract)
RESUME_COUNTER = 0


# -----------------------------
# Error Handling (JSON only)
# -----------------------------
def _json_error(status_code: int, payload: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Ensure our errors match the API spec and are NOT wrapped in {"detail": ...}.
    """
    if isinstance(exc.detail, dict):
        return _json_error(exc.status_code, exc.detail)

    return _json_error(
        exc.status_code,
        {"status": "error", "code": "HTTP_EXCEPTION", "message": str(exc.detail)},
    )

@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    """
    Convert FastAPI validation errors into Libelle spec 422 format.
    (e.g. if someone sends totally malformed multipart)
    """
    fields: Dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc", [])
        msg = err.get("msg", "Invalid")
        # loc like ("body", "full_name") or ("body", "file")
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
def _validate_email(email: str) -> bool:
    return bool(email) and ("@" in email) and ("." in email)

def _parse_interests(raw: Union[str, List[str], None]) -> str:
    """
    Spec allows: String / String[] (array preferred, CSV accepted).
    In multipart/form-data, arrays commonly arrive as:
      - JSON string: '["a","b"]'
      - comma string: 'a,b'
      - plain string: 'a'
    We normalize to a single CSV string for Sheets storage.
    """
    if raw is None:
        return ""

    if isinstance(raw, list):
        return ", ".join([str(x).strip() for x in raw if str(x).strip()])

    s = str(raw).strip()
    if not s:
        return ""

    # JSON array
    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return ", ".join([str(x).strip() for x in arr if str(x).strip()])
        except Exception:
            # fall through to treat as plain string
            pass

    # CSV or single token
    # Keep user text as-is, just normalize whitespace around commas
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return ", ".join(parts) if parts else s


# -----------------------------
# Endpoints (Spec)
# -----------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "libelle-backend",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@app.post("/api/upload")
async def upload_volunteer_application(
    background_tasks: BackgroundTasks,

    # Spec: multipart/form-data key MUST be "file"
    file: Optional[UploadFile] = File(None),

    # Spec fields
    full_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    interests: Optional[str] = Form(None),
    availability: Optional[str] = Form(None),
    experience_level: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    github_url: Optional[str] = Form(None),
    motivation: Optional[str] = Form(None),

    # Spec: consent is boolean + must be true
    consent: Optional[bool] = Form(None),
):
    global RESUME_COUNTER

    # 1) Missing file -> 400 FILE_REQUIRED (spec)
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "code": "FILE_REQUIRED",
                "message": "A resume file is required to complete this submission.",
            },
        )

    # 2) Validate required fields -> 422 VALIDATION_ERROR (spec)
    fields: Dict[str, str] = {}

    if not full_name or not full_name.strip():
        fields["full_name"] = "Required"
    if not email or not email.strip():
        fields["email"] = "Required"
    elif not _validate_email(email.strip()):
        fields["email"] = "Invalid format"

    if not location or not location.strip():
        fields["location"] = "Required"

    normalized_interests = _parse_interests(interests)
    if not normalized_interests.strip():
        fields["interests"] = "Required"

    if not availability or not availability.strip():
        fields["availability"] = "Required"

    if not experience_level or not experience_level.strip():
        fields["experience_level"] = "Required"

    # Consent must be true
    if consent is not True:
        fields["consent"] = "Must be true to submit"

    if fields:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "code": "VALIDATION_ERROR", "fields": fields},
        )

    # 3) File validation
    # MIME-type check (more reliable than filename)
    if file.content_type not in ALLOWED_PDF_MIMES and not (file.filename.lower().endswith(".pdf")):
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "code": "INVALID_FILE_TYPE", "message": "Only PDF files supported"},
        )

    submission_id = str(uuid.uuid4())[:8]

    try:
        pdf_bytes = await file.read()
        filename = file.filename or "resume.pdf"

        # size cap
        if len(pdf_bytes) > MAX_PDF_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "code": "FILE_TOO_LARGE", "message": f"PDF too large (>{MAX_PDF_MB}MB)"},
            )

        # 4) PDF sanity check + extract text once
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pre_text = "\n".join([p.get_text("text") for p in doc])
            doc.close()
        except Exception:
            traceback.print_exc()
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "code": "PDF_PARSE_FAILED", "message": "PDF parsing failed"},
            )

        if not pre_text.strip():
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "code": "NO_TEXT_EXTRACTED", "message": "PDF has no extractable text"},
            )

        # 5) Upload to Drive
        RESUME_COUNTER += 1
        folder_id = get_target_folder_id()
        drive_file_id, drive_file_url = upload_pdf(
            pdf_bytes, f"{RESUME_COUNTER}-{filename}", folder_id
        )

        # 6) Write base row (UI data + drive info)
        ui_data = {
            "name": full_name.strip(),
            "email": email.strip(),
            "location": location.strip(),
            "areas": normalized_interests,               # store as CSV string in sheet
            "capacity": availability.strip(),
            "experience": experience_level.strip(),
            "linkedin": (linkedin_url or "").strip(),
            "github": (github_url or "").strip(),
            "motivation": (motivation or "").strip(),
        }

        write_base_row(RESUME_COUNTER, drive_file_id, drive_file_url, submission_id, ui_data)

        # 7) Background parsing (async)
        background_tasks.add_task(_parse_and_update, RESUME_COUNTER, drive_file_id, pre_text)

        # 8) Success response (spec)
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "submission_id": submission_id,
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
        parsed = parse_resume(pre_extracted_text or "")
        parsed["drive_file_id"] = drive_file_id
        update_resume_in_sheet(resume_id, parsed)
    except Exception as e:
        print(f"[JOB] Error parsing resume_id={resume_id}: {e}")
        traceback.print_exc()


# -----------------------------
# Optional OAuth endpoints (JSON responses)
# (Not part of Libelle spec, but kept for local Drive auth setup)
# -----------------------------
@app.get("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        os.getenv("GOOGLE_OAUTH_CLIENT", "org_oauth_client.json"),
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri="http://127.0.0.1:8000/oauth2callback",
    )
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    # JSON only
    return {"status": "ok", "auth_url": auth_url}

@app.get("/oauth2callback")
def oauth2callback(code: str):
    flow = Flow.from_client_secrets_file(
        os.getenv("GOOGLE_OAUTH_CLIENT", "org_oauth_client.json"),
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri="http://127.0.0.1:8000/oauth2callback",
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    with open(os.getenv("TOKEN_FILE", "token.json"), "w") as token:
        token.write(creds.to_json())
    return {"status": "success", "message": "Authorization complete. token.json saved."}
