"""Validate V2 golden JSON fixtures without touching the V1 benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from .models import (
    STRUCTURED_ITEM_FIELDS,
    V2_TOP_LEVEL_FIELDS,
    FixtureRecord,
    ValidationIssue,
    detect_schema_version,
    display_fixture_id,
    load_json,
    relative_fixture_map,
)


def _issue(fixture_id: str, field: str, message: str) -> ValidationIssue:
    return ValidationIssue(fixture_id=fixture_id, field=field, message=message)


def _validate_optional_string(
    issues: List[ValidationIssue],
    fixture_id: str,
    data: Dict[str, Any],
    field: str,
    *,
    nullable: bool,
) -> None:
    value = data.get(field)
    if value is None and nullable:
        return
    if not isinstance(value, str):
        issues.append(_issue(fixture_id, field, f"expected string{' or null' if nullable else ''}"))


def _validate_location(
    issues: List[ValidationIssue], fixture_id: str, value: Any
) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        issues.append(_issue(fixture_id, "location", "expected object or null"))
        return
    for key in ("city", "country", "raw"):
        if key not in value:
            issues.append(_issue(fixture_id, f"location.{key}", "missing required location field"))
        elif not isinstance(value[key], str):
            issues.append(_issue(fixture_id, f"location.{key}", "expected string"))


def _validate_string_array(
    issues: List[ValidationIssue], fixture_id: str, value: Any, field: str
) -> None:
    if not isinstance(value, list):
        issues.append(_issue(fixture_id, field, "expected array"))
        return
    for i, item in enumerate(value):
        if not isinstance(item, str):
            issues.append(_issue(fixture_id, f"{field}[{i}]", "expected string item"))


def _validate_sections(
    issues: List[ValidationIssue], fixture_id: str, sections: Any
) -> None:
    if not isinstance(sections, list):
        issues.append(_issue(fixture_id, "sections", "expected array of section objects"))
        return

    for section_index, section in enumerate(sections):
        prefix = f"sections[{section_index}]"
        if not isinstance(section, dict):
            issues.append(_issue(fixture_id, prefix, "expected section object"))
            continue

        heading = section.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            issues.append(_issue(fixture_id, f"{prefix}.heading", "missing non-empty heading string"))

        if "items" not in section:
            issues.append(_issue(fixture_id, f"{prefix}.items", "missing required items array"))
            continue
        items = section["items"]
        if not isinstance(items, list):
            issues.append(_issue(fixture_id, f"{prefix}.items", "expected array"))
            continue

        for item_index, item in enumerate(items):
            item_prefix = f"{prefix}.items[{item_index}]"
            if isinstance(item, str):
                continue
            if not isinstance(item, dict):
                issues.append(_issue(fixture_id, item_prefix, "expected string or structured object"))
                continue

            missing = sorted(STRUCTURED_ITEM_FIELDS - set(item))
            for key in missing:
                issues.append(_issue(fixture_id, f"{item_prefix}.{key}", "missing required structured entry field"))

            title = item.get("title")
            if not isinstance(title, str) or not title.strip():
                issues.append(_issue(fixture_id, f"{item_prefix}.title", "expected non-empty string"))

            for key in ("meta", "subtitle"):
                value = item.get(key)
                if value is not None and not isinstance(value, str):
                    issues.append(_issue(fixture_id, f"{item_prefix}.{key}", "expected string or null"))

            bullets = item.get("bullets")
            if not isinstance(bullets, list):
                issues.append(_issue(fixture_id, f"{item_prefix}.bullets", "expected array of strings"))
            else:
                for bullet_index, bullet in enumerate(bullets):
                    if not isinstance(bullet, str):
                        issues.append(_issue(fixture_id, f"{item_prefix}.bullets[{bullet_index}]", "expected string"))


def validate_v2_golden(
    golden: Dict[str, Any],
    *,
    fixture_key: str,
    golden_path: Path,
) -> List[ValidationIssue]:
    fixture_id = display_fixture_id(golden, fixture_key)
    issues: List[ValidationIssue] = []

    missing_fields = sorted(V2_TOP_LEVEL_FIELDS - set(golden))
    for field in missing_fields:
        issues.append(_issue(fixture_id, field, "missing required top-level field"))

    extra_id = golden.get("resume_id")
    if not isinstance(extra_id, str) or not extra_id.strip():
        issues.append(_issue(fixture_id, "resume_id", "expected non-empty string"))
    else:
        expected_stem = golden_path.stem
        if extra_id != expected_stem:
            issues.append(
                _issue(
                    fixture_id,
                    "resume_id",
                    f"does not match filename stem '{expected_stem}'",
                )
            )

    for field in ("source_persona", "persona"):
        _validate_optional_string(issues, fixture_id, golden, field, nullable=False)
    for field in ("name", "email", "phone"):
        _validate_optional_string(issues, fixture_id, golden, field, nullable=True)

    _validate_location(issues, fixture_id, golden.get("location"))
    _validate_string_array(issues, fixture_id, golden.get("links"), "links")
    _validate_string_array(issues, fixture_id, golden.get("skills"), "skills")

    notes = golden.get("notes")
    if notes is not None and not isinstance(notes, (str, dict)):
        issues.append(_issue(fixture_id, "notes", "expected string, object, or null"))

    _validate_sections(issues, fixture_id, golden.get("sections"))
    return issues


def discover_and_validate(pdf_dir: Path, golden_dir: Path, *, include_v1: bool = False) -> List[FixtureRecord]:
    pdfs = relative_fixture_map(pdf_dir, ".pdf")
    goldens = relative_fixture_map(golden_dir, ".json")
    keys = sorted(set(pdfs) | set(goldens))
    records: List[FixtureRecord] = []
    seen_resume_ids: Dict[str, str] = {}

    if not keys:
        records.append(
            FixtureRecord(
                fixture_id="<none>",
                pdf_path=None,
                golden_path=None,
                schema_version="unknown",
                issues=[_issue("<none>", "input", "no PDF or JSON fixtures found")],
            )
        )
        return records

    for key in keys:
        pdf_path = pdfs.get(key)
        golden_path = goldens.get(key)
        issues: List[ValidationIssue] = []
        golden: Optional[Dict[str, Any]] = None

        fixture_id = Path(key).name
        if pdf_path is None:
            issues.append(_issue(fixture_id, "pdf", f"missing PDF pair for golden '{key}.json'"))
        if golden_path is None:
            issues.append(_issue(fixture_id, "golden", f"missing JSON pair for PDF '{key}.pdf'"))

        if golden_path is not None:
            golden, error = load_json(golden_path)
            if error:
                issues.append(_issue(fixture_id, "golden", error))

        schema_version = detect_schema_version(golden)
        fixture_id = display_fixture_id(golden, key)

        if golden is not None and schema_version == "v2":
            issues.extend(validate_v2_golden(golden, fixture_key=key, golden_path=golden_path or Path(key)))
            resume_id = golden.get("resume_id")
            if isinstance(resume_id, str):
                if resume_id in seen_resume_ids:
                    issues.append(
                        _issue(
                            fixture_id,
                            "resume_id",
                            f"duplicate ID also used by fixture '{seen_resume_ids[resume_id]}'",
                        )
                    )
                else:
                    seen_resume_ids[resume_id] = key
        elif golden is not None and not include_v1:
            issues.append(
                ValidationIssue(
                    fixture_id=fixture_id,
                    field="schema",
                    message="skipped: fixture is not V2-shaped",
                    severity="info",
                )
            )

        records.append(
            FixtureRecord(
                fixture_id=fixture_id,
                pdf_path=pdf_path,
                golden_path=golden_path,
                schema_version=schema_version,
                golden=golden,
                issues=issues,
            )
        )

    return records


def records_to_summary(records: Iterable[FixtureRecord]) -> Dict[str, Any]:
    fixtures = []
    total_errors = 0
    for record in records:
        errors = [issue for issue in record.issues if issue.severity == "error"]
        if errors:
            validation_status = "invalid"
        elif record.schema_version != "v2":
            validation_status = "skipped"
        else:
            validation_status = "valid"
        total_errors += len(errors)
        fixtures.append(
            {
                "fixture_id": record.fixture_id,
                "schema_version": record.schema_version,
                "validation_status": validation_status,
                "failure_count": len(errors),
                "issues": [
                    {
                        "severity": issue.severity,
                        "field": issue.field,
                        "message": issue.message,
                    }
                    for issue in record.issues
                ],
            }
        )
    return {
        "validation_status": "valid" if total_errors == 0 else "invalid",
        "failure_count": total_errors,
        "fixtures": fixtures,
    }


def _write_summary(path: Optional[Path], summary: Dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", required=True, type=Path)
    parser.add_argument("--golden-dir", required=True, type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--include-v1", action="store_true", help="include V1-shaped fixtures as non-deep-validated records")
    args = parser.parse_args(argv)

    records = discover_and_validate(args.pdf_dir, args.golden_dir, include_v1=args.include_v1)
    summary = records_to_summary(records)
    _write_summary(args.summary_out, summary)

    for record in records:
        for issue in record.issues:
            print(issue.format())
            print()

    print(
        f"Validated {len(summary['fixtures'])} fixture records; "
        f"errors: {summary['failure_count']}"
    )
    return 1 if summary["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
