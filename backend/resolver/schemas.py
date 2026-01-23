# backend/resolver/schemas.py
from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# --- Pydantic v1/v2 compatible "forbid extras" config ---
try:
    # Pydantic v2
    from pydantic import ConfigDict  # type: ignore

    class _StrictModel(BaseModel):
        model_config = ConfigDict(extra="forbid")
except Exception:
    # Pydantic v1
    class _StrictModel(BaseModel):
        class Config:
            extra = "forbid"


# -------------------------
# Input schema (from Extractor)
# -------------------------

class ExtractedProfileV1(_StrictModel):
    """
    What resolver consumes.

    NOTE: This matches your fixture:
      submission_id, skills, location_raw, meta
    """
    submission_id: str = Field(..., description="Stable ID for the submission (UUID or test id).")
    skills: List[str] = Field(default_factory=list, description="Raw skill strings extracted from the resume.")
    location_raw: Optional[str] = Field(default=None, description="Raw location string as extracted.")
    meta: Dict[str, str] = Field(default_factory=dict, description="Lightweight metadata (string values only).")


# -------------------------
# Output schemas (from Resolver)
# -------------------------

class ResolvedLocationV1(_StrictModel):
    """
    Minimal location output for v1.
    Resolver should not guess globally. If unsure, leave fields null and keep raw.
    """
    raw: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None


class ResolverStatsV1(_StrictModel):
    input_count: int = 0
    resolved_count: int = 0
    unknown_count: int = 0
    coverage: float = 0.0  # 0.0 - 1.0


class ResolvedFieldsV1(_StrictModel):
    """
    The 'resolved' payload is explicit so it can't silently change.
    """
    skills: List[str] = Field(default_factory=list, description="Canonical skill strings (v1).")
    location: ResolvedLocationV1 = Field(default_factory=ResolvedLocationV1)


class UnknownsV1(_StrictModel):
    skills: List[str] = Field(default_factory=list)
    location: List[str] = Field(default_factory=list)


class ResolvedProfileV1(_StrictModel):
    """
    What resolver returns (pure function output).
    """
    submission_id: str
    resolved: ResolvedFieldsV1 = Field(default_factory=ResolvedFieldsV1)
    unknowns: UnknownsV1 = Field(default_factory=UnknownsV1)
    stats: ResolverStatsV1 = Field(default_factory=ResolverStatsV1)
    meta: Dict[str, str] = Field(
        default_factory=dict,
        description="Versions etc (resolver_version, aliases_version). String values only.",
    )
