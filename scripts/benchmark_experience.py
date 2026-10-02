#!/usr/bin/env python3
"""Evaluate the public synthetic V2 sample; retain auditable parser traces."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from benchmarks.experience_eval import (
    compare_experience_entries, extract_expected_experience_entries,
    extract_predicted_experience_entries, flatten_section_item, section_type, text_coverage,
)
from parser import parse_resume, extract_work_experience, extract_project_experience
from services.pdf_text_extraction import extract_text_from_pdf_path


def run(pdf_dir: Path, golden_dir: Path, out: Path) -> dict:
    goldens = {p.stem: p for p in golden_dir.glob("*.json")}
    pdfs = {p.stem: p for p in pdf_dir.glob("*.pdf")}
    if not goldens or goldens.keys() != pdfs.keys():
        raise ValueError("Expected nonempty, exactly paired PDF/V2 golden inputs")
    rows, traces = [], []
    for name in sorted(goldens):
        golden = json.loads(goldens[name].read_text())
        text = extract_text_from_pdf_path(pdfs[name])
        parsed = parse_resume(text)
        expected = extract_expected_experience_entries(golden)
        predicted = extract_predicted_experience_entries(parsed)
        comparison = compare_experience_entries(expected, predicted)
        _, _, work_end = extract_work_experience(text)
        projects_zero, _ = extract_project_experience(text, 0)
        # Diagnostic only: do not substitute counterfactual output for predictions.
        comparison["work_end_index"] = work_end
        comparison["project_count_start_zero"] = len(projects_zero)
        if projects_zero != parsed["project_experience"]["value"]:
            comparison["notes"].append("project extraction differs with start_index=0")
        combined_projects = "\n".join(e["raw_text"] for e in predicted if e["entry_type"] == "project")
        for entry in expected:
            if entry["source_section"].strip().upper() == "ADDITIONAL PROJECTS":
                if (text_coverage(entry["raw_text"], combined_projects) or 0) < 0.5:
                    comparison["notes"].append("additional projects low coverage or missed")
                    break
        excluded_sections = [s["heading"] for s in golden["sections"] if section_type(s["heading"]) == "unknown"]
        bleed = []
        combined_pred = "\n".join(e["raw_text"] for e in predicted)
        for section in golden["sections"]:
            if section_type(section["heading"]) == "unknown":
                for item in section["items"]:
                    raw = flatten_section_item(item)
                    if len(raw.split()) >= 8 and (text_coverage(raw, combined_pred) or 0) >= 0.6:
                        bleed.append(section["heading"])
        if bleed:
            comparison["notes"].append("possible section bleed: " + ", ".join(sorted(set(bleed))))
        comparison["notes"] = sorted(set(comparison["notes"]))
        hashes = {"pdf": hashlib.sha256(pdfs[name].read_bytes()).hexdigest(),
                  "golden": hashlib.sha256(goldens[name].read_bytes()).hexdigest()}
        traces.append(dict(resume=name, input_sha256=hashes, extracted_text=text,
                           parsed=parsed, expected=expected, predicted=predicted,
                           comparison=comparison, projects_start_zero=projects_zero,
                           excluded_section_headings=excluded_sections))
        rows.append(dict(resume=name, **{k: v for k, v in comparison.items() if k != "entry_diagnostics"}))
    out.mkdir(parents=True, exist_ok=True)
    summary = dict(schema="ExperienceEntryV1", exploratory=True,
                   parser_path="extract_text_from_pdf_path -> parse_resume",
                   source_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   sample_size=len(rows), results=rows)
    (out / "experience_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "experience_traces.json").write_text(json.dumps(traces, indent=2, ensure_ascii=False) + "\n")
    with (out / "experience_report.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({**r, "notes": "; ".join(r["notes"])} for r in rows)
    return summary


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--pdf-dir", type=Path, default=ROOT / "backend/benchmarks/resumes/v2")
    cli.add_argument("--golden-dir", type=Path, default=ROOT / "backend/benchmarks/golden_json/v2")
    cli.add_argument("--out", type=Path, default=ROOT / "backend/benchmarks/experience_spike")
    args = cli.parse_args()
    summary = run(args.pdf_dir, args.golden_dir, args.out)
    print(f"Evaluated {summary['sample_size']} V2 fixtures; exploratory artifacts: {args.out}")


if __name__ == "__main__":
    main()
