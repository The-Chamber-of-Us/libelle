#!/usr/bin/env python3
"""
Libelle Parser Benchmark CLI
Usage:
    python scripts/benchmark.py \
        --pdf_dir benchmarks/resumes \
        --golden_dir benchmarks/golden_json \
        --parsers libelle pyresparser \
        --out benchmarks/runs
"""

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Adapter helpers
# ---------------------------------------------------------------------------

def libelle_adapter(parsed: Dict[str, Any], submission_id: str, runtime_ms: float) -> Dict[str, Any]:
    """Map Libelle parse_resume() output → required benchmark schema."""
    skills_raw = parsed.get("skills", {}).get("value", [])
    skills = [s.strip() for s in skills_raw if isinstance(s, str) and s.strip()]

    loc_list = parsed.get("locations", {}).get("value", [])
    raw_loc = loc_list[0] if loc_list else ""
    city, country = _split_location(raw_loc)

    return {
        "submission_id": submission_id,
        "skills": skills,
        "location": {
            "city": city,
            "country": country,
            "raw": raw_loc,
        },
        "metadata": {
            "parser_name": "libelle",
            "runtime_ms": round(runtime_ms, 2),
        },
    }


def pyresparser_adapter(parsed: Dict[str, Any], submission_id: str, runtime_ms: float) -> Dict[str, Any]:
    """Map pyresparser ResumeParser output → required benchmark schema."""
    skills_raw = parsed.get("skills") or []
    skills = [s.strip() for s in skills_raw if isinstance(s, str) and s.strip()]

    raw_loc = (parsed.get("location") or "").strip()
    city, country = _split_location(raw_loc)

    return {
        "submission_id": submission_id,
        "skills": skills,
        "location": {
            "city": city,
            "country": country,
            "raw": raw_loc,
        },
        "metadata": {
            "parser_name": "pyresparser",
            "runtime_ms": round(runtime_ms, 2),
        },
    }


def _split_location(raw: str) -> Tuple[str, str]:
    """Best-effort split 'City, State/Country' → (city, country).
    
    If the trailing token is a 2-letter US state code, country is set to
    'united states' so it matches golden JSONs that use that convention.
    """
    US_STATES = {
        "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
        "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
        "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
        "TX","UT","VT","VA","WA","WV","WI","WY","DC",
    }
    if not raw:
        return "", ""
    parts = [p.strip() for p in raw.split(",")]
    city = parts[0] if parts else ""
    if len(parts) > 1:
        last = parts[-1].strip().upper().split()[0] if parts[-1].strip() else ""
        if last in US_STATES:
            country = "united states"
        else:
            country = parts[-1].strip()
    else:
        country = ""
    return city, country


# ---------------------------------------------------------------------------
# Runner helpers
# ---------------------------------------------------------------------------

def _run_libelle(pdf_path: Path) -> Tuple[Dict[str, Any], float]:
    """Extract text with PyMuPDF and run Libelle parser. Returns (raw_parsed, runtime_ms)."""
    import fitz  # PyMuPDF

    # Add parent dirs to sys.path so we can import parser.py
    for p in [str(Path(__file__).parent.parent.parent), str(Path(__file__).parent.parent)]:
        if p not in sys.path:
            sys.path.insert(0, p)

    from parser import parse_resume  # Libelle's parser

    doc = fitz.open(str(pdf_path))
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()

    t0 = time.perf_counter()
    result = parse_resume(text)
    runtime_ms = (time.perf_counter() - t0) * 1000
    return result, runtime_ms


def _run_pyresparser(pdf_path: Path) -> Tuple[Dict[str, Any], float]:
    """Run pyresparser on a PDF. Returns (raw_parsed, runtime_ms)."""
    try:
        from pyresparser import ResumeParser
    except ImportError:
        raise ImportError("pyresparser is not installed. Run: pip install pyresparser")

    t0 = time.perf_counter()
    result = ResumeParser(str(pdf_path)).get_extracted_data()
    runtime_ms = (time.perf_counter() - t0) * 1000
    return result or {}, runtime_ms


