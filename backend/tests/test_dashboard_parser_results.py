from services.dashboard_parser_results import select_latest_parser_result


def test_select_latest_parser_result_returns_none_for_empty_rows() -> None:
    assert select_latest_parser_result([]) is None


def test_select_latest_parser_result_selects_highest_parser_run_id() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "1",
            "created_at": "04-20-2026 10:00:00 UTC",
            "parsed_skills_raw": "Python",
        },
        {
            "submission_id": "sub_001",
            "parser_run_id": "10",
            "created_at": "04-20-2026 09:00:00 UTC",
            "parsed_skills_raw": "Python, SQL",
        },
        {
            "submission_id": "sub_001",
            "parser_run_id": "2",
            "created_at": "04-20-2026 11:00:00 UTC",
            "parsed_skills_raw": "Python, React",
        },
    ]

    latest = select_latest_parser_result(rows)

    assert latest is not None
    assert latest["parser_run_id"] == "10"
    assert latest["parsed_skills_raw"] == "Python, SQL"


def test_select_latest_parser_result_breaks_ties_by_latest_created_at() -> None:
    rows = [
        {
            "submission_id": "sub_001",
            "parser_run_id": "5",
            "created_at": "04-20-2026 10:00:00 UTC",
            "parsed_skills_raw": "older result",
        },
        {
            "submission_id": "sub_001",
            "parser_run_id": "5",
            "created_at": "04-20-2026 12:00:00 UTC",
            "parsed_skills_raw": "newer result",
        },
    ]

    latest = select_latest_parser_result(rows)

    assert latest is not None
    assert latest["created_at"] == "04-20-2026 12:00:00 UTC"
    assert latest["parsed_skills_raw"] == "newer result"