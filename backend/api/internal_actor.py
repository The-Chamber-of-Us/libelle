import base64
import binascii
import json
from typing import Any

from fastapi import HTTPException, Request


CLOUDFLARE_ACCESS_EMAIL_HEADER = "cf-access-authenticated-user-email"
CLOUDFLARE_ACCESS_JWT_HEADER = "cf-access-jwt-assertion"


def get_internal_actor(request: Request) -> str | None:
    actor = _normalize_actor(request.headers.get(CLOUDFLARE_ACCESS_EMAIL_HEADER))
    if actor is not None:
        return actor

    access_jwt = request.headers.get(CLOUDFLARE_ACCESS_JWT_HEADER)
    if not access_jwt:
        return None

    return _normalize_actor(_get_email_from_access_jwt(access_jwt))


def require_internal_actor(request: Request) -> str:
    actor = get_internal_actor(request)
    if actor is None:
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "code": "INTERNAL_ACTOR_REQUIRED",
                "message": "Authenticated internal actor identity is required.",
            },
        )
    return actor


def _normalize_actor(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip().lower()
    if not normalized:
        return None

    return normalized


def _get_email_from_access_jwt(access_jwt: str) -> str | None:
    parts = access_jwt.split(".")
    if len(parts) != 3:
        return None

    try:
        payload_bytes = _decode_base64url(parts[1])
        payload = json.loads(payload_bytes)
    except (binascii.Error, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload.get("email")


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")
