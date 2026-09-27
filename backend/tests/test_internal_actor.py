import base64
import json

import pytest

from fastapi import HTTPException, Request

from api.internal_actor import (
    CLOUDFLARE_ACCESS_EMAIL_HEADER,
    get_internal_actor,
    require_internal_actor,
)


CLOUDFLARE_ACCESS_JWT_HEADER = "cf-access-jwt-assertion"


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


def test_fabricated_jwt_cannot_establish_actor() -> None:
    request = _request({CLOUDFLARE_ACCESS_JWT_HEADER: _jwt_with_payload({"email": "Ops@Example.ORG"})})

    assert get_internal_actor(request) is None
    with pytest.raises(HTTPException) as exc:
        require_internal_actor(request)
    assert exc.value.status_code == 401


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


@pytest.mark.parametrize("email", [
    "", "  ", "reviewer", "@example.org", "a@", "a@@example.org",
    "a b@example.org", "Reviewer <a@example.org>", "a@example.org,b@example.org",
    "a@example..org", "a@-example.org", ".a@example.org", "a..b@example.org",
    "a@example.org\r\n", "a@example.org\t", "a" * 65 + "@example.org",
])
def test_malformed_header_cannot_fall_back_to_fabricated_jwt(email) -> None:
    request = _request({
        CLOUDFLARE_ACCESS_EMAIL_HEADER: email,
        CLOUDFLARE_ACCESS_JWT_HEADER: _jwt_with_payload({"email": "ops@example.org"}),
    })
    with pytest.raises(HTTPException) as exc:
        require_internal_actor(request)
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "INTERNAL_ACTOR_REQUIRED"


def test_duplicate_identity_headers_fail_closed() -> None:
    request = _request({CLOUDFLARE_ACCESS_EMAIL_HEADER: "reviewer@example.org"})
    request.scope["headers"].append((CLOUDFLARE_ACCESS_EMAIL_HEADER.encode(), b"other@example.org"))
    assert get_internal_actor(request) is None


def test_dev_environment_does_not_supply_backend_identity(monkeypatch) -> None:
    monkeypatch.setenv("VITE_DEV_INTERNAL_ACTOR_EMAIL", "local@example.org")
    assert get_internal_actor(_request()) is None
