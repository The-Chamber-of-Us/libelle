import os
from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: str) -> int:
    return int(os.getenv(name, default))


def _csv_env(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]

# ---- Google Sheets ----
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "org_credentials.json")

# ---- Google Drive ----
GOOGLE_OAUTH_CLIENT = os.getenv("GOOGLE_OAUTH_CLIENT", "org_oauth_client.json")
TOKEN_FILE = os.getenv("TOKEN_FILE", "token.json")
DRIVE_ROOT_FOLDER_ID = os.getenv("DRIVE_ROOT_FOLDER_ID")

# ---- App ----
MAX_PDF_MB = _int_env("MAX_PDF_MB", "5")
APP_REDIRECT_URI = os.getenv("APP_REDIRECT_URI", "http://127.0.0.1:8000/oauth2callback")

_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]

# ---- Public intake rate limiting ----
# In-memory only: counters reset on restart and are not shared across app instances.
ENABLE_INTAKE_RATE_LIMITING = _bool_env("ENABLE_INTAKE_RATE_LIMITING", "true")
INTAKE_RATE_LIMIT_PER_IP_PER_MINUTE = _int_env("INTAKE_RATE_LIMIT_PER_IP_PER_MINUTE", "60")
INTAKE_RATE_LIMIT_PER_EMAIL_PER_HOUR = _int_env("INTAKE_RATE_LIMIT_PER_EMAIL_PER_HOUR", "10")
INTAKE_RATE_LIMIT_GLOBAL_PER_MINUTE = _int_env("INTAKE_RATE_LIMIT_GLOBAL_PER_MINUTE", "120")
INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS = _csv_env("INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS")
INTAKE_TRUSTED_FORWARD_PROXY_CIDRS = _csv_env("INTAKE_TRUSTED_FORWARD_PROXY_CIDRS")
