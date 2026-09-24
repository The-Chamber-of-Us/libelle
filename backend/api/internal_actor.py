"""Actor attribution under the trusted-ingress contract (see docs/deployment/internal_actor_trust.md).

Access authentication happens upstream. Direct origin access must be blocked;
header syntax validation cannot authenticate an arbitrary caller.
"""

import re

from fastapi import HTTPException, Request


CLOUDFLARE_ACCESS_EMAIL_HEADER = "cf-access-authenticated-user-email"


def get_internal_actor(request: Request) -> str | None:
    # Multiple values are ambiguous even if an intermediary would pick one.
    values = request.headers.getlist(CLOUDFLARE_ACCESS_EMAIL_HEADER)
    if len(values) != 1:
        return None
    return _normalize_actor(values[0])


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


def _normalize_actor(value: str) -> str | None:
    # Accept a single ASCII mailbox, not display names or address lists.
    # Trim surrounding spaces while rejecting controls (including CR/LF).
    if any(ord(char) < 32 or ord(char) > 126 for char in value):
        return None
    normalized = value.strip().lower()
    if len(normalized) > 254 or normalized.count("@") != 1:
        return None
    local, domain = normalized.split("@")
    if not local or len(local) > 64 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local):
        return None
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return None
    labels = domain.split(".")
    if len(labels) < 2 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ):
        return None
    return normalized
