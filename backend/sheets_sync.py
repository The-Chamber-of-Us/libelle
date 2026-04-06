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


# ---------- Write Base Row ----------
def write_base_row(
    drive_file_id: str,
    drive_file_url: Optional[str] = None,
    submission_id: Optional[str] = None,
    ui_data: Optional[Dict[str, Union[str, List[str], bool]]] = None,
) -> None:
    """
    Appends a base row.

    Existing columns stay in their current positions.
    submission_id is written as a new append-only last column.
    """
    ui_data = ui_data or {}

    ts = _local_timestamp()
    drive_url = drive_file_url or _drive_link(drive_file_id)

    # Existing layout used through AC, plus one new final column for submission_id.
    # A  = timestamp
    # B  = full_name
    # C  = email
    # D  = location
    # E  = areas_of_interest
    # F  = availability
    # G  = experience_level
    # H  = linkedin_url
    # I  = github_url
    # J  = resume_file_id
    # K  = resume_file_url
    # L  = motivation
    # M:AC = parser output block
    # AD = submission_id (new last column)
    row = [""] * 30

    row[0] = ts
    row[1] = str(ui_data.get("name", "")).strip()
    row[2] = str(ui_data.get("email", "")).strip()
    row[3] = str(ui_data.get("location", "")).strip()
    row[4] = str(ui_data.get("areas", "")).strip()
    row[5] = str(ui_data.get("capacity", "")).strip()
    row[6] = str(ui_data.get("experience", "")).strip()
    row[7] = str(ui_data.get("linkedin", "")).strip()
    row[8] = str(ui_data.get("github", "")).strip()
    row[9] = drive_file_id
    row[10] = drive_url
    row[11] = str(ui_data.get("motivation", "")).strip()

    # Append-only new last column
    row[29] = submission_id or ""

    sheet.values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    print(
        f"[SHEETS] Base row appended → drive_file_id={drive_file_id}, submission_id={submission_id}"
    )


# ---------- Update Parsed Data ----------
def update_resume_in_sheet(parsed: Dict[str, Any]) -> None:
    drive_file_id = parsed.get("drive_file_id")
    if not drive_file_id:
        print("[SHEETS] Missing drive_file_id. Skipping update.")
        return

    # Locate the correct row by drive_file_id in column J
    values = sheet.values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!J2:J"
    ).execute()

    ids = [r[0] for r in values.get("values", []) if r]
    if drive_file_id not in ids:
        print(f"[SHEETS] Drive file ID {drive_file_id} not found in sheet.")
        return

    row_index = ids.index(drive_file_id) + 2

    # Safe extraction helpers
    name_data = parsed.get("name", {}) or {}
    emails_data = parsed.get("emails", {}) or {}
    locations_data = parsed.get("locations", {}) or {}
    education_data = parsed.get("education", {}) or {}
    skills_data = parsed.get("skills", {}) or {}
    work_data = parsed.get("work_experience", {}) or {}
    project_data = parsed.get("project_experience", {}) or {}

    overall_conf = round(
        (
            float(name_data.get("confidence", 0.0))
            + float(emails_data.get("confidence", 0.0))
            + float(locations_data.get("confidence", 0.0))
            + float(skills_data.get("confidence", 0.0))
        ) / 4.0,
        2,
    )

    parser_row = [
        "parsed",                                                # M - parser_status
        overall_conf,                                            # N - parser_confidence_overall
        name_data.get("value", ""),                              # O - parsed_name
        name_data.get("confidence", 0.0),                        # P - parsed_name_conf
        ", ".join(emails_data.get("value", []) or []),           # Q - parsed_email
        emails_data.get("confidence", 0.0),                      # R - parsed_email_conf
        ", ".join(locations_data.get("value", []) or []),        # S - parsed_location
        locations_data.get("confidence", 0.0),                   # T - parsed_location_conf
        str(education_data.get("value", "")),                    # U - parsed_education
        education_data.get("confidence", 0.0),                   # V - parsed_education_conf
        str(skills_data.get("value", "")),                       # W - parsed_skills_json
        skills_data.get("confidence", 0.0),                      # X - parsed_skills_conf
        str(work_data.get("value", "")),                         # Y - parsed_work_experience_json
        work_data.get("confidence", 0.0),                        # Z - parsed_work_experience_conf
        str(project_data.get("value", "")),                      # AA - parsed_project_experience_json
        project_data.get("confidence", 0.0),                     # AB - parsed_project_experience_conf
        "",                                                      # AC - full_extracted_text placeholder
    ]

    # Update parser block M:AC
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