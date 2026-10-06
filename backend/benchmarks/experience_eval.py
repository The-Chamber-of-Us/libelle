"""Exploratory V2 experience adapters. No formal matching or PRF scoring."""
from __future__ import annotations

import re
import unicodedata
from typing import Literal, TypedDict

from .v2_evaluation.validate_v2_goldens import validate_v2_sections


class ExperienceEntryV1(TypedDict):
    entry_type: Literal["work", "project", "unknown"]
    title: str | None
    meta: str | None
    subtitle: str | None
    bullets: list[str]
    raw_text: str
    source_section: str | None


WORK_SECTION_HEADINGS = {
    "experience", "work experience", "professional experience", "employment",
    "employment history", "relevant experience", "job experience",
    "career history", "work history",
    "research experience", "engineering experience", "professional background",
}
PROJECT_SECTION_HEADINGS = {
    "projects", "project experience", "technical projects", "selected projects",
    "additional projects",
    "portfolio projects", "project highlights", "more projects",
    "machine learning projects", "analytics projects at work",
}


def normalize_heading(heading: str) -> str:
    return " ".join(heading.strip().lower().rstrip(":").replace("&", "and").split())


def section_type(heading: str) -> str:
    heading = normalize_heading(heading)
    if heading in WORK_SECTION_HEADINGS:
        return "work"
    if heading in PROJECT_SECTION_HEADINGS:
        return "project"
    return "unknown"


def flatten_section_item(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        raise ValueError("section item must be a string or object")
    fields = [item.get(key) for key in ("title", "meta", "subtitle")]
    bullets = item.get("bullets", [])
    if not isinstance(bullets, list) or any(not isinstance(b, str) for b in bullets):
        raise ValueError("bullets must be a string list")
    if any(value is not None and not isinstance(value, str) for value in fields):
        raise ValueError("structured fields must be strings or null")
    return "\n".join(value for value in fields + bullets if value)


def _entry(item: object, kind: str, source: str | None) -> ExperienceEntryV1:
    raw = flatten_section_item(item)
    if not raw.strip():
        raise ValueError("experience entry must contain non-empty text")
    fields = item if isinstance(item, dict) else {}
    return dict(entry_type=kind, title=fields.get("title"), meta=fields.get("meta"),
                subtitle=fields.get("subtitle"), bullets=list(fields.get("bullets", [])),
                raw_text=raw, source_section=source)


def extract_expected_experience_entries(golden: dict) -> list[ExperienceEntryV1]:
    if not isinstance(golden, dict):
        raise ValueError("V2 golden must be an object")
    issues = validate_v2_sections(golden.get("sections"), fixture_id=golden.get("resume_id", "experience"))
    if issues:
        raise ValueError("Invalid V2 sections:\n" + "\n".join(issue.format() for issue in issues))
    entries = []
    for section in golden["sections"]:
        heading = section["heading"]
        kind = section_type(heading)
        for index, item in enumerate(section["items"]):
            if not flatten_section_item(item).strip():
                raise ValueError(f"{heading}.items[{index}]: section item must contain non-empty text")
        if kind != "unknown":
            entries.extend(_entry(item, kind, heading) for item in section["items"])
    return entries


def extract_predicted_experience_entries(parsed: dict) -> list[ExperienceEntryV1]:
    if not isinstance(parsed, dict):
        raise ValueError("parser output must be an object")
    entries = []
    for kind in ("work", "project"):
        field = f"{kind}_experience"
        if field not in parsed:
            raise ValueError(f"missing required prediction field: {field}")
        value = parsed[field]
        if isinstance(value, dict):
            if "value" not in value:
                raise ValueError(f"{field} wrapper is missing value")
            value = value["value"]
        if not isinstance(value, list):
            raise ValueError(f"{kind}_experience must contain an entry list")
        # A parser field identifies the type, not the original section heading.
        for index, item in enumerate(value):
            try:
                if isinstance(item, dict):
                    issues = validate_v2_sections([{"heading": field, "items": [item]}], fixture_id="prediction")
                    if issues:
                        raise ValueError("; ".join(issue.format() for issue in issues))
                entries.append(_entry(item, kind, None))
            except ValueError as exc:
                raise ValueError(f"{field}[{index}]: {exc}") from exc
    return entries


def normalize_entry_text(text: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def _tokens(text: str) -> set[str]:
    return set(normalize_entry_text(text).split())


def rough_text_overlap(expected_entry: dict, predicted_entry: dict) -> float:
    """Unique-token Jaccard; empty vs empty is zero, not a successful match."""
    a, b = _tokens(expected_entry["raw_text"]), _tokens(predicted_entry["raw_text"])
    return len(a & b) / len(a | b) if a | b else 0.0


def text_coverage(expected_text: str, predicted_text: str) -> float | None:
    """Expected-token coverage; null means no annotated tokens to inspect."""
    a = _tokens(expected_text)
    return len(a & _tokens(predicted_text)) / len(a) if a else None


def compare_experience_entries(expected: list[dict], predicted: list[dict]) -> dict:
    result = {"notes": [], "entry_diagnostics": []}
    for kind in ("work", "project"):
        gold = [e for e in expected if e["entry_type"] == kind]
        pred = [p for p in predicted if p["entry_type"] == kind]
        result[f"expected_{kind}_count"] = len(gold)
        result[f"predicted_{kind}_count"] = len(pred)
        if gold and not pred:
            result["notes"].append(f"{kind} section missed")
        elif len(gold) > len(pred):
            result["notes"].append(f"possible merge or missing {kind} entries")
        elif len(pred) > len(gold):
            result["notes"].append(f"extra {kind} output; possible split or section bleed")
        best_scores = []
        combined = "\n".join(p["raw_text"] for p in pred)
        for entry in gold:
            scores = [rough_text_overlap(entry, p) for p in pred]
            best = max(scores, default=0.0)
            best_scores.append(best)
            other = [rough_text_overlap(entry, p) for p in predicted if p["entry_type"] != kind]
            if max(other, default=0.0) >= 0.25 and max(other) > best + 0.15:
                result["notes"].append("possible work/project confusion")
            result["entry_diagnostics"].append({
                "entry_type": kind, "title": entry["title"],
                "source_section": entry["source_section"],
                "best_predicted_index": scores.index(best) if pred else None,
                "best_jaccard": round(best, 4),
                "raw_token_coverage_across_fragments": text_coverage(entry["raw_text"], combined),
                "field_token_coverage_across_fragments": {
                    field: text_coverage(entry[field] or "", combined)
                    for field in ("title", "meta", "subtitle")},
                "bullet_token_coverage_across_fragments": [text_coverage(b, combined) for b in entry["bullets"]],
            })
        result[f"best_{kind}_overlap"] = round(sum(best_scores) / len(best_scores), 4) if best_scores else None
        if best_scores and min(best_scores) < 0.25:
            result["notes"].append(f"low {kind} text overlap")
    if any(p["title"] is None for p in predicted):
        result["notes"].append("parser output shape gap: raw strings lack field and section ownership")
    result["notes"] = sorted(set(result["notes"]))
    return result
