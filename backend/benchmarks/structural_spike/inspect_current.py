"""Reproduce #301 traces using only the checked-in benchmark fixtures.

Run from the repository root with the backend Python environment. This is an
observation tool, not a structure scorer or an alternative parser.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from parser import (  # noqa: E402
    _is_section_header,
    _is_skill_start_header,
    _is_skill_stop_header,
    extract_project_experience,
    extract_work_experience,
)
from services.pdf_text_extraction import extract_pdf_text_from_bytes  # noqa: E402
from services.resume_pdf_parser import parse_resume_pdf  # noqa: E402
from services.skill_section_projection import project_skill_sections  # noqa: E402


CASES = (
    "dense_skills_01", "dense_skills_02", "multi_col_02",
    "header_contact_01", "embed_link_01", "non_usa_01",
    "v2/resume_201", "v2/resume_202", "v2/resume_203", "v2/resume_204",
)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", type=Path, required=True)
    args = cli.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    base = ROOT / "backend/benchmarks"
    for case in CASES:
        pdf = base / "resumes" / f"{case}.pdf"
        golden_path = base / "golden_json" / f"{case}.json"
        pdf_bytes = pdf.read_bytes()
        golden_bytes = golden_path.read_bytes()
        golden = json.loads(golden_bytes)
        extracted = extract_pdf_text_from_bytes(pdf_bytes)
        projection = project_skill_sections(extracted)
        parsed = parse_resume_pdf(pdf_bytes)
        lines = extracted.text.splitlines()
        headings = [s["heading"] for s in golden.get("sections", [])]
        # Omit the initial identity/contact block; preserve original line indexes.
        first_section = next(
            (i for i, line in enumerate(lines)
             if line.strip() in headings or _is_section_header(line)), len(lines)
        )
        _, _, work_end = extract_work_experience(extracted.text)
        trace = {
            "git_commit": commit,
            "pdf": str(pdf.relative_to(ROOT)),
            "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "golden": str(golden_path.relative_to(ROOT)),
            "golden_sha256": hashlib.sha256(golden_bytes).hexdigest(),
            "layout": projection.layout.name,
            "section_lines": [
                {"index": i, "text": line}
                for i, line in enumerate(lines) if i >= first_section
            ],
            "golden_headings": [
                {"heading": h, "general_header": _is_section_header(h),
                 "skill_start": _is_skill_start_header(h),
                 "skill_stop": _is_skill_stop_header(h)} for h in headings
            ],
            "projected_skill_text": projection.text,
            "parsed": {k: parsed[k] for k in (
                "skills", "locations", "education", "work_experience",
                "project_experience",
            )},
            "work_end_index": work_end,
            "work_stop_line": lines[work_end] if work_end < len(lines) else None,
            # Diagnostic only: isolates the production work-end slicing effect.
            "projects_from_document_start": extract_project_experience(
                extracted.text, 0
            )[0],
        }
        (args.out / f"{Path(case).name}.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2) + "\n"
        )
    print(f"Wrote {len(CASES)} fixture traces to {args.out}")


if __name__ == "__main__":
    main()
