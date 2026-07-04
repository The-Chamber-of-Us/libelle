"""
Startup-time validation that the live Google Sheet matches the repo-owned
schema contract in sheet_schema.py.

Pure orchestration: fetches a live snapshot via storage.sheets_repo and
compares it against SHEET_SCHEMA using the pure comparison helpers.
Raises SchemaValidationError on any mismatch so FastAPI halts startup.
"""
from sheet_schema import SHEET_SCHEMA, compare_headers, compare_tab_names
from storage.sheets_repo import fetch_live_schema


class SchemaValidationError(RuntimeError):
    """Raised when the live Google Sheet does not match SHEET_SCHEMA."""


def validate_sheet_schema() -> None:
    """
    Verify the live Google Sheet matches SHEET_SCHEMA.

    On success: prints "[SCHEMA] Schema Validated" and returns None.
    On mismatch: raises SchemaValidationError naming every offending tab
    and showing expected vs. actual headers. Missing tabs are named
    explicitly.

    Sheets/auth exceptions raised by fetch_live_schema() propagate so
    their original diagnostic traceback is preserved.
    """
    live = fetch_live_schema()

    errors = []

    tab_result = compare_tab_names(live["tabs"])
    if not tab_result["is_match"]:
        errors.append(_format_tab_error(tab_result))

    live_tabs = set(live["tabs"])
    for tab_name in SHEET_SCHEMA:
        if tab_name not in live_tabs:
            continue
        actual_headers = live["headers"].get(tab_name, [])
        header_result = compare_headers(tab_name, actual_headers)
        if not header_result["is_match"]:
            errors.append(_format_header_error(header_result))

    if errors:
        raise SchemaValidationError(
            "Google Sheet schema validation failed:\n\n" + "\n\n".join(errors)
        )

    for tab_name in tab_result.get("missing_optional", []):
        print(
            f"[SCHEMA] Optional tab '{tab_name}' not found; "
            "related writes will be skipped with a warning."
        )

    print("[SCHEMA] Schema Validated")


def _format_tab_error(result: dict) -> str:
    lines = ["[tabs] Sheet tab set does not match SHEET_SCHEMA."]
    lines.append(f"  expected: {result['expected_tabs']}")
    lines.append(f"  actual:   {result['actual_tabs']}")
    if result["missing_expected"]:
        lines.append(f"  missing tabs: {result['missing_expected']}")
    if result["extra_found"]:
        lines.append(f"  extra tabs:   {result['extra_found']}")
    return "\n".join(lines)


def _format_header_error(result: dict) -> str:
    lines = [f"[{result['tab_name']}] Header mismatch."]
    lines.append(f"  expected: {result['expected_headers']}")
    lines.append(f"  actual:   {result['actual_headers']}")
    if result["missing_expected"]:
        lines.append(f"  missing:  {result['missing_expected']}")
    if result["extra_found"]:
        lines.append(f"  extra:    {result['extra_found']}")
    if (
        not result["order_matches"]
        and not result["missing_expected"]
        and not result["extra_found"]
    ):
        lines.append("  order does not match expected.")
    return "\n".join(lines)
