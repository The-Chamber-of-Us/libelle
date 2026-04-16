import logging
import os
import json

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_CREDENTIALS,
    GOOGLE_OAUTH_CLIENT, TOKEN_FILE,
)

logger = logging.getLogger(__name__)

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def load_service_account_creds(scopes: list):
    """Load Google service-account credentials from env var or local file."""
    if GOOGLE_SERVICE_ACCOUNT_JSON:
        try:
            info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON.strip())
            creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            logger.info("Loaded service account from environment variable.")
            return creds
        except Exception as e:
            raise RuntimeError(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}")

    if not os.path.exists(GOOGLE_CREDENTIALS):
        raise RuntimeError(
            "No GOOGLE_SERVICE_ACCOUNT_JSON env var set and no local credential file found."
        )

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS,
        scopes=scopes,
    )
    logger.info("Loaded service account from local file: %s", GOOGLE_CREDENTIALS)
    return creds


def load_oauth_creds(scopes: list):
    """Load user OAuth credentials from token file, refreshing if needed."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired OAuth credentials.")
            creds.refresh(Request())
        else:
            raise RuntimeError(
                "Drive OAuth token missing/invalid. Visit /authorize in your browser to grant access, "
                "then retry the request."
            )

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def build_oauth_flow(redirect_uri: str) -> Flow:
    """Create an OAuth flow for Drive authorization."""
    return Flow.from_client_secrets_file(
        GOOGLE_OAUTH_CLIENT,
        scopes=DRIVE_SCOPES,
        redirect_uri=redirect_uri,
    )
