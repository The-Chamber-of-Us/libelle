"""Offline #387 evidence probe; run with backend/.venv/bin/python from repo root.

Uses real PDF parsing, Resolver V1, repository serialization, snapshot composition,
and API response validation. Only Drive and Sheets I/O are replaced. Requires the
backend development dependencies and existing synthetic Sheet test helper.
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# Configuration imports can print diagnostics; do not include them in evidence.
with contextlib.redirect_stdout(io.StringIO()):
    from api.models.dashboard import ReviewerSubmissionSnapshot
    from benchmarks.layout_regression.generate import load_cases, render_pdf
    from resolver.resolver import resolve_extracted_profile
    from resolver.schemas import ExtractedProfileV1
    from services import parser_worker
    from services.dashboard_service import assemble_snapshot_records
    from services.parser_service import _add_resolver_output, _load_alias_map
    from services.ops_write_service import update_or_create_ops_workflow_state
    from services.pdf_text_extraction import extract_pdf_text_from_bytes
    from services.resume_pdf_parser import parse_resume_pdf
    from services.skill_section_projection import project_skill_sections
    from storage import sheets_repo
    from sheet_schema import build_row
    from tests.test_sheets_persistence_boundary import Sheet


def simple_pdf(text):
    return render_pdf({"blocks": [{"x": 50, "y": 50, "text": text, "size": 11}]})


def trace(name, pdf):
    extracted = extract_pdf_text_from_bytes(pdf)
    projection = project_skill_sections(extracted)
    canonical = parse_resume_pdf(pdf)
    worker = parser_worker.ParserWorker(parser_worker.ParserWorkerConfig(worker_id="offline"))
    with patch.object(parser_worker, "download_file", return_value=pdf):
        parsed = worker._run_parser({"drive_file_id": "synthetic"})
    aliases, version = _load_alias_map()
    resolver_input = ExtractedProfileV1(submission_id=name, skills=parsed["skills"]["value"],
                                        location_raw="", meta={"source": "runtime_parser_service"})
    resolved = resolve_extracted_profile(resolver_input, aliases, aliases_version=version)
    sheet = Sheet()
    with patch.object(sheets_repo, "_get_sheet", return_value=sheet), contextlib.redirect_stdout(io.StringIO()):
        sheets_repo.persist_parser_result_if_missing(submission_id=name, parser_run_id="offline-run", parsed=parsed)
        before_resolver = sheets_repo.load_parser_result_rows()[0]
        _add_resolver_output(parsed, name)
        sheets_repo.persist_resolver_output_for_parser_result(submission_id=name, parser_run_id="offline-run", parsed=parsed)
        row = sheets_repo.load_parser_result_rows()[0]
        sheet.rows["submissions"] = [build_row("submissions", {"submission_id": name, "resume_status": "uploaded"})]
        update_or_create_ops_workflow_state(name, {"status": "reviewed", "notes": "Do not rely on Python", "updated_by": "reviewer@example.test"})
        ops_rows = sheets_repo.load_ops_rows()
        events = sheets_repo.load_ops_event_rows()
        assert sheets_repo.load_parser_result_rows()[0] == row
    snapshot = assemble_snapshot_records(
        {name: {"submission_id": name, "resume_status": "uploaded", "skills_raw": "intake-only"}},
        [row], ops_rows, [],
    )[0]
    api = ReviewerSubmissionSnapshot.model_validate(snapshot).model_dump(mode="json")
    assert json.loads(row["parsed_skills_raw"]) == resolver_input.skills
    assert json.loads(api["resolved"]["resolved_skill_ids"]) == resolved.resolved.skills
    assert json.loads(api["resolved"]["unknown_skills"]) == resolved.unknowns.skills
    assert api["raw"]["skills_raw"] == "intake-only"
    return {"case": name, "extracted_text": extracted.text, "layout": projection.layout.name,
            "projected_text": projection.text, "canonical_skills": canonical["skills"],
            "worker_skills": parsed["skills"], "resolver_input": resolver_input.model_dump(),
            "resolver_result": resolved.model_dump(), "parser_only_row": before_resolver,
            "persisted_row": row, "ops_events": events, "api": api}


def main():
    cases = [("inline_literal", simple_pdf("SKILLS: Python")),
             ("explicit", simple_pdf("SKILLS:\nPython")),
             ("alias", simple_pdf("SKILLS\nPython3")),
             ("postgres", simple_pdf("SKILLS\nPostgres")),
             ("unknown", simple_pdf("SKILLS\nQuuxLang")),
             ("narrative", simple_pdf("SKILLS\nPython\nPROJECTS\nBuilt reports using Docker")),
             ("normalization", simple_pdf("SKILLS\nLanguages: Python (5 years), Python3, QuuxLang, quuxlang"))]
    cases.extend((case["id"], render_pdf(case)) for case in load_cases())
    results = [trace(name, pdf) for name, pdf in cases]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
