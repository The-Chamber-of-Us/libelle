import pytest

from ops_schema import (
    OPS_STATUS_CLOSED,
    OPS_STATUS_CONTACTED,
    OPS_STATUS_IN_PROGRESS,
    OPS_STATUS_NEW,
    OPS_STATUS_PAUSED,
    OPS_STATUS_REVIEWED,
    VALID_OPS_STATUSES,
    is_valid_ops_status,
)


@pytest.mark.parametrize(
    "status",
    [
        OPS_STATUS_NEW,
        OPS_STATUS_REVIEWED,
        OPS_STATUS_CONTACTED,
        OPS_STATUS_IN_PROGRESS,
        OPS_STATUS_PAUSED,
        OPS_STATUS_CLOSED,
    ],
)
def test_is_valid_ops_status_accepts_all_valid_statuses(status: str) -> None:
    assert is_valid_ops_status(status) is True


@pytest.mark.parametrize(
    "status",
    [
        "archived",
        "pending",
        "",
        "NEW",
        "Reviewed",
        "in progress",
        "paused ",
        None,
        123,
        [],
        {},
    ],
)
def test_is_valid_ops_status_rejects_invalid_statuses(status) -> None:
    assert is_valid_ops_status(status) is False


def test_valid_ops_statuses_constant_matches_expected_contract() -> None:
    assert VALID_OPS_STATUSES == (
        "new",
        "reviewed",
        "contacted",
        "in_progress",
        "paused",
        "closed",
    )