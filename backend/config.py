import os
from dotenv import load_dotenv

load_dotenv()

# ---- Google Sheets ----
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "org_credentials.json")

# ---- Google Drive ----
GOOGLE_OAUTH_CLIENT = os.getenv("GOOGLE_OAUTH_CLIENT", "org_oauth_client.json")
TOKEN_FILE = os.getenv("TOKEN_FILE", "token.json")
DRIVE_ROOT_FOLDER_ID = os.getenv("DRIVE_ROOT_FOLDER_ID")

# ---- App ----
MAX_PDF_MB = int(os.getenv("MAX_PDF_MB", "5"))
APP_REDIRECT_URI = os.getenv("APP_REDIRECT_URI", "http://127.0.0.1:8000/oauth2callback")

_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]
