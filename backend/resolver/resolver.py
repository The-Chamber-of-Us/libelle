from typing import Dict, Optional, List, Set, Tuple

from .normalize import normalize_key
from .schemas import (
    ExtractedProfileV1,
    ResolvedProfileV1,
    ResolvedFieldsV1,
    UnknownsV1,
    ResolverStatsV1,
)


def resolve_extracted_profile(
    extracted: ExtractedProfileV1,
    aliases: Dict[str, str],
    *,
    resolver_version: str = "v1",
    aliases_version: Optional[str] = None,
) -> ResolvedProfileV1:
    """
    Pure function: JSON in -> JSON out. No I/O.
    Resolves extracted skills to canonical IDs using aliases,
    calculates coverage stats, and preserves unknowns.
    """

    # 1. Setup
    resolved_skill_ids: List[str] = []
    unknown_candidates: List[Tuple[str, str]] = []  # (normalized_key, raw)
    unique_input_keys: Set[str] = set()

    # 2. Resolve Skills
    for raw_skill in extracted.skills:
        clean_key = normalize_key(raw_skill)

        if not clean_key:
            unknown_candidates.append(("<empty>", raw_skill))
            continue

        unique_input_keys.add(clean_key)

        if clean_key in aliases:
            resolved_skill_ids.append(aliases[clean_key])
        else:
            unknown_candidates.append((clean_key, raw_skill))

    # 3. Deduplicate Resolved Skills (preserve first-seen order)
    final_resolved_skills: List[str] = []
    seen_skill_ids: Set[str] = set()

    for skill_id in resolved_skill_ids:
        if skill_id not in seen_skill_ids:
            seen_skill_ids.add(skill_id)
            final_resolved_skills.append(skill_id)

    # 4. Deduplicate Unknowns by KEY (preserve first-seen raw string)
    final_unknown_skills: List[str] = []
    seen_unknown_keys: Set[str] = set()

    for key, raw in unknown_candidates:
        if key not in seen_unknown_keys:
            seen_unknown_keys.add(key)
            final_unknown_skills.append(raw)

    # 5. Calculate Coverage Stats
    matched_keys = unique_input_keys.intersection(aliases.keys())
    denominator = len(unique_input_keys)
    coverage = len(matched_keys) / denominator if denominator > 0 else 0.0

    stats = ResolverStatsV1(
        coverage=coverage,
        input_count=denominator,
        resolved_count=len(matched_keys),
        unknown_count=len(unique_input_keys - matched_keys),
    )

    # 6. Assemble Output Schemas
    resolved_fields = ResolvedFieldsV1(
        skills=final_resolved_skills,
        location={
            "raw": extracted.location_raw,
            "city": None,
            "state": None,
            "country": None,
        },
    )

    unknowns = UnknownsV1(
        skills=final_unknown_skills,
        location=[],
    )

    # 7. Return Final Profile
    return ResolvedProfileV1(
        submission_id=extracted.submission_id,
        resolved=resolved_fields,
        unknowns=unknowns,
        stats=stats,
        meta={
            "resolver_version": resolver_version,
            "aliases_version": aliases_version or "unknown",
        },
    )
