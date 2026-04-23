import json
import threading
import uuid
from typing import Optional, Dict, Union, Any, List
from datetime import datetime, timezone
from googleapiclient.discovery import build

from config import GOOGLE_SHEET_ID
from sheet_schema import SHEET_SCHEMA, build_row, get_headers
from storage._auth import load_service_account_creds, SHEETS_SCOPES

if not GOOGLE_SHEET_ID:
    raise RuntimeError("GOOGLE_SHEET_ID not set in .env")

SUBMISSIONS_SHEET_NAME = "submissions"
PARSER_RESULTS_SHEET_NAME = "parser_results"

_sheet = None
_sheet_lock = threading.Lock()


def _get_sheet():
    """Lazily build and cache the Sheets API client."""
    global _sheet
    if _sheet is None:
        with _sheet_lock:
            if _sheet is None:
                creds = load_service_account_creds(SHEETS_SCOPES)
                _sheet = build("sheets", "v4", credentials=creds).spreadsheets()
    return _sheet


def fetch_live_schema() -> Dict[str, Any]:
    """
    Snapshot the live Google Sheet for startup schema validation.

    Makes two Sheets API calls:
      1. spreadsheets().get(fields="sheets.properties.title") to list tab names.
      2. values().batchGet(...) to read Row 1 of every expected tab that
         exists in the live sheet.

    Returns:
        {
            "tabs":    [str, ...],                    # all live tab titles
            "headers": {tab_name: [str, ...], ...},   # row 1 for expected
                                                       # tabs that exist
        }

    Sheets/auth exceptions are allowed to propagate so the caller (startup
    validator) halts with the underlying diagnostic traceback intact.
    """
    sheet = _get_sheet()

    meta = sheet.get(
        spreadsheetId=GOOGLE_SHEET_ID,
        fields="sheets.properties.title",
    ).execute()
    tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]

    expected_present = [t for t in SHEET_SCHEMA if t in tabs]
    headers: Dict[str, List[str]] = {}

    if expected_present:
        ranges = [f"{t}!1:1" for t in expected_present]
        batch = sheet.values().batchGet(
            spreadsheetId=GOOGLE_SHEET_ID,
            ranges=ranges,
        ).execute()
        value_ranges = batch.get("valueRanges", [])
        for tab_name, vr in zip(expected_present, value_ranges):
            rows = vr.get("values", [])
            headers[tab_name] = rows[0] if rows else []

    return {"tabs": tabs, "headers": headers}


def load_submission_records() -> Dict[str, Dict[str, str]]:
    """
    Load canonical intake rows from the submissions tab for later snapshot composition.

    Returns:
        Dict[str, Dict[str, str]]:
            A dictionary keyed by submission_id. Each value is a schema-aligned
            dictionary containing only submissions-tab fields.

    Scope boundary:
        - Loads submissions data only
        - Does NOT perform parser selection
        - Does NOT compose ops state
        - Does NOT summarize errors
        - Does NOT assemble final snapshot records

    Missing/blank cells are normalized to "" so optional fields are handled safely.
    Rows with no submission_id are skipped because submission_id is the required key.
    """
    headers = get_headers(SUBMISSIONS_SHEET_NAME)

    response = _get_sheet().values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SUBMISSIONS_SHEET_NAME}!A2:{chr(64 + len(headers))}",
    ).execute()

    rows = response.get("values", [])
    records_by_submission_id: Dict[str, Dict[str, str]] = {}

    for raw_row in rows:
        padded_row = list(raw_row) + [""] * (len(headers) - len(raw_row))
        row_dict = {
            header: str(value).strip() if value is not None else ""
            for header, value in zip(headers, padded_row)
        }

        submission_id = row_dict.get("submission_id", "")
        if not submission_id:
            continue

        records_by_submission_id[submission_id] = row_dict

    return records_by_submission_id


# ---------- Helpers ----------
def _drive_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view?usp=drive_link"


def _local_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%m-%d-%Y %H:%M:%S %Z")


