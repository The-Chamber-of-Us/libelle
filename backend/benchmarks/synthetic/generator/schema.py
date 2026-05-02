"""Profile + scenario schema and deterministic gold derivation.

The profile is the single source of truth for a synthetic case. The renderer
turns it into HTML/PDF; the gold emitter derives gold.json directly from it
following labeling_rules_v1.md.
"""
from __future__ import annotations

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


def derive_gold(profile: Profile) -> dict:
    """Derive gold.json from a profile per labeling_rules_v1.md.

    Rules:
      - Skills come only from explicit Skills/Tools sections (not experience).
      - Lowercase, trim, dedupe (preserve first occurrence order).
      - Location uses profile.location.{city, country} canonical form;
        raw mirrors what the rendered resume actually shows.
      - city/country may be null if the rendered raw is intentionally
        unresolvable (e.g. fictional place, ambiguous format).
    """
    seen: set[str] = set()
    skills_normalized: list[str] = []
    for s in (*profile.skills, *profile.tools):
        norm = s.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        skills_normalized.append(norm)

    return {
        "submission_id": profile.case_id,
        "skills": skills_normalized,
        "location": {
            "city": profile.location.city,
            "country": profile.location.country,
            "raw": profile.location.raw,
        },
        "notes": {
            "ambiguities": list(profile.meta.boundary_probes),
        },
    }
