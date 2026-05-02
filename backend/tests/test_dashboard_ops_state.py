from services.dashboard_ops_state import compose_current_ops_state, format_current_ops_state


def test_format_current_ops_state_returns_default_new_state_when_missing() -> None:
    state = format_current_ops_state(None)

    assert state == {
        "status": "new",
        "notes": "",
        "tags": "",
        "contact_tracking": "",
        "updated_at": "",
        "updated_by": "",
    }


def test_format_current_ops_state_formats_repo_owned_ops_fields() -> None:
    row = {
        "submission_id": "sub_001",
        "status": "reviewed",
        "notes": " Looks strong ",
        "tags": "legal, spanish",
        "contact_tracking": "emailed",
        "updated_at": "04-20-2026 12:00:00 UTC",
        "updated_by": "ops@example.org",
        "unowned_field": "not exposed",
    }

    state = format_current_ops_state(row)

    assert state == {
        "status": "reviewed",
        "notes": "Looks strong",
        "tags": "legal, spanish",
        "contact_tracking": "emailed",
        "updated_at": "04-20-2026 12:00:00 UTC",
        "updated_by": "ops@example.org",
    }
    assert "submission_id" not in state
    assert "unowned_field" not in state


def test_format_current_ops_state_defaults_invalid_status_to_new() -> None:
    state = format_current_ops_state(
        {
            "submission_id": "sub_001",
            "status": "pending",
            "notes": "Needs review",
        }
    )

    assert state["status"] == "new"
    assert state["notes"] == "Needs review"


def test_compose_current_ops_state_returns_default_new_state_when_no_match() -> None:
    state = compose_current_ops_state(
        "sub_001",
        [
            {
                "submission_id": "sub_999",
                "status": "contacted",
                "updated_at": "04-20-2026 10:00:00 UTC",
            }
        ],
    )

    assert state["status"] == "new"
    assert state["updated_at"] == ""


def test_compose_current_ops_state_filters_by_submission_id() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "status": "reviewed",
            "updated_at": "04-20-2026 10:00:00 UTC",
        },
        {
            "submission_id": "sub_002",
            "status": "closed",
            "updated_at": "04-20-2026 12:00:00 UTC",
        },
    ]

    state = compose_current_ops_state("sub_001", rows)

    assert state["status"] == "reviewed"
    assert state["updated_at"] == "04-20-2026 10:00:00 UTC"


def test_compose_current_ops_state_selects_latest_matching_ops_row() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "status": "reviewed",
            "updated_at": "04-20-2026 10:00:00 UTC",
        },
        {
            "submission_id": "sub_001",
            "status": "contacted",
            "updated_at": "04-20-2026 12:00:00 UTC",
            "updated_by": "ops@example.org",
        },
    ]

    state = compose_current_ops_state("sub_001", rows)

    assert state["status"] == "contacted"
    assert state["updated_by"] == "ops@example.org"
