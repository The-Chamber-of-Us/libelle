#!/usr/bin/env python3
"""Synthetic benchmark generator (#191).

Produces a deterministic synthetic corpus consumable by scripts/benchmark.py.
Same --seed reproduces the same case content and gold targets.

Usage:
    python backend/benchmarks/synthetic/generator/generate.py --seed 42 --count 30

Outputs:
    backend/benchmarks/synthetic/out/pdfs/{case_id}.pdf
    backend/benchmarks/synthetic/out/golden_json/{case_id}.json
    backend/benchmarks/synthetic/out/manifest.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, str(Path(__file__).parent))
from schema import (  # noqa: E402
    EducationEntry,
    ExperienceEntry,
    Location,
    Profile,
    ScenarioMeta,
    derive_gold,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
CATALOGS = ROOT / "catalogs"
OUT_PDF = ROOT / "out" / "pdfs"
OUT_GOLD = ROOT / "out" / "golden_json"
OUT_MANIFEST = ROOT / "out" / "manifest.json"

KNOWN_TEMPLATES = ["high_signal", "low_signal", "multi_col", "non_usa", "embed_link"]
ADVERSARIAL_TEMPLATES = [
    "adv_tools_header",
    "adv_tech_stack",
    "adv_paren_groups",
    "adv_spelled_state",
    "adv_remote_with_city",
    "adv_location_late",
    "adv_inline_url",
    "adv_allcaps_header",
    "adv_no_explicit_skills",
    "adv_unconventional_delim",
]

SYNTHETIC_NAMES = [
    "Alex Park", "Jamie Rivera", "Morgan Bell", "Sam Okafor", "Riley Tan",
    "Jordan Lee", "Casey Nakamura", "Drew Patel", "Quinn Aalto", "Avery Costa",
    "Sage Mensah", "Emerson Vu", "Rowan Sato", "Hayden Cruz", "Phoenix Ono",
]
COMPANIES = [
    "Alpine Systems", "Northwind Labs", "Beacon Logic", "Heron Analytics",
    "Stonecreek Software", "Quill & Ledger", "Halcyon Robotics", "Meridian Civic",
    "Cedarline Health", "Ironwood Tutoring", "Bramble Studio", "Vector Foundry",
]
DEGREES = [
    "B.S. Computer Science", "M.S. Data Science", "B.Eng. Civil Engineering",
    "B.A. Education", "B.S. Nursing", "B.A. Graphic Design", "M.B.A.",
]
INSTITUTIONS = [
    "State University of Westbridge", "Northshore Polytechnic",
    "Fairhaven College", "Ridgepoint Institute of Technology", "Kettle River University",
]


def _load_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def _make_skills_choice(rng: random.Random, skill_catalog: list, count: int) -> list[dict]:
    """Pick `count` skills with no repetition. Bias toward alias_stress=True."""
    stress = [s for s in skill_catalog if s.get("alias_stress")]
    nonstress = [s for s in skill_catalog if not s.get("alias_stress")]
    n_stress = min(len(stress), max(1, count * 2 // 3))
    n_other = count - n_stress
    chosen = rng.sample(stress, n_stress) + rng.sample(nonstress, min(len(nonstress), n_other))
    rng.shuffle(chosen)
    return chosen[:count]


def _format_skill(rng: random.Random, skill: dict) -> str:
    """Pick a random rendered variant of a skill (the catalog provides aliases)."""
    return rng.choice(skill["variants"])


def _location_for_template(rng: random.Random, locations: dict, template_name: str) -> tuple[Location, list[str]]:
    """Pick a location bundle appropriate for the template. Returns (Location, boundary_probes).

    Known templates use the canonical "City, ST" abbreviated form so they
    sit in the parser's happy path and serve as a true baseline. Adversarial
    templates explicitly pick boundary-probing forms.
    """
    if template_name == "non_usa":
        loc = rng.choice(locations["non_us"])
        raw = rng.choice(loc["raw_variants"])
        return Location(city=loc["city"], country=loc["country"], raw=raw), ["non-US location"]
    if template_name == "adv_spelled_state":
        loc = rng.choice(locations["us"])
        raw = f"{loc['city']}, {loc['state_full']}"
        return Location(city=loc["city"], country="United States", raw=raw), ["spelled-out US state name"]
    if template_name == "adv_remote_with_city":
        loc = rng.choice(locations["non_us"])
        raw = f"Remote — based in {loc['city']}"
        return Location(city=loc["city"], country=loc["country"], raw=raw), ["remote with implicit city"]
    if template_name == "adv_location_late":
        loc = rng.choice(locations["us"])
        raw = f"{loc['city']}, {loc['state_abbr']}"
        return Location(city=loc["city"], country="United States", raw=raw), ["location placed past parser's first-15-lines window"]
    # default: known templates use the canonical abbreviated form for a clean baseline
    loc = rng.choice(locations["us"])
    raw = f"{loc['city']}, {loc['state_abbr']}"
    return Location(city=loc["city"], country="United States", raw=raw), []


def _make_experience(rng: random.Random, location_raw: str, n: int = 2) -> tuple[ExperienceEntry, ...]:
    out = []
    for i in range(n):
        out.append(ExperienceEntry(
            title=rng.choice(["Senior Engineer", "Lead Analyst", "Principal Designer", "Project Lead"]),
            company=rng.choice(COMPANIES),
            location_raw=rng.choice(["Remote", location_raw, "Hybrid"]),
            dates=rng.choice(["2022 – Present", "2019 – 2022", "Jan 2020 – Dec 2022"]),
            bullets=tuple(rng.sample([
                "Owned end-to-end delivery of a multi-team initiative.",
                "Led cross-functional reviews and stakeholder alignment.",
                "Mentored junior contributors on best practices.",
                "Reduced incident response time through process improvements.",
                "Drove adoption of automated quality checks.",
            ], k=3)),
        ))
    return tuple(out)


def _make_education(rng: random.Random, location_raw: str) -> tuple[EducationEntry, ...]:
    return (EducationEntry(
        degree=rng.choice(DEGREES),
        institution=rng.choice(INSTITUTIONS),
        location_raw=location_raw,
        dates=rng.choice(["2014 – 2018", "2016 – 2020", "2010 – 2014"]),
    ),)


def _build_paren_groups(skill_choices: list[dict], rng: random.Random) -> list[dict]:
    """For adv_paren_groups: cluster skills into 'Parent (a, b, c)' style blocks.
    Returns list of {label, items, items_canonical}. Parent labels are made-up
    grouping terms; items are the chosen skills' rendered variants. """
    labels = ["Cloud", "Data", "Web", "DevOps", "ML"]
    # split into ~3 groups of 2-3 items
    groups, idx = [], 0
    rng.shuffle(skill_choices)
    while idx < len(skill_choices) and len(groups) < 3:
        size = rng.randint(2, 3)
        chunk = skill_choices[idx:idx + size]
        idx += size
        if not chunk:
            break
        label = rng.choice(labels)
        groups.append({
            "label": label,
            "members": [rng.choice(s["variants"]) for s in chunk],
            "members_canonical": [s["canonical"] for s in chunk],
        })
    return groups


