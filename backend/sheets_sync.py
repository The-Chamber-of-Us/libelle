import os
from typing import Optional, Dict, Union, Any, List
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv
import json

from sheet_schema import build_row

# Load .env
load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "applicantsInfo")
#USER_TIMEZONE = os.getenv("USER_TIMEZONE", "America/New_York")

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

    sheet.values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    print(f"[SHEETS] Base row appended → drive_file_id={drive_file_id}")


# ---------- Update Parsed Data ----------
def update_resume_in_sheet(parsed: Dict[str, Any]) -> None:
    drive_file_id = parsed.get("drive_file_id")
    if not drive_file_id:
        print("[SHEETS] Missing drive_file_id. Skipping update.")
        return

    # Locate the correct row
    values = sheet.values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!J2:J"
    ).execute()
    ids = [r[0] for r in values.get("values", []) if r]
    if drive_file_id not in ids:
        print(f"[SHEETS] Drive file ID {drive_file_id} not found in sheet.")
        return

    row_index = ids.index(drive_file_id) + 2

    # Compute parser confidence
    overall_conf = round(sum([
        parsed.get("name", {}).get("confidence", 0.0),
        parsed.get("emails", {}).get("confidence", 0.0),
        parsed.get("locations", {}).get("confidence", 0.0),
        parsed.get("skills", {}).get("confidence", 0.0)
    ]) / 4.0, 2)

    # Construct row aligned to columns M–AC (27 columns)
    parser_row = [
        "parsed",                                         # M - parser_status
        overall_conf,                                     # N - parser_confidence_overall
        parsed["name"]["value"],                          # O - parsed_name
        parsed["name"]["confidence"],                     # P - parsed_name_conf
        ", ".join(parsed["emails"]["value"]),             # Q - parsed_email
        parsed["emails"]["confidence"],                   # R - parsed_email_conf
        ", ".join(parsed["locations"]["value"]),          # S - parsed_location
        parsed["locations"]["confidence"],                # T - parsed_location_conf
        str(parsed["education"]["value"]),                # U - parsed_education
        parsed["education"]["confidence"],                # V - parsed_education_conf
        str(parsed["skills"]["value"]),                   # W - parsed_skills_json
        parsed["skills"]["confidence"],                   # X - parsed_skills_conf
        str(parsed["work_experience"]["value"]),          # Y- parsed_work_experience_json
        parsed["work_experience"]["confidence"],          # Z - parsed_work_experience_conf
        str(parsed["project_experience"]["value"]),       # AA - parsed_project_experience_json
        parsed["project_experience"]["confidence"],       # AB - parsed_project_experience_conf
        "",                                               # AC - full_extracted_text placeholder
    ]

    # Update the parser output columns
    sheet.values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!M{row_index}:AC{row_index}",
        valueInputOption="RAW",
        body={"values": [parser_row]},
    ).execute()

    # Update timestamp (A)
    sheet.values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!A{row_index}",
        valueInputOption="RAW",
        body={"values": [[_local_timestamp()]]},
    ).execute()

    print(f"[SHEETS] Updated parser output → row={row_index}, file_id={drive_file_id}")