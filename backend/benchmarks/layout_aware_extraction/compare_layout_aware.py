#!/usr/bin/env python3
"""
Standalone comparison: current production extraction vs. experimental
layout-aware extraction (issue #275), scored against the same golden
JSON corpus used by scripts/benchmark.py.

Does NOT modify scripts/benchmark.py. Reuses its scoring functions
(score_skills, score_location, _compute_prf) and reuses the unmodified
production parser (parser.parse_resume) and text extractor
(services.pdf_text_extraction.extract_text_from_pdf_path) exactly as
scripts/benchmark.py does for the "libelle" parser.

The only thing that changes between the two runs is which text goes
into parse_resume() — current production ordering, or layout-aware
ordering (gated behind enabled=True here; still False everywhere else
in the codebase).

Usage (from backend/):
    python benchmarks/layout_aware_extraction/compare_layout_aware.py

Outputs:
    backend/benchmarks/layout_aware_extraction/runs/<timestamp>/comparison.csv
    backend/benchmarks/layout_aware_extraction/runs/<timestamp>/comparison_summary.md
"""

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).parent.parent.parent.parent  # repo root
BACKEND_DIR = BASE_DIR / "backend"
SCRIPTS_DIR = BASE_DIR / "scripts"
THIS_DIR = Path(__file__).parent

