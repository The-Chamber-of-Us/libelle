import base64
import json

from fastapi import HTTPException, Request

from api.internal_actor import (
    CLOUDFLARE_ACCESS_EMAIL_HEADER,
    CLOUDFLARE_ACCESS_JWT_HEADER,
    get_internal_actor,
    require_internal_actor,
)


def _request(headers: dict[str, str] | None = None) -> Request:
    encoded_headers = []
    for key, value in (headers or {}).items():
        encoded_headers.append((key.lower().encode("ascii"), value.encode("utf-8")))

    return Request({"type": "http", "method": "GET", "path": "/", "headers": encoded_headers})


def _jwt_with_payload(payload: dict) -> str:
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).rstrip(b"=")
    return f"header.{encoded_payload.decode('ascii')}.signature"


def test_get_internal_actor_uses_cloudflare_access_email_header() -> None:
    request = _request({CLOUDFLARE_ACCESS_EMAIL_HEADER: " Reviewer@Example.ORG "})

    assert get_internal_actor(request) == "reviewer@example.org"


def test_get_internal_actor_uses_cloudflare_access_jwt_email_when_email_header_missing() -> None:
    request = _request({CLOUDFLARE_ACCESS_JWT_HEADER: _jwt_with_payload({"email": "Ops@Example.ORG"})})

    assert get_internal_actor(request) == "ops@example.org"


def test_get_internal_actor_prefers_cloudflare_access_email_header_over_jwt() -> None:
    request = _request(
        {
            CLOUDFLARE_ACCESS_EMAIL_HEADER: "reviewer@example.org",
            CLOUDFLARE_ACCESS_JWT_HEADER: _jwt_with_payload({"email": "other@example.org"}),
        }
    )

    assert get_internal_actor(request) == "reviewer@example.org"


def test_get_internal_actor_returns_none_when_identity_missing() -> None:
    assert get_internal_actor(_request()) is None


def test_get_internal_actor_returns_none_for_blank_identity() -> None:
    request = _request({CLOUDFLARE_ACCESS_EMAIL_HEADER: "  "})

    assert get_internal_actor(request) is None


def test_get_internal_actor_returns_none_for_invalid_jwt_payload() -> None:
    request = _request({CLOUDFLARE_ACCESS_JWT_HEADER: "header.not-json.signature"})

    assert get_internal_actor(request) is None


def test_require_internal_actor_returns_present_identity() -> None:
    request = _request({CLOUDFLARE_ACCESS_EMAIL_HEADER: "reviewer@example.org"})

    assert require_internal_actor(request) == "reviewer@example.org"


def test_require_internal_actor_rejects_missing_identity() -> None:
    try:
        require_internal_actor(_request())
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail["code"] == "INTERNAL_ACTOR_REQUIRED"
    else:
        raise AssertionError("Expected HTTPException for missing internal actor")
