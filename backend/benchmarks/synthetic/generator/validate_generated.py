#!/usr/bin/env python3
"""Validate generated synthetic benchmark artifacts against both boundaries (#349):

  1. Internal consistency: does gold.json remain consistent with the
     rendered PDF from the same synthetic profile? (consistency_check.py)
  2. Canonical benchmark corpus contract: does the generated corpus satisfy
     the preflight validator defined by #344? (backend/benchmarks/preflight.py)

A generated corpus is only "benchmark-ready" when it passes both. This
reuses both existing validators rather than duplicating their logic --
#344 is not reimplemented here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

from consistency_check import check_one  # noqa: E402

BACKEND_DIR = GENERATOR_DIR.parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from benchmarks.preflight import format_preflight_report, run_preflight  # noqa: E402

SYNTHETIC_ROOT = GENERATOR_DIR.parent
DEFAULT_PDF_DIR = SYNTHETIC_ROOT / "out" / "pdfs"
DEFAULT_GOLD_DIR = SYNTHETIC_ROOT / "out" / "golden_json"


def run_consistency(pdf_dir: Path, gold_dir: Path) -> Tuple[bool, List[str]]:
    """Run the generator's internal consistency check across a directory pair.

    Malformed/unreadable gold files are reported as consistency failures
    rather than raised -- the canonical validator below diagnoses schema
    problems in detail; this boundary just should not crash on bad input.
    """
    pdfs = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
    failures: List[str] = []
    for pdf in pdfs:
        gold_path = gold_dir / f"{pdf.stem}.json"
        if not gold_path.exists():
            failures.append(f"{pdf.stem}: no matching gold.json")
            continue
        try:
            case_id, issues = check_one(pdf, gold_path)
        except (json.JSONDecodeError, OSError) as exc:
            failures.append(f"{pdf.stem}: could not read gold.json ({exc})")
            continue
        for issue in issues:
            failures.append(f"{case_id}: {issue}")
    return not failures, failures


def validate_generated(pdf_dir: Path, gold_dir: Path) -> bool:
    """Run both validation boundaries and print an actionable report.

    Returns True only when the generated corpus is benchmark-ready: internally
    consistent AND passing the canonical corpus preflight validator.
    """
    print("=== Internal consistency check ===")
    consistency_ok, consistency_failures = run_consistency(pdf_dir, gold_dir)
    if consistency_ok:
        print("OK: generated artifacts are internally consistent with their source profile.\n")
    else:
        print("FAILED: internal consistency violations found:")
        for failure in consistency_failures:
            print(f"  - {failure}")
        print()

    print("=== Canonical benchmark corpus validation (#344) ===")
    preflight = run_preflight(pdf_dir, gold_dir)
    print(format_preflight_report(preflight))

    ready = consistency_ok and preflight.ok
    print("\nBENCHMARK-READY" if ready else "\nNOT BENCHMARK-READY")
    return ready


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR), type=Path)
    ap.add_argument("--gold-dir", default=str(DEFAULT_GOLD_DIR), type=Path)
    args = ap.parse_args(argv)

    ready = validate_generated(args.pdf_dir, args.gold_dir)
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
