"""Shared helpers for the experimental V2 corpus evaluator."""

from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


V2_TOP_LEVEL_FIELDS = {
    "resume_id",
    "source_persona",
    "persona",
    "name",
    "email",
    "phone",
    "location",
    "links",
    "skills",
    "notes",
    "sections",
}

STRUCTURED_ITEM_FIELDS = {"title", "meta", "subtitle", "bullets"}


@dataclass
class ValidationIssue:
    fixture_id: str
    field: str
    message: str
    severity: str = "error"

    def format(self) -> str:
        return f"Fixture: {self.fixture_id}\n{self.field}: {self.message}"


@dataclass
class FixtureRecord:
    fixture_id: str
    pdf_path: Optional[Path]
    golden_path: Optional[Path]
    schema_version: str
    golden: Optional[Dict[str, Any]] = None
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


def load_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"
    except OSError as exc:
        return None, f"could not read JSON: {exc}"

    if not isinstance(data, dict):
        return None, "golden root must be a JSON object"
    return data, None


def detect_schema_version(golden: Optional[Dict[str, Any]]) -> str:
    if not golden:
        return "unknown"
    if "resume_id" in golden or "sections" in golden:
        return "v2"
    return "v1_or_unknown"


def relative_fixture_map(root: Path, suffix: str) -> Dict[str, Path]:
    if not root.exists():
        return {}
    paths = sorted(root.rglob(f"*{suffix}"))
    return {path.relative_to(root).with_suffix("").as_posix(): path for path in paths}


def display_fixture_id(golden: Optional[Dict[str, Any]], fallback: str) -> str:
    if golden:
        value = golden.get("resume_id") or golden.get("submission_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return Path(fallback).name


def normalize_for_exact(value: Any) -> str:
    """Deterministic baseline normalization: case, punctuation, and whitespace."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def dedupe_normalized(values: Iterable[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        normalized = normalize_for_exact(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def sections_by_heading(sections: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for section in sections:
        heading = normalize_for_exact(section.get("heading"))
        if heading:
            grouped.setdefault(heading, []).append(section)
    return grouped


def structured_items(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in section.get("items", []) if isinstance(item, dict)]
