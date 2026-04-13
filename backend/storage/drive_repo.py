import io
from typing import Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

from config import DRIVE_ROOT_FOLDER_ID, TOKEN_FILE
from storage._auth import load_oauth_creds, build_oauth_flow, DRIVE_SCOPES


def get_drive_service():
    """
    Returns a Google Drive API service authorized with user's OAuth credentials.
    If token.json is missing/invalid, instruct caller to run /authorize.
    """
    creds = load_oauth_creds(DRIVE_SCOPES)
    return build("drive", "v3", credentials=creds)


def get_target_folder_id() -> str:
    """Return the folder ID where uploaded resumes will be stored."""
    if not DRIVE_ROOT_FOLDER_ID:
        raise RuntimeError("DRIVE_ROOT_FOLDER_ID is not set in .env")
    return DRIVE_ROOT_FOLDER_ID


def upload_pdf(file_bytes: bytes, submission_id: str, parent_folder_id: str = None) -> Tuple[str, str]:
    """Upload a resume PDF to Drive and return (file_id, webViewLink)."""
    folder_id = parent_folder_id or get_target_folder_id()
    drive_service = get_drive_service()

    filename = f"{submission_id}-resume.pdf"
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
    """Download a PDF from the user's MyDrive given its file_id."""
    drive_service = get_drive_service()
    request = drive_service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    print(f"[DRIVE] Downloaded file {file_id}")
    return buf.getvalue()


def build_auth_url(redirect_uri: str) -> str:
    """Build a Google OAuth authorization URL for Drive access."""
    flow = build_oauth_flow(redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def exchange_code(code: str, redirect_uri: str) -> None:
    """Exchange an OAuth authorization code for credentials and persist them."""
    flow = build_oauth_flow(redirect_uri)
    flow.fetch_token(code=code)
    with open(TOKEN_FILE, "w") as token:
        token.write(flow.credentials.to_json())
