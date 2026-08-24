"""Profile + scenario schema and deterministic gold derivation.

The profile is the single source of truth for a synthetic case. The renderer
turns it into HTML/PDF; the gold emitter derives gold.json directly from it
for the selected benchmark annotation schema.
"""
from __future__ import annotations

import string
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Location:
    city: Optional[str]
    country: Optional[str]
    raw: str


@dataclass(frozen=True)
class ExperienceEntry:
    title: str
    company: str
    location_raw: str
    dates: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class EducationEntry:
    degree: str
    institution: str
    location_raw: str
    dates: str


@dataclass(frozen=True)
class ScenarioMeta:
    case_id: str
    category: str
    template: str
    seed: int
    alias_stress_skills: tuple[str, ...] = ()
    boundary_probes: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class Profile:
    case_id: str
    name: str
    email: str
    phone: str
    location: Location
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    experience: tuple[ExperienceEntry, ...]
    education: tuple[EducationEntry, ...]
    meta: ScenarioMeta

    def to_dict(self) -> dict:
        return asdict(self)


def _normalized_skills(profile: Profile) -> list[str]:
    seen: set[str] = set()
    skills_normalized: list[str] = []
    for s in (*profile.skills, *profile.tools):
        norm = s.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        skills_normalized.append(norm)
    return skills_normalized


def _v2_display_skills(profile: Profile) -> list[str]:
    """Return V2 root skills with canonical display casing preserved.

    V2 goldens keep first-observed casing while deduping on the normalized
    comparison key described by the canonical annotation spec. The synthetic
    Profile already carries canonical skill labels, so this function only
    trims and dedupes without rewriting display text.
    """
    seen: set[str] = set()
    skills: list[str] = []
    for skill in (*profile.skills, *profile.tools):
        display = skill.strip()
        key = display.casefold().translate(str.maketrans("", "", string.punctuation))
        if not key or key in seen:
            continue
        seen.add(key)
        skills.append(display)
    return skills


def derive_gold_v1(profile: Profile) -> dict:
    """Derive gold.json from a profile per labeling_rules_v1.md.

    Rules:
      - Skills come only from explicit Skills/Tools sections (not experience).
      - Lowercase, trim, dedupe (preserve first occurrence order).
      - Location uses profile.location.{city, country} canonical form;
        raw mirrors what the rendered resume actually shows.
      - city/country may be null if the rendered raw is intentionally
        unresolvable (e.g. fictional place, ambiguous format).
    """
    return {
        "submission_id": profile.case_id,
        "skills": _normalized_skills(profile),
        "location": {
            "city": profile.location.city,
            "country": profile.location.country,
            "raw": profile.location.raw,
        },
        "notes": {
            "ambiguities": list(profile.meta.boundary_probes),
        },
    }


def derive_gold_v2(profile: Profile) -> dict:
    """Derive a canonical V2 golden per backend/benchmarks/v2_annotation_spec.md.

    Section order (SKILLS, EXPERIENCE, EDUCATION) is a fixed derivation
    order, not a literal rendered layout — the Profile IR does not carry
    template section ordering. Sections with no source content are omitted
    rather than emitted empty.
    """
    sections: list[dict] = []

    raw_skills = [s.strip() for s in (*profile.skills, *profile.tools) if s.strip()]
    if raw_skills:
        sections.append({"heading": "SKILLS", "items": [", ".join(raw_skills)]})

    if profile.experience:
        sections.append({
            "heading": "EXPERIENCE",
            "items": [
                {
                    "title": f"{entry.title}, {entry.company}",
                    "meta": entry.dates or None,
                    "subtitle": entry.location_raw or None,
                    "bullets": list(entry.bullets),
                }
                for entry in profile.experience
            ],
        })

    if profile.education:
        sections.append({
            "heading": "EDUCATION",
            "items": [
                {
                    "title": entry.institution,
                    "meta": entry.dates or None,
                    "subtitle": entry.degree or None,
                    "bullets": [],
                }
                for entry in profile.education
            ],
        })

    boundary_probes = list(profile.meta.boundary_probes)

    return {
        "resume_id": profile.case_id,
        "source_persona": f"{profile.meta.category} synthetic case",
        "persona": profile.meta.template,
        "name": profile.name or None,
        "email": profile.email or None,
        "phone": profile.phone or None,
        "location": {
            "city": profile.location.city or "",
            "country": profile.location.country or "",
            "raw": profile.location.raw,
        } if profile.location.raw else None,
        "links": [],
        "skills": _v2_display_skills(profile),
        "notes": {"ambiguities": boundary_probes} if boundary_probes else None,
        "sections": sections,
    }


ANNOTATION_DERIVERS = {
    "v1": derive_gold_v1,
    "v2": derive_gold_v2,
}


def derive_gold(profile: Profile, version: str = "v1") -> dict:
    """Versioned annotation derivation entry point (see #347).

    The synthetic Profile is the single source of truth; this dispatches to
    the deriver for the requested annotation schema version without
    affecting profile generation, rendering, or determinism.
    """
    try:
        deriver = ANNOTATION_DERIVERS[version]
    except KeyError:
        raise ValueError(
            f"Unsupported annotation version {version!r}; expected one of {sorted(ANNOTATION_DERIVERS)}"
        )
    return deriver(profile)