def _build_profile(case_id: str, template_name: str, master_seed: int, idx: int,
                   skill_catalog: list, locations: dict) -> tuple[Profile, dict]:
    """Returns (profile, render_extras). render_extras carries template-specific
    pieces like rendered_skills (with chosen variants) and paren_groups."""
    rng = random.Random((master_seed * 1_000_003) ^ (idx * 31337))

    location, probes = _location_for_template(rng, locations, template_name)

    skill_count = {
        "high_signal": rng.randint(8, 14),
        "low_signal": rng.randint(3, 5),
        "multi_col": rng.randint(8, 12),
        "non_usa": rng.randint(5, 9),
        "embed_link": rng.randint(6, 10),
    }.get(template_name, rng.randint(5, 10))

    # adv_no_explicit_skills: profile has no explicit skills
    if template_name == "adv_no_explicit_skills":
        skill_choices = []
    else:
        skill_choices = _make_skills_choice(rng, skill_catalog, skill_count)

    rendered_skills = [_format_skill(rng, s) for s in skill_choices]
    canonical_skills = [s["canonical"] for s in skill_choices]
    alias_stress_skills = tuple(s["canonical"] for s in skill_choices if s.get("alias_stress"))

    if template_name == "adv_paren_groups":
        # Skills are organised into parenthesised groups. Gold should record
        # each leaf item AND the parent label per labeling_rules_v1.md.
        groups = _build_paren_groups(skill_choices, rng)
        flat_canonical = []
        for g in groups:
            flat_canonical.append(g["label"])
            flat_canonical.extend(g["members_canonical"])
        canonical_skills = flat_canonical
        probes = list(probes) + ["parenthesised skill groups (parent + leaf extraction)"]
        render_extras = {"paren_groups": groups, "rendered_skills": rendered_skills}
    elif template_name == "adv_tools_header":
        probes = list(probes) + ["plain Tools header (parser only matches Tools & Technologies)"]
        render_extras = {"rendered_skills": rendered_skills, "paren_groups": []}
    elif template_name == "adv_tech_stack":
        probes = list(probes) + ["Tech Stack header (not in parser pattern list)"]
        render_extras = {"rendered_skills": rendered_skills, "paren_groups": []}
    elif template_name == "adv_inline_url":
        probes = list(probes) + ["URL embedded inline within skill bullet"]
        render_extras = {"rendered_skills": rendered_skills, "paren_groups": []}
    elif template_name == "adv_allcaps_header":
        probes = list(probes) + ["all-caps non-standard skills header (Technical Toolkit)"]
        render_extras = {"rendered_skills": rendered_skills, "paren_groups": []}
    elif template_name == "adv_no_explicit_skills":
        probes = list(probes) + ["no explicit Skills section — negative control"]
        render_extras = {"rendered_skills": [], "paren_groups": []}
    elif template_name == "adv_unconventional_delim":
        probes = list(probes) + [r"unconventional ' / ' delimiter (not in parser split set)"]
        render_extras = {"rendered_skills": rendered_skills, "paren_groups": []}
    else:
        render_extras = {"rendered_skills": rendered_skills, "paren_groups": []}

    name = rng.choice(SYNTHETIC_NAMES)
    email = f"{name.lower().replace(' ', '.')}@example.test"
    phone = f"+1-555-{rng.randint(100, 999):03d}-{rng.randint(1000, 9999):04d}"

    experience = _make_experience(rng, location.raw)
    education = _make_education(rng, location.raw)

    category = "known" if template_name in KNOWN_TEMPLATES else f"adversarial:{template_name}"

    meta = ScenarioMeta(
        case_id=case_id,
        category=category,
        template=template_name,
        seed=master_seed,
        alias_stress_skills=alias_stress_skills,
        boundary_probes=tuple(probes),
        notes="",
    )

    profile = Profile(
        case_id=case_id,
        name=name,
        email=email,
        phone=phone,
        location=location,
        skills=tuple(canonical_skills),
        tools=(),
        experience=experience,
        education=education,
        meta=meta,
    )
    return profile, render_extras


