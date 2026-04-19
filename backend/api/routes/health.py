from datetime import datetime, timezone

from fastapi import APIRouter

from config import ALLOWED_ORIGINS, APP_REDIRECT_URI, MAX_PDF_MB

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "libelle-backend",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.get("/debug/config")
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
