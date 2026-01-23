from typing import Dict, Optional

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

    TODO (Chechu):
      - normalize inputs
      - map skills using aliases
      - fill ResolvedFieldsV1 + UnknownsV1 + ResolverStatsV1
      - return ResolvedProfileV1
    """
    raise NotImplementedError("Chechu: Implement the resolution logic here.")
