from fastapi import APIRouter

from config import APP_REDIRECT_URI
from storage.drive_repo import build_auth_url, exchange_code

router = APIRouter()


@router.get("/authorize")
def authorize():
    auth_url = build_auth_url(APP_REDIRECT_URI)
    return {"status": "ok", "auth_url": auth_url}


@router.get("/oauth2callback")
def oauth2callback(code: str):
    exchange_code(code, APP_REDIRECT_URI)
    return {"status": "success", "message": "Authorization complete. token.json saved."}
