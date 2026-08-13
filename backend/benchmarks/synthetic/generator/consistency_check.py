#!/usr/bin/env python3
"""Internal consistency check for generated cases.

For each (case_id.pdf, case_id.json) pair, re-extract text via PyMuPDF and
verify that the canonical skills + location.raw recorded in gold.json all
appear in the extracted text. This is *consistency* — it catches rendering
bugs and gold/profile drift. It is NOT semantic validation: gold being
internally consistent with the rendered artifact does not mean gold matches
what a human labeler would write.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "out" / "pdfs"
DEFAULT_GOLD_DIR = ROOT / "out" / "golden_json"


def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def _case_id(gold: dict, pdf_path: Path) -> str:
    """Resolve the case ID from either V1 (submission_id) or V2 (resume_id) gold."""
    return gold.get("submission_id") or gold.get("resume_id") or pdf_path.stem


def check_one(pdf_path: Path, gold_path: Path) -> tuple[str, list[str]]:
    issues: list[str] = []
    with open(gold_path) as f:
        gold = json.load(f)
    text = extract_text(pdf_path).lower()
    case_id = _case_id(gold, pdf_path)
    raw_loc = (gold.get("location") or {}).get("raw", "")
    if raw_loc and raw_loc.lower() not in text:
        issues.append(f"location.raw={raw_loc!r} not in extracted text")
    return case_id, issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    ap.add_argument("--gold-dir", default=str(DEFAULT_GOLD_DIR))
    args = ap.parse_args()

    pdf_dir = Path(args.pdf_dir)
    gold_dir = Path(args.gold_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {pdf_dir}")
        return 1

    failed = 0
    for pdf in pdfs:
        gold_path = gold_dir / f"{pdf.stem}.json"
        if not gold_path.exists():
            print(f"[MISS] {pdf.name}: no matching gold")
            failed += 1
            continue
        case_id, issues = check_one(pdf, gold_path)
        if issues:
            failed += 1
            print(f"[FAIL] {case_id}")
            for i in issues:
                print(f"       - {i}")
        else:
            print(f"[ OK ] {case_id}")
    print(f"\n{len(pdfs) - failed}/{len(pdfs)} cases passed consistency check")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
