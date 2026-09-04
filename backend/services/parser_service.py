"""Background parser workflow."""
import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from resolver.normalize import normalize_key
from resolver.resolver import resolve_extracted_profile
from resolver.schemas import ExtractedProfileV1
from services.resume_pdf_parser import parse_resume_pdf
from storage.drive_repo import download_file
from storage.sheets_repo import append_error_row, update_resume_in_sheet


RESOLVER_VERSION = "v1"
ALIASES_PATH = Path(__file__).resolve().parents[1] / "resolver" / "knowledge" / "aliases_v1.json"


def _load_alias_map(path: Optional[Path] = None) -> Tuple[Dict[str, str], str]:
    """
    Load Resolver V1 aliases for runtime use.

    This mirrors the benchmark-supported alias formats without depending on the
    benchmark harness as runtime architecture.
    """
    selected_path = path or ALIASES_PATH

    with open(selected_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    aliases_version = selected_path.stem

    if isinstance(raw, dict) and isinstance(raw.get("aliases"), dict):
        aliases_version = str(raw.get("version") or raw.get("aliases_version") or aliases_version)
        aliases = raw["aliases"]
    elif isinstance(raw, dict):
        aliases = raw
    elif isinstance(raw, list):
        aliases = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            alias = item.get("alias") or item.get("key") or item.get("raw")
            canonical = item.get("canonical") or item.get("canonical_id") or item.get("skill_id")
            if alias and canonical:
                aliases[str(alias)] = str(canonical)
    else:
        raise ValueError(f"Unsupported alias map format in {selected_path}")

    cleaned_aliases: Dict[str, str] = {
        normalize_key(str(alias)): str(canonical)
        for alias, canonical in aliases.items()
        if normalize_key(str(alias)) and str(canonical).strip()
    }

    return cleaned_aliases, aliases_version


def _list_field_value(parsed: Dict[str, Any], field_name: str) -> List[str]:
    value = parsed.get(field_name, {}).get("value", [])
    if isinstance(value, list):
        return [str(item) for item in value]
    if value:
        return [str(value)]
    return []


def _location_raw(parsed: Dict[str, Any]) -> str:
    locations = _list_field_value(parsed, "locations")
    return ", ".join(location.strip() for location in locations if location.strip())


def _add_resolver_output(parsed: Dict[str, Any], submission_id: str) -> None:
    """Enrich parsed output with Resolver V1 fields used by parser_results."""
    aliases, aliases_version = _load_alias_map()
    extracted = ExtractedProfileV1(
        submission_id=submission_id,
        skills=_list_field_value(parsed, "skills"),
        location_raw=_location_raw(parsed),
        meta={"source": "runtime_parser_service"},
    )

    resolved = resolve_extracted_profile(
        extracted,
        aliases,
        resolver_version=RESOLVER_VERSION,
        aliases_version=aliases_version,
    )

    parsed["resolver_version"] = resolved.meta.get("resolver_version", RESOLVER_VERSION)
    parsed["aliases_version"] = resolved.meta.get("aliases_version", aliases_version)
    parsed["resolved_skill_ids"] = list(resolved.resolved.skills)
    parsed["unknown_skills"] = list(resolved.unknowns.skills)
    parsed["resolver_coverage"] = round(resolved.stats.coverage, 3)


def parse_and_update(submission_id: str, drive_file_id: str) -> None:
    """Reconstruct parsing from the durable PDF and update parser_results."""
    try:
        print(f"[JOB] Parsing submission_id={submission_id} drive_file_id={drive_file_id} ...")
        parsed = parse_resume_pdf(download_file(drive_file_id))
        parsed["submission_id"] = submission_id
        parsed["drive_file_id"] = drive_file_id
    except Exception as e:
        print(f"[JOB] Error parsing submission_id={submission_id}: {e}")
        traceback.print_exc()
        _log_runtime_error(
            submission_id=submission_id,
            stage="parser",
            error_code="PARSER_FAILED",
            error_summary="Parser failed",
            exc=e,
        )
        return

    try:
        _add_resolver_output(parsed, submission_id)
    except Exception as e:
        print(f"[JOB] Resolver error submission_id={submission_id}: {e}")
        traceback.print_exc()
        _log_runtime_error(
            submission_id=submission_id,
            stage="resolver",
            error_code="RESOLVER_FAILED",
            error_summary="Resolver failed",
            exc=e,
        )

    try:
        update_resume_in_sheet(submission_id, parsed)
        print(f"[JOB] Parsed + updated sheet submission_id={submission_id}")
    except Exception as e:
        print(f"[JOB] Error writing parser result submission_id={submission_id}: {e}")
        traceback.print_exc()


def _log_runtime_error(
    *,
    submission_id: str,
    stage: str,
    error_code: str,
    error_summary: str,
    exc: Exception,
) -> None:
    try:
        append_error_row(
            submission_id=submission_id,
            stage=stage,
            error_code=error_code,
            error_summary=error_summary,
            error_details=_exception_details(exc),
        )
    except Exception as logging_exc:
        print(
            f"[JOB] Error logging {stage} failure submission_id={submission_id}: "
            f"{logging_exc}"
        )
        traceback.print_exc()


def _exception_details(exc: Exception) -> str:
    detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    return detail[:1000]
