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
def write_base_row(resume_id: int, drive_file_id: str, drive_file_url: Optional[str] = None, submission_id: Optional[str] = None, ui_data: Optional[Dict[str, Union[str, List[str], bool]]] = None) -> None:
    """
    Appends a base row with timestamp, file_id, and file_url into columns A–K.
    """
    ts = _local_timestamp()
    drive_url = drive_file_url or _drive_link(drive_file_id)
    # Prepare a 60-column row with only A, J, K filled
    row = [""] * 60
    row[0] = ts  # Timestamp
    row[9] = drive_file_id  # resume_file_id
    row[10] = drive_url  # resume_file_url
    
    #Writing UI Data To Row
    row[1] = ui_data["name"]    #Full Name
    row[2] = ui_data["email"]    #Email
    row[3] = ui_data["location"]   #Location
    row[4] = ui_data["areas"]     #Areas of Interest
    row[5] = ui_data["capacity"]    #Availability
    row[6] = ui_data["experience"]   #Experience level
    row[7] = ui_data["linkedin"]    #LinkedIn URL
    row[8] = ui_data["github"]     #GitHub URL
    row[11] = ui_data["motivation"]    #Motivation

    sheet.values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{SHEET_NAME}!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    print(f"[SHEETS] Base row appended → drive_file_id={drive_file_id}")


# ---------- Update Parsed Data ----------
def update_resume_in_sheet(resume_id: int, parsed: Dict[str, Any]) -> None:
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

    # Construct row aligned to columns L–AB (27 columns)
    parser_row = [
        "parsed",                                         # L - parser_status
        overall_conf,                                     # M - parser_confidence_overall
        parsed["name"]["value"],                          # N - parsed_name
        parsed["name"]["confidence"],                     # O - parsed_name_conf
        ", ".join(parsed["emails"]["value"]),             # P - parsed_email
        parsed["emails"]["confidence"],                   # Q - parsed_email_conf
        ", ".join(parsed["locations"]["value"]),          # R - parsed_location
        parsed["locations"]["confidence"],                # S - parsed_location_conf
        str(parsed["education"]["value"]),                # T - parsed_education
        parsed["education"]["confidence"],                # U - parsed_education_conf
        str(parsed["skills"]["value"]),                   # V - parsed_skills_json
        parsed["skills"]["confidence"],                   # W - parsed_skills_conf
        str(parsed["work_experience"]["value"]),          # X - parsed_work_experience_json
        parsed["work_experience"]["confidence"],          # Y - parsed_work_experience_conf
        str(parsed["project_experience"]["value"]),       # Z - parsed_project_experience_json
        parsed["project_experience"]["confidence"],       # AA - parsed_project_experience_conf
        "",                                               # AB - full_extracted_text placeholder
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
