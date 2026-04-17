"""Background parser workflow."""
import traceback

from parser import parse_resume
from storage.sheets_repo import update_resume_in_sheet


def parse_and_update(drive_file_id: str, pre_extracted_text: str = "") -> None:
    """Parse the extracted resume text and update the parser_results row in Sheets."""
    try:
        print(f"[JOB] Parsing drive_file_id={drive_file_id} ...")
        parsed = parse_resume(pre_extracted_text or "")
        parsed["drive_file_id"] = drive_file_id
        update_resume_in_sheet(parsed)
        print(f"[JOB] Parsed + updated sheet drive_file_id={drive_file_id}")
    except Exception as e:
        print(f"[JOB] Error parsing drive_file_id={drive_file_id}: {e}")
        traceback.print_exc()