def _json_string(value: Any) -> str:
    """
    Serialize complex values consistently for sheet storage.
    Lists/dicts become JSON strings; scalars become plain strings.
    Empty/None becomes "".
    """
    if value is None or value == "":
        return ""

    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def _stringify_location(value: Any) -> str:
    """
    Store parsed_location_raw as a readable string while tolerating
    parser outputs that may be list or scalar.
    """
    if value is None or value == "":
        return ""

    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())

    return str(value)


def _compute_parser_confidence(parsed: Dict[str, Any]) -> float:
    """
    Preserve the current logical parser-confidence behavior:
    average of name, emails, locations, and skills confidence.
    """
    confidences = [
        parsed.get("name", {}).get("confidence", 0.0),
        parsed.get("emails", {}).get("confidence", 0.0),
        parsed.get("locations", {}).get("confidence", 0.0),
        parsed.get("skills", {}).get("confidence", 0.0),
    ]
    return round(sum(confidences) / 4.0, 2)


# ---------- Write Base Row ----------
def write_base_row(
    drive_file_id: str,
    drive_file_url: Optional[str] = None,
    submission_id: Optional[str] = None,
    ui_data: Optional[Dict[str, Union[str, List[str], bool]]] = None,
) -> None:
    """
    Appends a base row using schema-driven row construction.
    This refactor changes only how the row is built, not the write-path behavior.
    """
    ts = _local_timestamp()

    if ui_data is None:
        ui_data = {}

    row_data = {
        "submission_id": submission_id or "",
        "created_at": ts,
        "full_name": ui_data.get("name", ""),
        "email": ui_data.get("email", ""),
        "location_raw": ui_data.get("location", ""),
        "timezone": "",
        "skills_raw": "",
        "interests": ui_data.get("areas", ""),
        "experience_level": ui_data.get("experience", ""),
        "availability": ui_data.get("capacity", ""),
        "motivation": ui_data.get("motivation", ""),
        "linkedin_url": ui_data.get("linkedin", ""),
        "github_url": ui_data.get("github", ""),
        "consent_given": True,
        "resume_filename": f"{submission_id}-resume.pdf" if submission_id else "",
        "resume_status": "uploaded",
    }

    row = build_row("submissions", row_data)

    _get_sheet().values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SUBMISSIONS_SHEET_NAME}!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    print(f"[SHEETS] Base row appended → submission_id={submission_id}, drive_file_id={drive_file_id}")


# ---------- Write Parser Results ----------
def update_resume_in_sheet(submission_id: str, parsed: Dict[str, Any]) -> None:
    """
    Appends one schema-driven row to the parser_results tab.

    This ticket intentionally changes how the parser_results row is built,
    not the parser logic itself.
    """
    if not submission_id:
        print("[SHEETS] Missing submission_id. Skipping parser_results write.")
        return

    parser_run_id = parsed.get("parser_run_id") or str(uuid.uuid4())[:8]
    parser_confidence = _compute_parser_confidence(parsed)

    row_data = {
        "submission_id": submission_id,
        "parser_run_id": parser_run_id,
        "created_at": _local_timestamp(),
        "parser_version": parsed.get("parser_version", ""),
        "parsed_skills_raw": _json_string(parsed.get("skills", {}).get("value", [])),
        "parsed_location_raw": _stringify_location(parsed.get("locations", {}).get("value", [])),
        "parser_confidence": parser_confidence,
        "resolver_version": parsed.get("resolver_version", ""),
        "aliases_version": parsed.get("aliases_version", ""),
        "resolved_skill_ids": _json_string(parsed.get("resolved_skill_ids", [])),
        "unknown_skills": _json_string(parsed.get("unknown_skills", [])),
        "resolver_coverage": parsed.get("resolver_coverage", ""),
    }

    parser_row = build_row("parser_results", row_data)

    _get_sheet().values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{PARSER_RESULTS_SHEET_NAME}!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [parser_row]},
    ).execute()

    print(
        f"[SHEETS] Parser results appended → submission_id={submission_id}, "
        f"parser_run_id={parser_run_id}"
    )