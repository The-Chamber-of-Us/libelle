import os
from typing import Optional, Dict, Union, Any, List
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv
import json

# Load .env
load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "applicantsInfo")

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
        scopes=SCOPES
    )
    print(f"[CREDENTIALS] Loaded service account from local file: {GOOGLE_CREDENTIALS}")


sheet = build("sheets", "v4", credentials=creds).spreadsheets()


# ---------- Helpers ----------
def _drive_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view?usp=drive_link"


def _local_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%m-%d-%Y %H:%M:%S %Z")


def _column_letter(column_number: int) -> str:
    result = ""
    while column_number > 0:
        column_number, remainder = divmod(column_number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _get_headers() -> List[str]:
    header_values = sheet.values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!1:1",
    ).execute().get("values", [])
    return header_values[0] if header_values else []


def _ensure_submission_id_column() -> int:
    """
    Ensure `submission_id` exists as the last column header.
    Returns the 1-based column number for submission_id.

    Important:
    - append-only
    - never insert at column A
    - never shift existing columns
    """
    headers = _get_headers()

    if "submission_id" in headers:
        return headers.index("submission_id") + 1

    column_number = len(headers) + 1 if headers else 1
    column_letter = _column_letter(column_number)

    sheet.values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!{column_letter}1",
        valueInputOption="RAW",
        body={"values": [["submission_id"]]},
    ).execute()

    print(f"[SHEETS] Added submission_id header at column {column_letter}")
    return column_number


# ---------- Write Base Row ----------
def write_base_row(
    drive_file_id: str,
    drive_file_url: Optional[str] = None,
    submission_id: Optional[str] = None,
    ui_data: Optional[Dict[str, Union[str, List[str], bool]]] = None
) -> None:
    """
    Appends a base row while preserving all existing column positions.

    Existing schema remains untouched.
    submission_id is written to a new append-only last column.
    """
    ts = _local_timestamp()
    drive_url = drive_file_url or _drive_link(drive_file_id)
    submission_id_column = _ensure_submission_id_column()
    ui_data = ui_data or {}

    # Keep existing indexed layout intact, and extend row length if submission_id
    # lives beyond the current fixed-width row.
    row = [""] * max(60, submission_id_column)

    # Existing fixed columns
    row[0] = ts  # A  Timestamp
    row[1] = str(ui_data.get("name", ""))         # B  Full Name
    row[2] = str(ui_data.get("email", ""))        # C  Email
    row[3] = str(ui_data.get("location", ""))     # D  Location
    row[4] = str(ui_data.get("areas", ""))        # E  Areas of Interest
    row[5] = str(ui_data.get("capacity", ""))     # F  Availability
    row[6] = str(ui_data.get("experience", ""))   # G  Experience level
    row[7] = str(ui_data.get("linkedin", ""))     # H  LinkedIn URL
    row[8] = str(ui_data.get("github", ""))       # I  GitHub URL
    row[9] = drive_file_id                        # J  resume_file_id
    row[10] = drive_url                           # K  resume_file_url
    row[11] = str(ui_data.get("motivation", ""))  # L  Motivation

    # New append-only column
    row[submission_id_column - 1] = submission_id or ""

    sheet.values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    print(
        f"[SHEETS] Base row appended → drive_file_id={drive_file_id}, "
        f"submission_id_column={submission_id_column}"
    )


# ---------- Update Parsed Data ----------
def update_resume_in_sheet(parsed: Dict[str, Any]) -> None:
    drive_file_id = parsed.get("drive_file_id")
    if not drive_file_id:
        print("[SHEETS] Missing drive_file_id. Skipping update.")
        return

    # Locate row by resume_file_id in column J
    values = sheet.values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!J2:J"
    ).execute()

    ids = [r[0] for r in values.get("values", []) if r]
    if drive_file_id not in ids:
        print(f"[SHEETS] Drive file ID {drive_file_id} not found in sheet.")
        return

    row_index = ids.index(drive_file_id) + 2

    overall_conf = round(sum([
        parsed.get("name", {}).get("confidence", 0.0),
        parsed.get("emails", {}).get("confidence", 0.0),
        parsed.get("locations", {}).get("confidence", 0.0),
        parsed.get("skills", {}).get("confidence", 0.0)
    ]) / 4.0, 2)

    # 17 columns total → M:AC
    parser_row = [
        "parsed",                                                   # M  parser_status
        overall_conf,                                               # N  parser_confidence_overall
        parsed.get("name", {}).get("value", ""),                    # O  parsed_name
        parsed.get("name", {}).get("confidence", 0.0),              # P  parsed_name_conf
        ", ".join(parsed.get("emails", {}).get("value", [])),       # Q  parsed_email
        parsed.get("emails", {}).get("confidence", 0.0),            # R  parsed_email_conf
        ", ".join(parsed.get("locations", {}).get("value", [])),    # S  parsed_location
        parsed.get("locations", {}).get("confidence", 0.0),         # T  parsed_location_conf
        str(parsed.get("education", {}).get("value", "")),          # U  parsed_education
        parsed.get("education", {}).get("confidence", 0.0),         # V  parsed_education_conf
        str(parsed.get("skills", {}).get("value", "")),             # W  parsed_skills_json
        parsed.get("skills", {}).get("confidence", 0.0),            # X  parsed_skills_conf
        str(parsed.get("work_experience", {}).get("value", "")),    # Y  parsed_work_experience_json
        parsed.get("work_experience", {}).get("confidence", 0.0),   # Z  parsed_work_experience_conf
        str(parsed.get("project_experience", {}).get("value", "")), # AA parsed_project_experience_json
        parsed.get("project_experience", {}).get("confidence", 0.0),# AB parsed_project_experience_conf
        "",                                                         # AC full_extracted_text placeholder
    ]

    sheet.values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!M{row_index}:AC{row_index}",
        valueInputOption="RAW",
        body={"values": [parser_row]},
    ).execute()

    # Refresh timestamp in column A
    sheet.values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!A{row_index}",
        valueInputOption="RAW",
        body={"values": [[_local_timestamp()]]},
    ).execute()

    print(f"[SHEETS] Updated parser output → row={row_index}, file_id={drive_file_id}")