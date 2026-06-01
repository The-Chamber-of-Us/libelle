"""Background parser workflow."""
import traceback

from parser import parse_resume
from storage.sheets_repo import update_resume_in_sheet


def parse_and_update(submission_id: str, drive_file_id: str, pre_extracted_text: str) -> None:
    """Parse the extracted resume text and update the parser_results row in Sheets."""
    try:
        print(f"[JOB] Parsing submission_id={submission_id} drive_file_id={drive_file_id} ...")
        parsed = parse_resume(pre_extracted_text or "")
        parsed["submission_id"] = submission_id
        parsed["drive_file_id"] = drive_file_id
        update_resume_in_sheet(submission_id, parsed)
        print(f"[JOB] Parsed + updated sheet submission_id={submission_id}")
    except Exception as e:
        print(f"[JOB] Error parsing submission_id={submission_id}: {e}")
        traceback.print_exc()
