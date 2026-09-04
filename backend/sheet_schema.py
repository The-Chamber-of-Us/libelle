SUBMISSIONS_HEADERS = [
    "submission_id",
    "created_at",
    "full_name",
    "email",
    "location_raw",
    "timezone",
    "skills_raw",
    "interests",
    "experience_level",
    "availability",
    "motivation",
    "linkedin_url",
    "github_url",
    "consent_given",
    "drive_file_id",
    "resume_filename",
    "resume_status",
]

PARSER_RESULTS_HEADERS = [
    "submission_id",
    "parser_run_id",
    "created_at",
    "parser_version",
    "parsed_skills_raw",
    "parsed_location_raw",
    "parser_confidence",
    "resolver_version",
    "aliases_version",
    "resolved_skill_ids",
    "unknown_skills",
    "resolver_coverage",
]

OPS_HEADERS = [
    "submission_id",
    "status",
    "notes",
    "tags",
    "contact_tracking",
    "updated_at",
    "updated_by",
]

ERRORS_HEADERS = [
    "submission_id",
    "parser_run_id",
    "created_at",
    "stage",
    "error_code",
    "error_summary",
    "error_details",
]

PARSER_JOBS_HEADERS = [
    "job_id",
    "submission_id",
    "drive_file_id",
    "resume_filename",
    "job_type",
    "status",
    "attempt_count",
    "max_attempts",
    "available_at",
    "locked_by",
    "locked_at",
    "lock_expires_at",
    "last_parser_run_id",
    "authoritative_parser_run_id",
    "parser_started_at",
    "last_error_code",
    "last_error_summary",
    "created_at",
    "updated_at",
]

OPS_EVENTS_HEADERS = [
    "event_id",
    "submission_id",
    "actor_email",
    "action",
    "field_changed",
    "old_value",
    "new_value",
    "created_at",
    "source",
]

SHEET_SCHEMA = {
    "submissions": SUBMISSIONS_HEADERS,
    "parser_results": PARSER_RESULTS_HEADERS,
    "parser_jobs": PARSER_JOBS_HEADERS,
    "ops": OPS_HEADERS,
    "errors": ERRORS_HEADERS,
    "ops_events": OPS_EVENTS_HEADERS,
}

# Tabs that existing v0.3 sheets may not have yet. Startup validation checks
# their headers when present but does not require the tab to exist, and event
# writes degrade to a warning when the tab is missing.
OPTIONAL_TABS = ("ops_events",)


def get_headers(tab_name: str) -> list[str]:
    """
    Return the ordered header list for a known tab.

    Raises:
        ValueError: If the tab name is not defined in SHEET_SCHEMA.
    """
    if tab_name not in SHEET_SCHEMA:
        raise ValueError(f"Unknown tab name: {tab_name}")
    return SHEET_SCHEMA[tab_name]


def get_index_map(tab_name: str) -> dict[str, int]:
    """
    Return a mapping of header_name -> zero-based column index
    for the given tab.
    """
    headers = get_headers(tab_name)
    return {header: index for index, header in enumerate(headers)}


def build_row(tab_name: str, data: dict) -> list:
    """
    Build a row list for the given tab using schema order.

    Any fields not provided in `data` are filled with empty strings.

    Raises:
        ValueError: If `tab_name` is unknown or if `data` contains
        a field not present in the schema for that tab.
    """
    headers = get_headers(tab_name)
    index_map = get_index_map(tab_name)

    unknown_fields = [field for field in data if field not in index_map]
    if unknown_fields:
        raise ValueError(
            f"Unknown field(s) for tab '{tab_name}': {', '.join(unknown_fields)}"
        )

    row = [""] * len(headers)
    for field, value in data.items():
        row[index_map[field]] = value

    return row


def compare_headers(tab_name: str, actual_headers: list[str]) -> dict[str, object]:
    """
    Compare actual headers for a tab against the expected schema headers.

    Returns a dictionary describing whether the headers match exactly,
    including missing headers, extra headers, and whether the order matches.
    """
    expected_headers = get_headers(tab_name)

    missing_expected = [header for header in expected_headers if header not in actual_headers]
    extra_found = [header for header in actual_headers if header not in expected_headers]
    order_matches = actual_headers == expected_headers

    return {
        "tab_name": tab_name,
        "is_match": len(missing_expected) == 0 and len(extra_found) == 0 and order_matches,
        "expected_headers": expected_headers,
        "actual_headers": actual_headers,
        "missing_expected": missing_expected,
        "extra_found": extra_found,
        "order_matches": order_matches,
    }


def compare_tab_names(actual_tabs: list[str]) -> dict[str, object]:
    """
    Compare actual sheet tab names against the expected schema tab names.

    Expected tabs are derived dynamically from SHEET_SCHEMA.keys().

    Returns a dictionary describing whether the tab set matches,
    along with missing and extra tab names.
    """
    expected_tabs = list(SHEET_SCHEMA.keys())

    missing_expected = [
        tab_name
        for tab_name in expected_tabs
        if tab_name not in actual_tabs and tab_name not in OPTIONAL_TABS
    ]
    missing_optional = [
        tab_name
        for tab_name in OPTIONAL_TABS
        if tab_name in expected_tabs and tab_name not in actual_tabs
    ]
    extra_found = [tab_name for tab_name in actual_tabs if tab_name not in expected_tabs]

    return {
        "is_match": len(missing_expected) == 0 and len(extra_found) == 0,
        "expected_tabs": expected_tabs,
        "actual_tabs": actual_tabs,
        "missing_expected": missing_expected,
        "missing_optional": missing_optional,
        "extra_found": extra_found,
    }
