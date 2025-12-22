from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Form, Request
from typing import Union
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
import fitz, traceback, os
from parser import parse_resume
from sheets_sync import write_base_row, update_resume_in_sheet
from drive_sync import get_target_folder_id, upload_pdf, download_file
from google_auth_oauthlib.flow import Flow
from datetime import datetime, timezone
import uuid


app = FastAPI(title="Resume Intake & Parser API")
RESUME_COUNTER = 0

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {}

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": detail.get("code", "HTTP_ERROR"),
            "message": detail.get("message", "Request failed"),
            "fields": detail.get("fields", {}),
        },
    )

@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    fields = {}

    for error in exc.errors():
        loc = error.get("loc", [])
        msg = error.get("msg", "Invalid value")

        # Example loc: ("body", "email")
        if len(loc) >= 2:
            fields[loc[-1]] = msg

    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "code": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "fields": fields,
        },
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "libelle-backend",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

@app.get("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        os.getenv("GOOGLE_OAUTH_CLIENT", "org_oauth_client.json"),
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri="http://127.0.0.1:8000/oauth2callback"
    )
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    return RedirectResponse(auth_url)

@app.get("/oauth2callback")
def oauth2callback(code: str):
    flow = Flow.from_client_secrets_file(
        os.getenv("GOOGLE_OAUTH_CLIENT", "org_oauth_client.json"),
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri="http://127.0.0.1:8000/oauth2callback"
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    with open(os.getenv("TOKEN_FILE", "token.json"), "w") as token:
        token.write(creds.to_json())
    return {"status": "success", "message": "Authorization complete. token.json saved."}

@app.get("/")
def root():
    return {"message": "Resume Parser API is running"}

@app.post("/api/upload")
async def upload_volunteer_application(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    full_name: str = Form(...),
    email: str = Form(...),
    location: str = Form(...),
    interests: str = Form(...),
    availability: str = Form(...),
    experience_level: str = Form(...),
    consent: bool = Form(...),
    linkedin_url: Union[str, None] = Form(None),
    github_url: Union[str, None] = Form(None),
    motivation: Union[str, None] = Form(None),
):
    global RESUME_COUNTER
    
    # 1) Consent validation
    if consent is not True:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "code": "VALIDATION_ERROR",
                "fields": {"consent": "Must be checked to submit application."},
            },
        )

    # 2) File presence + type validation
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "code": "FILE_REQUIRED",
                "message": "A resume file is required to complete this submission.",
            },
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "Only PDF files supported",
                "fields": {"file": "Only PDF files supported"},
            },
        )

    

    # 3) Add validation for email and extra security for each field 
    missing_fields = {}
    if (not full_name):
        missing_fields["full_name"] = "Required"
    if (not location):
        missing_fields["location"] = "Required"
    if (not interests):
        missing_fields["interests"] = "Required"
    if (not availability):
        missing_fields["availability"] = "Required"
    if (not experience_level):
        missing_fields["experience_level"] = "Required"
    if (not consent):
        missing_fields["consent"] = "Required"
        
    if (not email):
        missing_fields["email"] = "Required"
    elif (not "." in email or not "@" in email):
        missing_fields["email"] = "Invalid format"
    
    if missing_fields:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "code": "VALIDATION_ERROR",
                "fields": missing_fields
            },
        ) 

    submission_id = str(uuid.uuid4())[:8]

    # 4) Build ui_data for Sheets
    ui_data = {
        "name": full_name,
        "email": email,
        "location": location,
        "areas": interests,
        "capacity": availability,
        "experience": experience_level,
        "linkedin": linkedin_url,
        "github": github_url,
        "motivation": motivation,
    }

    try:
        file_bytes = await file.read()
        filename = file.filename

        # 5) Basic PDF sanity check
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception:
            traceback.print_exc()
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "PDF parsing failed: no text extracted",
                },
            )

        pre_text = "\n".join([p.get_text("text") for p in doc])
        doc.close()

        if not pre_text.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "PDF parsing failed: no text extracted",
                },
            )

        # 6) Upload to Drive
        RESUME_COUNTER += 1  # keep existing behaviour for now
        folder_id = get_target_folder_id()
        drive_file_id, drive_file_url = upload_pdf(
            file_bytes, f"{RESUME_COUNTER}-{filename}", folder_id
        )

        # 7) Write base row (requires updated sheets_sync.write_base_row)
        write_base_row(RESUME_COUNTER, drive_file_id, drive_file_url, submission_id, ui_data)

        # 8) Background parsing
        background_tasks.add_task(
            _parse_and_update, RESUME_COUNTER, drive_file_id, pre_text
        )

        # 9) Success response (matches API spec)
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
        text = pre_extracted_text or "\n".join([p.get_text("text") for p in fitz.open(stream=download_file(drive_file_id), filetype="pdf")])
        parsed = parse_resume(text)
        parsed["drive_file_id"] = drive_file_id
        update_resume_in_sheet(resume_id, parsed)
    except Exception as e:
        print(f"[JOB] Error parsing resume_id={resume_id}: {e}")
        traceback.print_exc()
