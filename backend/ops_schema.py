OPS_STATUS_NEW = "new"
OPS_STATUS_REVIEWED = "reviewed"
OPS_STATUS_CONTACTED = "contacted"
OPS_STATUS_IN_PROGRESS = "in_progress"
OPS_STATUS_PAUSED = "paused"
OPS_STATUS_CLOSED = "closed"

VALID_OPS_STATUSES = (
    OPS_STATUS_NEW,
    OPS_STATUS_REVIEWED,
    OPS_STATUS_CONTACTED,
    OPS_STATUS_IN_PROGRESS,
    OPS_STATUS_PAUSED,
    OPS_STATUS_CLOSED,
)


def is_valid_ops_status(status: str) -> bool:
    """
    Return True if `status` is one of the repo-owned valid ops workflow statuses.

    This helper is intentionally pure and performs exact matching only.
    """
    return isinstance(status, str) and status in VALID_OPS_STATUSES