#!/usr/bin/env python3
"""
Libelle Parser Benchmark CLI
Usage:
    python scripts/benchmark.py

    # Optional overrides:
    python scripts/benchmark.py \
        --pdf_dir backend/benchmarks/resumes \
        --golden_dir backend/benchmarks/golden_json \
        --parsers libelle pyresparser \
        --out backend/benchmarks/runs
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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set



# ---------------------------------------------------------------------------
# Path / import helpers
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent
BACKEND_DIR = BASE_DIR / "backend"

for p in [str(BASE_DIR), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Resolver helpers
# ---------------------------------------------------------------------------

DEFAULT_ALIAS_PATHS = [
    BACKEND_DIR / "resolver" / "aliases_v1.json",
    BACKEND_DIR / "resolver" / "aliases.json",
    BACKEND_DIR / "resolver" / "skill_aliases.json",
    BACKEND_DIR / "resolver" / "knowledge" / "aliases_v1.json",
    BACKEND_DIR / "resolver" / "knowledge" / "aliases.json",
    BACKEND_DIR / "resolver" / "knowledge" / "skill_aliases.json",
    BACKEND_DIR / "resolver" / "aliases" / "skills.json",
    BACKEND_DIR / "resolver" / "aliases" / "skills_v1.json",
    BACKEND_DIR / "data" / "skill_aliases.json",
    BACKEND_DIR / "benchmarks" / "aliases.json",
]


def _load_alias_map(path: Optional[str]) -> Tuple[Dict[str, str], str, str]:
    """
    Load resolver aliases for local benchmark evaluation.

    Supports either:
      1. {"python": "python", "js": "javascript"}
      2. {"version": "2026-04-xx", "aliases": {...}}
      3. [{"alias": "js", "canonical": "javascript"}, ...]
    """

    from resolver.normalize import normalize_key
    candidate_paths = [Path(path)] if path else DEFAULT_ALIAS_PATHS

    selected_path: Optional[Path] = None
    for candidate in candidate_paths:
        if candidate.exists():
            selected_path = candidate
            break

    if selected_path is None:
        searched = ", ".join(str(p) for p in candidate_paths)
        raise FileNotFoundError(f"No resolver alias map found. Searched: {searched}")

    with open(selected_path) as f:
        raw = json.load(f)

    aliases_version = selected_path.stem

    if isinstance(raw, dict) and isinstance(raw.get("aliases"), dict):
        aliases_version = str(raw.get("version") or raw.get("aliases_version") or aliases_version)
        aliases = raw["aliases"]
    elif isinstance(raw, dict):
        aliases = raw
    elif isinstance(raw, list):
        aliases = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            alias = item.get("alias") or item.get("key") or item.get("raw")
            canonical = item.get("canonical") or item.get("canonical_id") or item.get("skill_id")
            if alias and canonical:
                aliases[str(alias)] = str(canonical)
    else:
        raise ValueError(f"Unsupported alias map format in {selected_path}")

    cleaned_aliases: Dict[str, str] = {
        normalize_key(str(k)): str(v)
        for k, v in aliases.items()
        if normalize_key(str(k)) and str(v).strip()
    }

    return cleaned_aliases, aliases_version, str(selected_path)


def _resolve_skills_for_benchmark(
    *,
    submission_id: str,
    skills: List[str],
    location_raw: str,
    aliases: Dict[str, str],
    aliases_version: str,
) -> Dict[str, Any]:
    from resolver.resolver import resolve_extracted_profile
    from resolver.schemas import ExtractedProfileV1

    if not skills:
        return {
            "resolver_coverage": "",
            "resolver_input_count": 0,
            "resolver_resolved_count": 0,
            "resolver_unknown_count": 0,
            "unknown_skills": [],
            "resolver_version": "v1",
            "aliases_version": aliases_version,
        }

    extracted = ExtractedProfileV1(
        submission_id=submission_id,
        skills=skills,
        location_raw=location_raw or "",
        meta={"source": "benchmark"},
    )

    resolved = resolve_extracted_profile(
        extracted,
        aliases,
        resolver_version="v1",
        aliases_version=aliases_version,
    )

    return {
        "resolver_coverage": round(resolved.stats.coverage, 3),
        "resolver_input_count": resolved.stats.input_count,
        "resolver_resolved_count": resolved.stats.resolved_count,
        "resolver_unknown_count": resolved.stats.unknown_count,
        "unknown_skills": list(resolved.unknowns.skills),
        "resolver_version": resolved.meta.get("resolver_version", "v1"),
        "aliases_version": resolved.meta.get("aliases_version", aliases_version),
    }


def _build_resolver_summary(resolver_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    coverage_values = [
        float(r["resolver_coverage"])
        for r in resolver_rows
        if r.get("resolver_coverage") != ""
    ]

    unknown_counter: Counter[str] = Counter()
    for row in resolver_rows:
        for skill in row.get("unknown_skills", []):
            if isinstance(skill, str) and skill.strip():
                unknown_counter[skill.strip()] += 1

    unknown_skills = [
        {"skill": skill, "count": count}
        for skill, count in sorted(unknown_counter.items(), key=lambda x: (-x[1], x[0].lower()))
    ]

    avg_coverage = round(sum(coverage_values) / len(coverage_values), 3) if coverage_values else 0.0

    return {
        "average_resolver_coverage": avg_coverage,
        "resolved_rows_count": len(coverage_values),
        "unknown_skills": unknown_skills,
    }



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
    from services.pdf_text_extraction import extract_text_from_pdf_path
    from parser import parse_resume

    text = extract_text_from_pdf_path(pdf_path)

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

def _normalize(s: Any) -> str:
    if not s:
        return ""
    return str(s).strip().lower()

def _resolve_skill(skill: str, aliases: Dict[str, str]) -> str:
    """Resolve a single skill to its canonical ID via the alias map.
    Falls through to normalized key if no alias exists."""
    from resolver.normalize import normalize_key
    key = normalize_key(skill)
    return aliases.get(key, key) if key else ""

def _resolve_skill_set(skills: List[str], aliases: Dict[str, str]) -> Set[str]:
    resolved = set()
    for s in skills:
        if s:
            r = _resolve_skill(s, aliases)
            if r:
                resolved.add(r)
    return resolved

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

def score_skills_resolved(
    predicted: List[str],
    golden: List[str],
    aliases: Dict[str, str],
) -> Dict[str, Any]:
    pred_set = _resolve_skill_set(predicted, aliases)
    gold_set = _resolve_skill_set(golden, aliases)

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
        "resolver_coverage",
        "resolver_input_count",
        "resolver_resolved_count",
        "resolver_unknown_count",
        "resolver_version",
        "aliases_version",
        "unknown_skills",
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
    resolver_summary: Dict[str, Any],
    alias_path: str,
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
        "resolver": {
            "alias_path": alias_path,
            **resolver_summary,
        },
        "errors": errors,
    }
    with open(path, "w") as f:
        json.dump(log, f, indent=2)
    return path

# Summary markdown file 
def write_summary_md(
        rows: List[Dict[str, Any]], 
        stats: Dict[Tuple[str, str], Dict[str, Any]], 
        resolver_summary: Dict[str, Any],
        out_dir: Path, 
        args: argparse.Namespace) -> Path:
    path = out_dir / "summary.md"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    git_commit = _get_git_commit()
    parsers_used = ", ".join(args.parsers)

    top_fps = sorted(rows, key=lambda r: r["fp_count"], reverse=True)[:3]

    lines = []

    lines.append("# Benchmark Summary\n")
    lines.append(f"**Timestamp:** {timestamp}  ")
    lines.append(f"**Git Commit:** `{git_commit}`  ")
    lines.append(f"**Parsers:** {parsers_used}\n")

    lines.append("## Scoreboard\n")
    lines.append("| Parser | Field | Micro-F1 | Macro-F1 | Std Dev |")
    lines.append("|--------|-------|----------|----------|---------|")
    for (parser, field), s in sorted(stats.items()):
        lines.append(
            f"| {parser} | {field} | {s['micro_f1']:.3f} | {s['macro_f1']:.3f} | {s['std_dev']:.3f} |"
        )

    lines.append("\n## Resolver Coverage on Parser Output\n")
    lines.append(f"- Average resolver coverage on parser output: `{resolver_summary['average_resolver_coverage']:.3f}`")
    lines.append(f"- Resolver rows counted: `{resolver_summary['resolved_rows_count']}`")
    lines.append(f"- Unknown skills captured: `{len(resolver_summary['unknown_skills'])}`")
    lines.append("- Note: This measures resolver alias-map coverage over skills emitted by the parser. It is not end-to-end parser skill recovery against the gold skills; TP / FP / FN / precision / recall / F1 scoring above remains unchanged.")

    lines.append("\n## Failure Heatmap (Top 3 by False Positive resume/field combinations)\n")
    lines.append("| Resume | Field | Parser | FP Count |")
    lines.append("|--------|-------|--------|----------|")
    for r in top_fps:
        lines.append(f"| {r['resume']} | {r['field']} | {r['parser']} | {r['fp_count']} |")

    with open(path, "w") as f:
        f.write("\n".join(lines))

    return path

# Summary JSON file
def write_summary_json(
        stats: Dict[Tuple[str, str], Dict[str, Any]], 
        resolver_summary: Dict[str, Any],
        out_dir: Path, 
        args: argparse.Namespace) -> Path:
    path = out_dir / "summary.json"

    serializable = {
        "scores": {},
        "resolver": resolver_summary,
    }
    for (parser, field), s in stats.items():
        key = f"{parser}::{field}"
        serializable["scores"][key] = {
            "micro_p": s["micro_p"],
            "micro_r": s["micro_r"],
            "micro_f1": s["micro_f1"],
            "macro_f1": s["macro_f1_raw"],
            "std_dev": s["std_dev_raw"],
            "tp": s["tp"],
            "fp": s["fp"],
            "fn": s["fn"],
        }

    with open(path, "w") as f:
        json.dump(serializable, f, indent=2)

    return path

# computing aggregate stats (SD and var included) - raw values
def compute_aggregate_stats(rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    groups = defaultdict(list)
    for r in rows:
        key = (r["parser"], r["field"])
        groups[key].append(r)

    stats = {}
    for (parser, field), group_rows in groups.items():
        tp = sum(r["tp_count"] for r in group_rows)
        fp = sum(r["fp_count"] for r in group_rows)
        fn = sum(r["fn_count"] for r in group_rows)
        micro_p, micro_r, micro_f1 = _compute_prf(tp, fp, fn)

        f1_scores = [r["f1"] for r in group_rows]
        macro_f1_raw = sum(f1_scores) / len(f1_scores)

        mean = macro_f1_raw
        variance = sum((x - mean) ** 2 for x in f1_scores) / len(f1_scores)
        std_dev_raw = variance ** 0.5 if len(f1_scores) > 1 else 0.0

        stats[(parser, field)] = {
            "tp": tp, "fp": fp, "fn": fn,
            "micro_p": micro_p, "micro_r": micro_r, "micro_f1": micro_f1,
            "macro_f1_raw": macro_f1_raw,
            "std_dev_raw": std_dev_raw,
            "macro_f1": round(macro_f1_raw, 3),
            "std_dev": round(std_dev_raw, 3),
            "f1_scores": f1_scores,
        }

    return stats

def _print_summary(stats: Dict[Tuple[str, str], Dict[str, Any]], resolver_summary: Dict[str, Any]) -> None:
    print("\n── Summary ──────────────────────────────────")
    print(f"{'Parser':<15} {'Field':<10} {'Micro-P':>8} {'Micro-R':>8} {'Micro-F1':>9} {'Macro-F1':>9}")
    print("─" * 55)
    for (parser, field), s in sorted(stats.items()):
        print(
            f"{parser:<15} {field:<10} {s['micro_p']:>8.3f} {s['micro_r']:>8.3f} {s['micro_f1']:>9.3f} {s['macro_f1']:>9.3f}"
        )
    print("─" * 55)
    print(f"Average resolver coverage on parser output: {resolver_summary['average_resolver_coverage']:.3f}")
    print(f"Unknown skills captured: {len(resolver_summary['unknown_skills'])}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Libelle Parser Benchmark CLI")

    parser.add_argument(
        "--pdf_dir",
        default=str(BASE_DIR / "backend/benchmarks/resumes"),
        help="Directory of PDF resumes",
    )

    parser.add_argument(
        "--golden_dir",
        default=str(BASE_DIR / "backend/benchmarks/golden_json"),
        help="Directory of golden JSON files",
    )

    parser.add_argument(
        "--parsers", nargs="+", default=["libelle"],
        choices=list(PARSERS.keys()),
        help="Parsers to benchmark",
    )

    parser.add_argument(
        "--out",
        default=str(BASE_DIR / "backend/benchmarks/runs"),
        help="Output base directory",
    )

    parser.add_argument(
        "--aliases_path",
        default=None,
        help="Optional path to Resolver V1 alias map JSON. If omitted, benchmark.py searches known local paths.",
    )

    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    golden_dir = Path(args.golden_dir)

    aliases, aliases_version, alias_path = _load_alias_map(args.aliases_path)
    print(f"[RESOLVER] Loaded {len(aliases)} aliases from {alias_path}")

    # Create timestamped output dir
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"[ERROR] No PDFs found in {pdf_dir}")
        sys.exit(1)

    report_rows: List[Dict[str, Any]] = []
    resolver_rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

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
                resolver_metrics = _resolve_skills_for_benchmark(
                    submission_id=submission_id,
                    skills=adapted["skills"],
                    location_raw=adapted["location"].get("raw", ""),
                    aliases=aliases,
                    aliases_version=aliases_version,
                )
                resolver_rows.append({
                    "resume": submission_id,
                    "parser": parser_name,
                    **resolver_metrics,
                })
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

            # Score skills (raw)
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
                "resolver_coverage": resolver_metrics["resolver_coverage"],
                "resolver_input_count": resolver_metrics["resolver_input_count"],
                "resolver_resolved_count": resolver_metrics["resolver_resolved_count"],
                "resolver_unknown_count": resolver_metrics["resolver_unknown_count"],
                "resolver_version": resolver_metrics["resolver_version"],
                "aliases_version": resolver_metrics["aliases_version"],
                "unknown_skills": json.dumps(resolver_metrics["unknown_skills"]),
            })

            # Score skills (resolved)
            skills_resolved_score = score_skills_resolved(
                adapted["skills"], golden.get("skills", []), aliases
            )
            p_res, r_res, f1_res = _compute_prf(
                skills_resolved_score["tp_count"],
                skills_resolved_score["fp_count"],
                skills_resolved_score["fn_count"],
            )
            report_rows.append({
                "resume": submission_id,
                "parser": parser_name,
                "field": "skills_resolved",
                **skills_resolved_score,
                "precision": p_res,
                "recall": r_res,
                "f1": f1_res,
                "runtime_ms": round(runtime_ms, 2),
                "tp_examples": json.dumps(skills_resolved_score["tp_examples"]),
                "fp_examples": json.dumps(skills_resolved_score["fp_examples"]),
                "fn_examples": json.dumps(skills_resolved_score["fn_examples"]),
                "resolver_coverage": resolver_metrics["resolver_coverage"],
                "resolver_input_count": resolver_metrics["resolver_input_count"],
                "resolver_resolved_count": resolver_metrics["resolver_resolved_count"],
                "resolver_unknown_count": resolver_metrics["resolver_unknown_count"],
                "resolver_version": resolver_metrics["resolver_version"],
                "aliases_version": resolver_metrics["aliases_version"],
                "unknown_skills": json.dumps(resolver_metrics["unknown_skills"]),
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
                "resolver_coverage": "",
                "resolver_input_count": "",
                "resolver_resolved_count": "",
                "resolver_unknown_count": "",
                "resolver_version": resolver_metrics["resolver_version"],
                "aliases_version": resolver_metrics["aliases_version"],
                "unknown_skills": "",
            })

    if not report_rows:
        print("[ERROR] No results generated. Check your inputs.")
        sys.exit(1)

    stats = compute_aggregate_stats(report_rows)
    resolver_summary = _build_resolver_summary(resolver_rows)
    # Write outputs
    csv_path = write_report_csv(report_rows, out_dir)
    md_path = write_examples_md(report_rows, out_dir)
    log_path = write_run_log(out_dir, args.parsers, args, errors, resolver_summary, alias_path)
    summary_path = write_summary_md(report_rows, stats, resolver_summary, out_dir, args)
    json_path = write_summary_json(stats, resolver_summary, out_dir, args)

    print(f"\n✅ Run complete → {out_dir}")
    print(f"   report.csv   : {csv_path}")
    print(f"   examples.md  : {md_path}")
    print(f"   run_log.json : {log_path}")
    print(f"   summary.md   : {summary_path}")
    print(f"   summary.json : {json_path}")

    # Print quick summary
    _print_summary(stats, resolver_summary)


if __name__ == "__main__":
    main()
