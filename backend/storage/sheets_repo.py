import threading
from typing import Optional, Dict, Union, Any, List
from datetime import datetime, timezone
from googleapiclient.discovery import build

from config import GOOGLE_SHEET_ID, SHEET_NAME
from storage._auth import load_service_account_creds, SHEETS_SCOPES

if not GOOGLE_SHEET_ID:
    raise RuntimeError("GOOGLE_SHEET_ID not set in .env")

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


# ---------- Helpers ----------
def _drive_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view?usp=drive_link"


def _local_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%m-%d-%Y %H:%M:%S %Z")


# ---------- Write Base Row ----------
def write_base_row(drive_file_id: str, drive_file_url: Optional[str] = None, submission_id: Optional[str] = None, ui_data: Optional[Dict[str, Union[str, List[str], bool]]] = None) -> None:
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
    row[11] = ui_data["motivation"]    #Motivation (column L)

    _get_sheet().values().append(
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

    sheet = _get_sheet()

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
