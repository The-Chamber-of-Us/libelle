# Labeling Rules v2

These notes document the synthetic v2 resume slice created from the Phase 1 persona proposal. The resumes use fake identities and intentionally realistic parser edge cases rather than unusual visual layouts.

## Contact and Links

- Treat top-header links as candidate-level profile links unless a link appears inside a project entry.
- Preserve non-US phone and location formats as written. Do not coerce UK or Canadian addresses into US city/state/ZIP fields.
- If a contact line is awkward but readable, label only explicit fields. Do not infer missing state, country, or ZIP/postcode components.

## Skills

- Split slash-combined skills only when both sides are independently meaningful skills, such as `AWS/GCP`.
- Keep named frameworks attached to languages when written as a common stack phrase, such as `Python/Django`, unless the benchmark schema requires individual skill tokens.
- Treat section headers such as `Technical Toolkit`, `Core Competencies`, and `Specialised Skills` as skills-equivalent sections when the content is primarily tools, languages, platforms, or professional competencies.

## Projects and Experience

- Project-specific demo or GitHub links should stay attached to the project entry, not the candidate profile.
- Class projects, independent projects, and volunteer technical builds should be labeled as projects when they have a project title and implementation details.
- Operational or healthcare roles with technical tasks remain experience entries. Technical bullets inside those roles should not cause the role itself to be relabeled as a project.

## Academic and Research Sections

- `Research Experience` entries should be labeled as experience when they describe a role, lab, institution, dates, and responsibilities.
- Publications and presentations should remain separate academic outputs. Do not label them as jobs or projects even when they include dates, locations, or links.

## Ordering and Ambiguity

- Do not assume section order. Resume 210 intentionally starts with projects and skills before work history and education.
- Resume 209 intentionally mixes date and location placement. Associate dates/locations with the closest role unless another role line clearly owns them.
- Resume 208 uses `Selected Work`-style content under `Impact Highlights`; label entries by their content. If no employer/client context is present, treat them as projects or accomplishments rather than formal employment.
