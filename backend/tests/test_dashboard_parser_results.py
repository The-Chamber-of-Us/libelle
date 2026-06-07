from services.dashboard_parser_results import select_latest_parser_result


def test_select_latest_parser_result_returns_none_for_empty_rows() -> None:
    assert select_latest_parser_result([]) is None


def test_select_latest_parser_result_selects_latest_created_at() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "z-lower-priority",
            "created_at": "04-20-2026 10:00:00 UTC",
            "parsed_skills_raw": "Python",
        },
        {
            "submission_id": "sub_001",
            "parser_run_id": "a-newest",
            "created_at": "04-20-2026 09:00:00 UTC",
            "parsed_skills_raw": "Python, SQL",
        },
        {
            "submission_id": "sub_001",
            "parser_run_id": "b-newer",
            "created_at": "04-20-2026 11:00:00 UTC",
            "parsed_skills_raw": "Python, React",
        },
    ]

    latest = select_latest_parser_result(rows)

    assert latest is not None
    assert latest["parser_run_id"] == "b-newer"
    assert latest["parsed_skills_raw"] == "Python, React"


def test_select_latest_parser_result_breaks_created_at_ties_by_parser_run_id() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "5",
            "created_at": "04-20-2026 12:00:00 UTC",
            "parsed_skills_raw": "lower run id",
        },
        {
            "submission_id": "sub_001",
            "created_at": "04-20-2026 12:00:00 UTC",
            "parser_run_id": "10",
            "parsed_skills_raw": "higher run id",
        },
    ]

    latest = select_latest_parser_result(rows)

    assert latest is not None
    assert latest["created_at"] == "04-20-2026 12:00:00 UTC"
    assert latest["parser_run_id"] == "10"
    assert latest["parsed_skills_raw"] == "higher run id"


def test_select_latest_parser_result_returns_copy() -> None:
    row = {
        "submission_id": "sub_001",
        "parser_run_id": "1",
        "created_at": "04-20-2026 10:00:00 UTC",
    }

    latest = select_latest_parser_result([row])

    assert latest is not row
    assert latest is not None

    latest["parser_run_id"] = "999"

    assert row["parser_run_id"] == "1"