for p in [str(BASE_DIR), str(BACKEND_DIR), str(SCRIPTS_DIR), str(THIS_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from parser import parse_resume  # noqa: E402
from services.pdf_text_extraction import extract_text_from_pdf_path  # noqa: E402
from benchmark import score_skills, score_location, _compute_prf, _split_location  # noqa: E402

from layout_aware_extraction import extract_text_from_pdf_layout_aware  # noqa: E402


PDF_DIR = BACKEND_DIR / "benchmarks" / "resumes"
GOLDEN_DIR = BACKEND_DIR / "benchmarks" / "golden_json"
OUT_BASE = Path(__file__).parent / "runs"


def _adapt(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Same shape as benchmark.py's libelle_adapter, minus metadata."""
    skills_raw = parsed.get("skills", {}).get("value", [])
    skills = [s.strip() for s in skills_raw if isinstance(s, str) and s.strip()]

    loc_list = parsed.get("locations", {}).get("value", [])
    raw_loc = loc_list[0] if loc_list else ""
    city, country = _split_location(raw_loc)

    return {
        "skills": skills,
        "location": {"city": city, "country": country, "raw": raw_loc},
    }


def _score_one(adapted: Dict[str, Any], golden: Dict[str, Any]) -> Dict[str, float]:
    skills_score = score_skills(adapted["skills"], golden.get("skills", []))
    sp, sr, sf1 = _compute_prf(
        skills_score["tp_count"], skills_score["fp_count"], skills_score["fn_count"]
    )

    loc_score = score_location(adapted["location"], golden.get("location", {}))
    lp, lr, lf1 = _compute_prf(
        loc_score["tp_count"], loc_score["fp_count"], loc_score["fn_count"]
    )

    return {
        "skills_precision": sp, "skills_recall": sr, "skills_f1": sf1,
        "skills_tp": skills_score["tp_count"], "skills_fp": skills_score["fp_count"],
        "skills_fn": skills_score["fn_count"],
        "location_precision": lp, "location_recall": lr, "location_f1": lf1,
    }


def run(allow_missing_goldens: bool = False) -> Path:
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"[ERROR] No PDFs found in {PDF_DIR}")
        sys.exit(1)

    rows: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    skipped: List[str] = []

    for pdf_path in pdfs:
        submission_id = pdf_path.stem
        golden_path = GOLDEN_DIR / f"{submission_id}.json"

        if not golden_path.exists():
            skipped.append(submission_id)
            if not allow_missing_goldens:
                print(
                    f"[ERROR] Missing golden JSON for {submission_id}. "
                    f"Pass --allow-missing-goldens to skip instead of failing."
                )
                sys.exit(1)
            print(f"[WARN] Skipping {submission_id} — no golden JSON found.")
            continue

        with open(golden_path) as f:
            golden = json.load(f)

        # --- Current production path (unchanged) ---
        prod_text = extract_text_from_pdf_path(pdf_path)
        prod_parsed = parse_resume(prod_text)
        prod_adapted = _adapt(prod_parsed)
        prod_scores = _score_one(prod_adapted, golden)

        # --- Layout-aware path (experimental, enabled=True here only) ---
        la_result = extract_text_from_pdf_layout_aware(pdf_path, enabled=True)

        # Fallback guarantees exact production text for true apples-to-apples scoring
        if la_result["layout_aware_used"]:
            la_text = la_result["text"]
        else:
            la_text = prod_text

        la_parsed = parse_resume(la_text)
        la_adapted = _adapt(la_parsed)
        la_scores = _score_one(la_adapted, golden)

        # --- Diagnostics: only recorded for resumes where layout-aware
        # extraction actually triggered, to investigate regressions ---
        if la_result["layout_aware_used"]:
            prod_skill_set = set(s.lower().strip() for s in prod_adapted["skills"])
            la_skill_set = set(s.lower().strip() for s in la_adapted["skills"])
            gold_skill_set = set(s.lower().strip() for s in golden.get("skills", []))

            diagnostics.append({
                "resume": submission_id,
                "reason": "; ".join(la_result["reasons"]),
                "prod_text": prod_text,
                "la_text": la_result["text"],
                "prod_skills": sorted(prod_skill_set),
                "la_skills": sorted(la_skill_set),
                "gold_skills": sorted(gold_skill_set),
                "lost_in_la": sorted(prod_skill_set & gold_skill_set - la_skill_set),
                "gained_in_la": sorted(la_skill_set & gold_skill_set - prod_skill_set),
            })

        row = {
            "resume": submission_id,
            "layout_aware_used": la_result["layout_aware_used"],
            "layout_aware_reasons": "; ".join(la_result["reasons"]),
            "prod_skills_f1": prod_scores["skills_f1"],
            "la_skills_f1": la_scores["skills_f1"],
            "skills_f1_delta": round(la_scores["skills_f1"] - prod_scores["skills_f1"], 3),
            "prod_skills_precision": prod_scores["skills_precision"],
            "la_skills_precision": la_scores["skills_precision"],
            "prod_skills_recall": prod_scores["skills_recall"],
            "la_skills_recall": la_scores["skills_recall"],
            "prod_location_f1": prod_scores["location_f1"],
            "la_location_f1": la_scores["location_f1"],
            "location_f1_delta": round(la_scores["location_f1"] - prod_scores["location_f1"], 3),
        }
        rows.append(row)

        flag = "LAYOUT-AWARE USED" if la_result["layout_aware_used"] else "fallback to production"
        print(
            f"[{submission_id}] prod_skills_f1={prod_scores['skills_f1']:.3f} "
            f"la_skills_f1={la_scores['skills_f1']:.3f} "
            f"delta={row['skills_f1_delta']:+.3f} ({flag})"
        )

    if not rows:
        print("[ERROR] No results generated — nothing to compare. Check corpus and golden paths.")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_BASE / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "comparison.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    if diagnostics:
        diag_path = out_dir / "diagnostics.json"
        with open(diag_path, "w") as f:
            json.dump(diagnostics, f, indent=2)
        print(f"   diagnostics.json: {diag_path}")

    _write_summary(rows, out_dir)

    if skipped:
        print(f"\n⚠️  {len(skipped)} resume(s) skipped (missing golden): {', '.join(skipped)}")

    print(f"\n✅ Comparison complete → {out_dir}")
    return out_dir


def _write_summary(rows: List[Dict[str, Any]], out_dir: Path) -> None:
    used_rows = [r for r in rows if r["layout_aware_used"]]
    fallback_rows = [r for r in rows if not r["layout_aware_used"]]

    improved = [r for r in rows if r["skills_f1_delta"] > 0]
    regressed = [r for r in rows if r["skills_f1_delta"] < 0]
    unchanged = [r for r in rows if r["skills_f1_delta"] == 0]

    lines = ["# Layout-aware vs. production comparison\n"]
    lines.append(f"Total resumes: {len(rows)}  ")
    lines.append(f"Layout-aware accepted (safeguards passed): {len(used_rows)}  ")
    lines.append(f"Fell back to production (safeguards rejected): {len(fallback_rows)}\n")

    lines.append("## Skills F1 deltas\n")
    lines.append(f"- Improved: {len(improved)}")
    lines.append(f"- Regressed: {len(regressed)}")
    lines.append(f"- Unchanged: {len(unchanged)}\n")

    lines.append("## Per-resume results\n")
    lines.append("| Resume | Layout-aware used | Prod F1 | LA F1 | Delta |")
    lines.append("|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: r["skills_f1_delta"]):
        lines.append(
            f"| {r['resume']} | {r['layout_aware_used']} | "
            f"{r['prod_skills_f1']:.3f} | {r['la_skills_f1']:.3f} | "
            f"{r['skills_f1_delta']:+.3f} |"
        )

    if regressed:
        lines.append("\n## ⚠️ Regressions (layout-aware scored lower than production)\n")
        for r in regressed:
            lines.append(f"- `{r['resume']}`: {r['prod_skills_f1']:.3f} → {r['la_skills_f1']:.3f} ({r['skills_f1_delta']:+.3f})")

    with open(out_dir / "comparison_summary.md", "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--allow-missing-goldens", action="store_true")
    args = arg_parser.parse_args()

    run(allow_missing_goldens=args.allow_missing_goldens)