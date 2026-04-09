import io
import os
from typing import Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from config import GOOGLE_OAUTH_CLIENT, TOKEN_FILE, DRIVE_ROOT_FOLDER_ID

# Drive API scopes
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    """
    Returns a Google Drive API service authorized with user's OAuth credentials.
    If token.json is missing/invalid, instruct caller to run /authorize.
    """
    creds = None

    # Load saved token if present
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If not valid, try to refresh; else instruct to authorize
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[DRIVE] Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            # Do NOT pop a browser here; the app exposes /authorize for a clean flow
            raise RuntimeError(
                "Drive OAuth token missing/invalid. Visit /authorize in your browser to grant access, "
                "then retry the request."
            )

        # Persist refreshed token
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def get_target_folder_id() -> str:
    """Return the folder ID where uploaded resumes will be stored."""
    if not DRIVE_ROOT_FOLDER_ID:
        raise RuntimeError("DRIVE_ROOT_FOLDER_ID is not set in .env")
    return DRIVE_ROOT_FOLDER_ID


def upload_pdf(file_bytes: bytes, filename: str, parent_folder_id: str = None) -> Tuple[str, str]:
    """Upload a PDF to the user’s MyDrive and return (file_id, webViewLink)."""
    folder_id = parent_folder_id or get_target_folder_id()
    drive_service = get_drive_service()

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="application/pdf", resumable=False)
    metadata = {"name": filename, "parents": [folder_id]}

    file = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    file_id = file["id"]
    web_view = file.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
    print(f"[DRIVE] Uploaded '{filename}' → {file_id}")
    return file_id, web_view


def download_file(file_id: str) -> bytes:
    """Download a PDF from the user’s MyDrive given its file_id."""
    drive_service = get_drive_service()
    request = drive_service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    print(f"[DRIVE] Downloaded file {file_id}")
    return buf.getvalue()
