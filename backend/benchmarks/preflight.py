"""Corpus preflight validation for the V1 benchmark runner (scripts/benchmark.py).

Validates the resume PDF / golden JSON corpus for internal consistency
before any benchmark scoring begins (#344). Kept separate from scoring so
additional corpus checks can be added here without touching the scoring
path.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .v2_evaluation.validate_v2_goldens import validate_v2_golden


@dataclass
class PreflightIssue:
    fixture_id: str
    message: str
    severity: str = "error"  # "error" or "warning"
    expected: Optional[str] = None
    found: Optional[str] = None

    def format(self) -> str:
        lines = [f"Fixture: {self.fixture_id}", "", self.message]
        if self.expected is not None or self.found is not None:
            if self.expected is not None:
                lines.append(f"Expected ID: {self.expected}")
            if self.found is not None:
                lines.append(f"Found ID: {self.found}")
        return "\n".join(lines)


@dataclass
class PreflightResult:
    pdf_count: int
    golden_count: int
    matched_count: int
    schema_versions: Counter
    issues: List[PreflightIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def _load_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"
    except (OSError, UnicodeError) as exc:
        return None, f"could not read JSON: {exc}"

    if not isinstance(data, dict):
        return None, "golden root must be a JSON object"
    return data, None


def _golden_id(golden: Dict[str, Any]) -> Optional[str]:
    for key in ("submission_id", "resume_id"):
        value = golden.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _schema_version(golden: Dict[str, Any]) -> str:
    if "resume_id" in golden or "sections" in golden:
        return "v2"
    if "submission_id" in golden and "skills" in golden:
        return "v1"
    return "unsupported"


def _observed_field(golden: Dict[str, Any], field: str) -> str:
    """Describe the offending field, including missing parents, for diagnostics."""
    value: Any = golden
    for part in field.replace("[", ".").replace("]", "").split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return f"missing or inaccessible field ({field})"
    return repr(value)


def run_preflight(
    pdf_dir: Path, golden_dir: Path, *, allow_missing: bool = False
) -> PreflightResult:
    """Validate a benchmark corpus before scoring begins.

    Mirrors the non-recursive discovery scripts/benchmark.py already uses
    (flat `*.pdf` / `*.json` globs), so this validates exactly the corpus
    the benchmark run itself will see.
    """
    pdfs = {p.stem: p for p in sorted(pdf_dir.glob("*.pdf"))} if pdf_dir.exists() else {}
    goldens = {p.stem: p for p in sorted(golden_dir.glob("*.json"))} if golden_dir.exists() else {}

    schema_versions: Counter = Counter()

    if not pdfs and not goldens:
        issues = [
            PreflightIssue(
                fixture_id="<corpus>",
                message=f"empty benchmark corpus: no PDFs in {pdf_dir} and no golden JSON in {golden_dir}",
            )
        ]
        return PreflightResult(0, 0, 0, schema_versions, issues)

    issues: List[PreflightIssue] = []
    seen_ids: Dict[str, str] = {}
    matched_count = 0
    missing_severity = "warning" if allow_missing else "error"

    for stem in sorted(set(pdfs) | set(goldens)):
        pdf_path = pdfs.get(stem)
        golden_path = goldens.get(stem)

        if pdf_path is None:
            issues.append(
                PreflightIssue(
                    fixture_id=stem,
                    message=f"missing PDF for golden JSON '{stem}.json'",
                    severity=missing_severity,
                )
            )
        if golden_path is None:
            issues.append(
                PreflightIssue(
                    fixture_id=stem,
                    message=f"missing golden JSON for PDF '{stem}.pdf'",
                    severity=missing_severity,
                )
            )
        if golden_path is None:
            continue

        if pdf_path is not None:
            matched_count += 1

        golden, error = _load_json(golden_path)
        if error:
            issues.append(PreflightIssue(fixture_id=stem, message=error))
            continue

        internal_id = _golden_id(golden)
        if internal_id is None:
            issues.append(
                PreflightIssue(
                    fixture_id=stem,
                    message="golden JSON is missing a 'submission_id' or 'resume_id' field",
                )
            )
        else:
            if internal_id != stem:
                issues.append(
                    PreflightIssue(
                        fixture_id=stem,
                        message="internal ID does not match filename",
                        expected=stem,
                        found=internal_id,
                    )
                )
            if internal_id in seen_ids:
                issues.append(
                    PreflightIssue(
                        fixture_id=stem,
                        message=f"duplicate fixture ID also used by '{seen_ids[internal_id]}'",
                    )
                )
            else:
                seen_ids[internal_id] = stem

        version = _schema_version(golden)
        schema_versions[version] += 1
        if "schema_version" in golden:
            declared = golden["schema_version"]
            if not isinstance(declared, str) or declared not in ("v1", "v2") or declared != version:
                issues.append(PreflightIssue(
                    fixture_id=stem,
                    message=f"schema_version: expected '{version}' matching annotation shape "
                            f"(supported versions: v1, v2); observed {declared!r}",
                ))
        if "submission_id" in golden and "resume_id" in golden:
            issues.append(PreflightIssue(
                fixture_id=stem,
                message="ambiguous schema identity: expected one of submission_id (V1) or "
                        "resume_id (V2); observed both fields",
            ))
        if version == "unsupported":
            issues.append(
                PreflightIssue(
                    fixture_id=stem,
                    message="unsupported or unrecognized golden JSON schema shape",
                )
            )
        elif version == "v1":
            if not isinstance(golden.get("skills"), list):
                issues.append(PreflightIssue(fixture_id=stem, message="missing required 'skills' array"))
            if not isinstance(golden.get("location"), dict):
                issues.append(PreflightIssue(fixture_id=stem, message="missing required 'location' object"))

        elif version == "v2":
            for issue in validate_v2_golden(golden, fixture_key=stem, golden_path=golden_path):
                # Keep the filename identity even when the annotation ID is malformed.
                issues.append(PreflightIssue(
                    fixture_id=stem,
                    message=f"{issue.field}: {issue.message}; observed {_observed_field(golden, issue.field)}",
                ))

    known_versions = [v for v in schema_versions if v != "unsupported"]
    if len(known_versions) > 1:
        breakdown = ", ".join(f"{v}={schema_versions[v]}" for v in sorted(schema_versions))
        issues.append(
            PreflightIssue(
                fixture_id="<corpus>",
                message=f"corpus contains mixed schema versions ({breakdown})",
                severity="warning",
            )
        )

    return PreflightResult(len(pdfs), len(goldens), matched_count, schema_versions, issues)


def format_preflight_report(result: PreflightResult) -> str:
    """Render the preflight result in the CLI format described in #344."""
    if result.ok:
        lines = [
            "Benchmark preflight",
            "",
            f"✓ {result.pdf_count} PDFs found",
            f"✓ {result.golden_count} golden JSON fixtures found",
            "✓ IDs match filenames",
            "✓ No duplicate fixture IDs",
            "✓ Schemas validated",
        ]
        for warning in result.warnings:
            lines.append(f"! {warning.fixture_id}: {warning.message}")
        lines.append("")
        lines.append("Starting benchmark...")
        return "\n".join(lines)

    lines = ["Benchmark aborted", ""]
    for issue in result.errors:
        lines.append(issue.format())
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
