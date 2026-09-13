"""Semantic PDF parser regressions covered by benchmark source truth.

These tests intentionally assert content and section ownership, not PyMuPDF
block geometry, ordering, boundaries, or exact parser serialization.
"""

import json
import re
import unicodedata
from pathlib import Path

from services.pdf_text_extraction import extract_pdf_text_from_bytes
from services.resume_pdf_parser import parse_resume_pdf


BENCHMARKS_DIR = Path(__file__).resolve().parents[1] / "benchmarks"


def _pdf_bytes(resume_id):
    return (BENCHMARKS_DIR / "resumes" / f"{resume_id}.pdf").read_bytes()


def _golden_section(resume_id, heading):
    golden_path = BENCHMARKS_DIR / "golden_json" / f"{resume_id}.json"
    golden = json.loads(golden_path.read_text())
    return next(
        section for section in golden["sections"]
        if section["heading"].casefold() == heading.casefold()
    )


def _semantic_text(value):
    """Normalize harmless typography without imposing output formatting."""
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _contains(entries, expected):
    expected_text = _semantic_text(expected)
    return any(expected_text in _semantic_text(entry) for entry in entries)


def test_project_heavy_preserves_annotated_projects():
    project_entries = parse_resume_pdf(_pdf_bytes("project_heavy_01"))[
        "project_experience"
    ]["value"]
    annotated_projects = _golden_section("project_heavy_01", "Projects")["items"]

    for project in annotated_projects:
        assert _contains(project_entries, project["title"])

    young_adults_project = annotated_projects[0]
    assert _contains(project_entries, "Young Adults")
    for narrative in young_adults_project["bullets"]:
        assert _contains(project_entries, narrative)


def test_project_heavy_preserves_annotated_work_narrative_continuity():
    work_entries = parse_resume_pdf(_pdf_bytes("project_heavy_01"))[
        "work_experience"
    ]["value"]
    annotated_work = _golden_section("project_heavy_01", "Experience")["items"][0]

    # Each source bullet must remain continuous within one semantic parser entry;
    # line wrapping and the surrounding entry structure remain unconstrained.
    for narrative in annotated_work["bullets"]:
        assert _contains(work_entries, narrative)


def test_sparse_skill_source_contains_both_annotated_roles():
    extracted_text = extract_pdf_text_from_bytes(_pdf_bytes("sparse_skill_01")).text
    annotated_roles = _golden_section("sparse_skill_01", "EXPERIENCE")["items"]

    # This source-integrity sentinel prevents a parser assertion from becoming
    # vacuous if the committed fixture or extraction path loses either role.
    for role in annotated_roles:
        assert _semantic_text(role["title"]) in _semantic_text(extracted_text)


def test_sparse_skill_preserves_clinical_work_experience():
    work_entries = parse_resume_pdf(_pdf_bytes("sparse_skill_01"))[
        "work_experience"
    ]["value"]
    clinical_role = _golden_section("sparse_skill_01", "EXPERIENCE")["items"][0]

    assert work_entries
    assert _contains(work_entries, clinical_role["title"])
    assert _contains(work_entries, clinical_role["bullets"][0])


def test_multi_col_02_preserves_source_education():
    education_entries = parse_resume_pdf(_pdf_bytes("multi_col_02"))["education"][
        "value"
    ]

    # These facts are unambiguous in the committed PDF. This older benchmark's
    # golden only annotates skills and location, so no entry grouping is assumed.
    for expected in (
        "B.Sc. Environmental Science",
        "Institute of Apllied Science, MO",
        "2016 - 2020",
    ):
        assert _contains(education_entries, expected)


def test_high_signal_02_preserves_source_project_identities():
    project_entries = parse_resume_pdf(_pdf_bytes("high_signal_02"))[
        "project_experience"
    ]["value"]

    # Both titles are unambiguous in the committed PDF. A title may share an
    # entry with its own content, but must not be absorbed into prior content.
    for title in ("Data Ingestion Platform", "Task Management Web Application"):
        title_text = _semantic_text(title)
        assert any(
            _semantic_text(entry).startswith(title_text)
            for entry in project_entries
        )