PARSERS = {
    "libelle": (_run_libelle, libelle_adapter),
    "pyresparser": (_run_pyresparser, pyresparser_adapter),
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _normalize(s) -> str:
    if not s:
        return ""
    return str(s).strip().lower()


def score_skills(
    predicted: List[str], golden: List[str]
) -> Dict[str, Any]:
    pred_set = set(_normalize(s) for s in predicted if s)
    gold_set = set(_normalize(s) for s in golden if s)

    tp = pred_set & gold_set
    fp = pred_set - gold_set
    fn = gold_set - pred_set

    return {
        "tp_count": len(tp),
        "fp_count": len(fp),
        "fn_count": len(fn),
        "tp_examples": sorted(tp)[:10],
        "fp_examples": sorted(fp)[:10],
        "fn_examples": sorted(fn)[:10],
    }


def score_location(
    predicted: Dict[str, str], golden: Dict[str, str]
) -> Dict[str, Any]:
    pred_country = _normalize(predicted.get("country", ""))
    gold_country = _normalize(golden.get("country", ""))
    pred_city = _normalize(predicted.get("city", ""))
    gold_city = _normalize(golden.get("city", ""))

    country_match = pred_country == gold_country and gold_country != ""
    city_match = pred_city == gold_city and gold_city != ""

    # Treat as a single TP/FP/FN unit (country required, city optional bonus)
    if country_match:
        tp, fp, fn = 1, 0, 0
        tp_examples = [f"country={gold_country}" + (f", city={gold_city}" if city_match else "")]
        fp_examples, fn_examples = [], []
    elif not gold_country:
        # Golden has no country — any prediction is a false positive only, no FN
        if pred_country:
            tp, fp, fn = 0, 1, 0
            tp_examples = []
            fp_examples = [f"predicted country={pred_country} (golden has no country)"]
            fn_examples = []
        else:
            tp, fp, fn = 0, 0, 0
            tp_examples, fp_examples, fn_examples = [], [], []
    elif pred_country:
        # Wrong country predicted
        tp, fp, fn = 0, 1, 1
        tp_examples = []
        fp_examples = [f"predicted country={pred_country}"]
        fn_examples = [f"expected country={gold_country}"]
    else:
        # Nothing predicted
        tp, fp, fn = 0, 0, 1
        tp_examples, fp_examples = [], []
        fn_examples = [f"expected country={gold_country}"]

    return {
        "tp_count": tp,
        "fp_count": fp,
        "fn_count": fn,
        "tp_examples": tp_examples,
        "fp_examples": fp_examples,
        "fn_examples": fn_examples,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_report_csv(rows: List[Dict], out_dir: Path) -> Path:
    path = out_dir / "report.csv"
    fieldnames = [
        "resume", "parser", "field",
        "tp_count", "fp_count", "fn_count",
        "precision", "recall", "f1",
        "tp_examples", "fp_examples", "fn_examples",
        "runtime_ms",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _compute_prf(tp, fp, fn) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return round(precision, 3), round(recall, 3), round(f1, 3)


def write_examples_md(rows: List[Dict], out_dir: Path) -> Path:
    path = out_dir / "examples.md"
    fp_rows = sorted(
        [r for r in rows if r["fp_count"] > 0],
        key=lambda r: r["fp_count"],
        reverse=True,
    )
    fn_rows = sorted(
        [r for r in rows if r["fn_count"] > 0],
        key=lambda r: r["fn_count"],
        reverse=True,
    )

    lines = ["# Benchmark Failure Examples\n"]
    lines.append("## False Positives (predicted but not in golden)\n")
    for r in fp_rows[:5]:
        lines.append(f"**Resume:** `{r['resume']}` | **Parser:** `{r['parser']}` | **Field:** `{r['field']}`")
        fps = r["fp_examples"] if isinstance(r["fp_examples"], list) else json.loads(r["fp_examples"] or "[]")
        lines.append(f"- FP examples: {', '.join(str(x) for x in fps[:5])}\n")

    lines.append("\n## False Negatives (in golden but not predicted)\n")
    for r in fn_rows[:5]:
        lines.append(f"**Resume:** `{r['resume']}` | **Parser:** `{r['parser']}` | **Field:** `{r['field']}`")
        fns = r["fn_examples"] if isinstance(r["fn_examples"], list) else json.loads(r["fn_examples"] or "[]")
        lines.append(f"- FN examples: {', '.join(str(x) for x in fns[:5])}\n")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def _get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _get_parser_versions(parser_names: List[str]) -> Dict[str, str]:
    versions = {}
    for name in parser_names:
        if name == "libelle":
            versions[name] = "local"
        elif name == "pyresparser":
            try:
                import pyresparser
                versions[name] = getattr(pyresparser, "__version__", "unknown")
            except ImportError:
                versions[name] = "not_installed"
    return versions


def write_run_log(
    out_dir: Path,
    parser_names: List[str],
    args: argparse.Namespace,
    errors: List[Dict],
) -> Path:
    path = out_dir / "run_log.json"
    log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _get_git_commit(),
        "parsers": parser_names,
        "parser_versions": _get_parser_versions(parser_names),
        "command": " ".join(sys.argv),
        "system": {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        "args": vars(args),
        "errors": errors,
    }
    with open(path, "w") as f:
        json.dump(log, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Libelle Parser Benchmark CLI")
    parser.add_argument("--pdf_dir", required=True, help="Directory of PDF resumes")
    parser.add_argument("--golden_dir", required=True, help="Directory of golden JSON files")
    parser.add_argument(
        "--parsers", nargs="+", default=["libelle"],
        choices=list(PARSERS.keys()),
        help="Parsers to benchmark",
    )
    parser.add_argument("--out", default="benchmarks/runs", help="Output base directory")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    golden_dir = Path(args.golden_dir)

    # Create timestamped output dir
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"[ERROR] No PDFs found in {pdf_dir}")
        sys.exit(1)

    report_rows: List[Dict] = []
    errors: List[Dict] = []

    for pdf_path in pdfs:
        submission_id = pdf_path.stem
        golden_path = golden_dir / f"{submission_id}.json"

        if not golden_path.exists():
            msg = f"No golden JSON for {submission_id}, skipping."
            print(f"[WARN] {msg}")
            errors.append({"resume": submission_id, "error": msg})
            continue

        with open(golden_path) as f:
            golden = json.load(f)

        for parser_name in args.parsers:
            runner_fn, adapter_fn = PARSERS[parser_name]
            print(f"[RUN] {submission_id} → {parser_name} ...", end=" ", flush=True)

            try:
                raw, runtime_ms = runner_fn(pdf_path)
                adapted = adapter_fn(raw, submission_id, runtime_ms)
            except Exception as e:
                tb = traceback.format_exc()
                print(f"ERROR\n{tb}")
                errors.append({
                    "resume": submission_id,
                    "parser": parser_name,
                    "error": str(e),
                    "traceback": tb,
                })
                continue

            print(f"done ({runtime_ms:.0f}ms)")

            # Score skills
            skills_score = score_skills(
                adapted["skills"], golden.get("skills", [])
            )
            p, r, f1 = _compute_prf(
                skills_score["tp_count"], skills_score["fp_count"], skills_score["fn_count"]
            )
            report_rows.append({
                "resume": submission_id,
                "parser": parser_name,
                "field": "skills",
                **skills_score,
                "precision": p,
                "recall": r,
                "f1": f1,
                "runtime_ms": round(runtime_ms, 2),
                "tp_examples": json.dumps(skills_score["tp_examples"]),
                "fp_examples": json.dumps(skills_score["fp_examples"]),
                "fn_examples": json.dumps(skills_score["fn_examples"]),
            })

            # Score location
            loc_score = score_location(
                adapted["location"], golden.get("location", {})
            )
            p, r, f1 = _compute_prf(
                loc_score["tp_count"], loc_score["fp_count"], loc_score["fn_count"]
            )
            report_rows.append({
                "resume": submission_id,
                "parser": parser_name,
                "field": "location",
                **loc_score,
                "precision": p,
                "recall": r,
                "f1": f1,
                "runtime_ms": round(runtime_ms, 2),
                "tp_examples": json.dumps(loc_score["tp_examples"]),
                "fp_examples": json.dumps(loc_score["fp_examples"]),
                "fn_examples": json.dumps(loc_score["fn_examples"]),
            })

    if not report_rows:
        print("[ERROR] No results generated. Check your inputs.")
        sys.exit(1)

    # Write outputs
    csv_path = write_report_csv(report_rows, out_dir)
    md_path = write_examples_md(report_rows, out_dir)
    log_path = write_run_log(out_dir, args.parsers, args, errors)

    print(f"\n✅ Run complete → {out_dir}")
    print(f"   report.csv   : {csv_path}")
    print(f"   examples.md  : {md_path}")
    print(f"   run_log.json : {log_path}")

    # Print quick summary
    _print_summary(report_rows)


def _print_summary(rows: List[Dict]):
    from collections import defaultdict
    summary = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for r in rows:
        key = (r["parser"], r["field"])
        summary[key]["tp"] += r["tp_count"]
        summary[key]["fp"] += r["fp_count"]
        summary[key]["fn"] += r["fn_count"]

    print("\n── Summary ──────────────────────────────────")
    print(f"{'Parser':<15} {'Field':<10} {'P':>6} {'R':>6} {'F1':>6}")
    print("─" * 45)
    for (parser, field), counts in sorted(summary.items()):
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        print(f"{parser:<15} {field:<10} {p:>6.3f} {r:>6.3f} {f1:>6.3f}")
    print("─" * 45)


if __name__ == "__main__":
    main()