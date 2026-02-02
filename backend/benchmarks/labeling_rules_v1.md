# Labeling Rules v1

This document defines the labeling and normalization rules used to generate Golden JSON files for the resume parsing benchmark.

## Skill Normalization

- Skills are extracted only from explicit "Skills" sections.
- Skills are normalized by:
  - converting to lowercase
  - trimming whitespace
  - removing duplicates
- Skill group headers (e.g., "Programming Languages") are ignored.
- No skills are inferred from experience or project descriptions.

## Location Handling

- Location is resolved using the most explicit contact or header location.
- If multiple locations are mentioned:
  - the header/contact location is preferred
  - experience and education locations are treated as secondary
- If a city or country cannot be confidently resolved:
  - the field is set to null
- The original location text is preserved in `location.raw`.

## Ambiguities

- Ambiguities are recorded when multiple plausible interpretations exist
  (e.g., multiple cities listed in experience).
- Document features such as hyperlinks or formatting are not considered ambiguities unless they affect interpretation.