def _select_template(idx: int, total: int, adversarial_ratio: float = 0.30,
                     known_rng: random.Random | None = None,
                     adv_rng: random.Random | None = None) -> str:
    n_adv = int(round(total * adversarial_ratio))
    n_known = total - n_adv
    if idx < n_known:
        # cycle deterministically through known templates
        return KNOWN_TEMPLATES[idx % len(KNOWN_TEMPLATES)]
    adv_idx = idx - n_known
    return ADVERSARIAL_TEMPLATES[adv_idx % len(ADVERSARIAL_TEMPLATES)]


def _render_pdf(env: Environment, css: str, template_name: str, profile: Profile,
                render_extras: dict, out_path: Path) -> None:
    from weasyprint import HTML
    template = env.get_template(f"{template_name}.html.j2")
    html = template.render(
        profile=profile,
        css=css,
        rendered_skills=render_extras.get("rendered_skills", []),
        paren_groups=render_extras.get("paren_groups", []),
    )
    HTML(string=html).write_pdf(target=str(out_path))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--adversarial-ratio", type=float, default=0.30)
    ap.add_argument("--annotation-version", choices=["v1", "v2"], default="v1",
                     help="Benchmark annotation schema to derive gold.json in (#347).")
    ap.add_argument("--validate", action="store_true",
                     help="Run consistency + canonical corpus validation (#344/#349) after generation "
                          "and exit non-zero if the corpus isn't benchmark-ready.")
    args = ap.parse_args()

    OUT_PDF.mkdir(parents=True, exist_ok=True)
    OUT_GOLD.mkdir(parents=True, exist_ok=True)

    skill_catalog = _load_json(CATALOGS / "skills.json")["skills"]
    locations = _load_json(CATALOGS / "locations.json")
    css = (TEMPLATES / "_base.css").read_text()
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html", "xml"]))

    manifest = {"seed": args.seed, "count": args.count,
                "adversarial_ratio": args.adversarial_ratio,
                "annotation_version": args.annotation_version, "cases": []}

    for idx in range(args.count):
        template_name = _select_template(idx, args.count, args.adversarial_ratio)
        case_id = f"syn_{idx:03d}_{template_name}"
        profile, extras = _build_profile(case_id, template_name, args.seed, idx,
                                         skill_catalog, locations)
        gold = derive_gold(profile, version=args.annotation_version)
        gold_path = OUT_GOLD / f"{case_id}.json"
        pdf_path = OUT_PDF / f"{case_id}.pdf"

        with open(gold_path, "w") as f:
            json.dump(gold, f, indent=2, ensure_ascii=False)
            f.write("\n")
        _render_pdf(env, css, template_name, profile, extras, pdf_path)

        manifest["cases"].append({
            "case_id": case_id,
            "template": template_name,
            "category": profile.meta.category,
            "alias_stress_skills": list(profile.meta.alias_stress_skills),
            "boundary_probes": list(profile.meta.boundary_probes),
            "skill_count": len(profile.skills),
            "location_raw": profile.location.raw,
            "location_country": profile.location.country,
        })
        print(f"[{idx+1}/{args.count}] {case_id}")

    with open(OUT_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote {args.count} cases. Manifest: {OUT_MANIFEST}")
    print(f"PDFs:  {OUT_PDF}")
    print(f"Gold:  {OUT_GOLD}")

    if args.validate:
        from validate_generated import validate_generated
        print()
        if not validate_generated(OUT_PDF, OUT_GOLD):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
