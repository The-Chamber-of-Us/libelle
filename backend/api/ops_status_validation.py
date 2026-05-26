from typing import Any

from fastapi import HTTPException

from ops_schema import VALID_OPS_STATUSES, is_valid_ops_status


INVALID_OPS_STATUS_CODE = "INVALID_OPS_STATUS"


def validate_incoming_ops_status(status: Any) -> str:
    """
    Validate an incoming ops status before any write path persists it.

    Stored snapshot rows may be sanitized for display elsewhere, but incoming
    write requests must be rejected clearly instead of coerced or defaulted.
    """
    if is_valid_ops_status(status):
        return status

    allowed_statuses = ", ".join(VALID_OPS_STATUSES)
    raise HTTPException(
        status_code=400,
        detail={
            "status": "error",
            "code": INVALID_OPS_STATUS_CODE,
            "message": f"Invalid ops status. Expected one of: {allowed_statuses}.",
            "fields": {
                "status": "Must be one of the repo-owned ops workflow statuses.",
            },
        },
    )
