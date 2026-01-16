from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Form
from typing import Union
from fastapi.responses import JSONResponse, RedirectResponse
import fitz, traceback, os
from parser import parse_resume
from sheets_sync import write_base_row, update_resume_in_sheet
from drive_sync import get_target_folder_id, upload_pdf, download_file
from google_auth_oauthlib.flow import Flow
from datetime import datetime, timezone
import uuid


app = FastAPI(title="Resume Intake & Parser API")
RESUME_COUNTER = 0

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
            detail={"status": "error", 
                    "code": "VALIDATION_ERROR",
                    "fields": {"file":"Only PDF files are supported."},
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

        # File size validation (5MB)
        MAX_FILE_SIZE_MB = 5
        MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={
                    "status": "error",
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "Max file size is 5MB.",
                },
            )

        # 5) PDF Signature Validation
        if len(file_bytes) < 4 or file_bytes[:4] != b"%PDF":
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "code": "BAD_REQUEST",
                    "message": "Uploaded file is not a valid PDF.",
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
            _parse_and_update, RESUME_COUNTER, drive_file_id
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


def _parse_and_update(resume_id: int, drive_file_id: str):
    try:
        # Downloading PDF bytes
        file_bytes = download_file(drive_file_id)

        # Opening PDF and extract text (using fitz)
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join(page.get_text("text") for page in doc)
        doc.close()

        if not text.strip():
            raise ValueError("PDF opened but no extracted text can be found")
        
        # Parsing resume text
        parsed = parse_resume(text)
        parsed["drive_file_id"] = drive_file_id

        # Updating google sheet
        update_resume_in_sheet(resume_id, parsed)
    
    except Exception as e:
        # Avoiding crash
        print(f"[JOB] Resume parsing failed for resume_id={resume_id}")
        print(f"[JOB] Reason: {e}")
        traceback.print_exc()
        