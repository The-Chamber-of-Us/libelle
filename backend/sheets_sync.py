import os
import json
import uuid
from typing import Optional, Dict, Union, Any, List
from datetime import datetime, timezone

from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv

from sheet_schema import build_row

from sheet_schema import build_row

# Load .env
load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# Keep backward compatibility for submissions tab if SHEET_NAME is already used.
SUBMISSIONS_SHEET_NAME = os.getenv("SUBMISSIONS_SHEET_NAME", os.getenv("SHEET_NAME", "submissions"))
PARSER_RESULTS_SHEET_NAME = os.getenv("PARSER_RESULTS_SHEET_NAME", "parser_results")

if not GOOGLE_SHEET_ID:
    raise RuntimeError("GOOGLE_SHEET_ID not set in .env")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ------------------------------ Secure Credential Loading -------------------------------------

service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

if service_account_json:
    try:
        service_account_json = service_account_json.strip()
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        print("[CREDENTIALS] Loaded service account from environment variable.")
    except Exception as e:
        raise RuntimeError(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
else:
    # Fallback: using file (LOCAL DEV ONLY)
    GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "org_credentials.json")

    if not os.path.exists(GOOGLE_CREDENTIALS):
        raise RuntimeError(
            "No GOOGLE_SERVICE_ACCOUNT_JSON env var set and no local credential file found."
        )

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS,
        scopes=SCOPES,
    )
    print(f"[CREDENTIALS] Loaded service account from local file: {GOOGLE_CREDENTIALS}")

sheet = build("sheets", "v4", credentials=creds).spreadsheets()


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

    sheet.values().append(
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

    sheet.values().append(
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
