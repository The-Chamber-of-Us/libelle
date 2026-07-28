# Canonical V2 Golden JSON Annotation Specification

This is the source of truth for creating and reviewing V2 benchmark golden
JSON annotations. It defines what the golden files represent, not what the
current parser already emits.

Historical context is preserved in `labeling_rules_v1.md` and
`labeling_rules_v2.md`, but new V2 annotations should follow this file.

## Purpose

A V2 golden is human-reviewed benchmark truth for a resume fixture. It records:

- normalized candidate-level fields used by current benchmark scoring;
- source-faithful section structure used by future structural scoring;
- reviewer notes about ambiguity, fixture traps, or source quality.

Do not change production parser behavior, benchmark scoring, or corpus layout
just to satisfy this document. This specification describes annotation policy.

## Root Schema

Each V2 golden is a JSON object with these top-level fields.

| Field | Type | Presence | Empty value | Example |
| --- | --- | --- | --- | --- |
| `resume_id` | string | required | never empty | `"resume_201"` |
| `source_persona` | string | required | `""` only if unknown | `"Nadia Patel benchmark slice"` |
| `persona` | string | required | `""` only if unknown | `"Sparse Early-Career Resume"` |
| `name` | string or null | required, nullable | `null` if absent | `"Maya R. Wong"` |
| `email` | string or null | required, nullable | `null` if absent | `"maya.wong@gmail.com"` |
| `phone` | string or null | required, nullable | `null` if absent | `"(315) 555-0184"` |
| `location` | object or null | required, nullable | `null` if no primary candidate location | `{"city":"Ithaca","country":"United States","raw":"Ithaca, NY"}` |
| `links` | array of strings | required | `[]` | `["github.com/mayarwong"]` |
| `skills` | array of strings | required | `[]` | `["Python","React","SQL"]` |
| `notes` | string, object, or null | required | `null` if no notes | `"Low-signal recent graduate."` |
| `sections` | array of section objects | required | `[]` only for intentionally sectionless source | `[{"heading":"SKILLS","items":["Python, SQL"]}]` |

Prefer keeping all root fields present even when values are absent. Use `null`
for absent scalar facts, `[]` for absent lists, and `""` only when a field is
known to exist but the exact text is unknown or intentionally withheld.

### Location Object

When `location` is not `null`, it has this shape:

```json
{
  "city": "Ithaca",
  "country": "United States",
  "raw": "Ithaca, NY"
}
```

`city` and `country` are normalized when they can be resolved confidently.
`raw` preserves the candidate-level contact/header text. If the raw location is
visible but cannot be confidently normalized, keep `raw` and set unknown
components to `""`:

```json
{
  "city": "",
  "country": "",
  "raw": "Remote"
}
```

## Sections Schema

`sections` preserves source order and resume structure. Each section object has:

```json
{
  "heading": "EXPERIENCE",
  "items": []
}
```

| Field | Type | Presence | Empty value | Example |
| --- | --- | --- | --- | --- |
| `heading` | string | required | never empty | `"PROJECTS"` |
| `items` | array of strings or objects | required | `[]` only for visible empty/truncated section | `["Python, SQL"]` |

Use the heading text as it appears after obvious whitespace cleanup. Do not
normalize unusual headings into canonical labels: `TECHNICAL TOOLKIT`,
`PROFESSIONAL BACKGROUND`, and `IMPACT HIGHLIGHTS` should remain source-faithful.

### Plain String Items

Use plain strings for section content that is a paragraph, comma-separated line,
or list where internal structure is not being asserted.

Section types that normally use plain strings:

- objective, summary, profile, and personal statement sections;
- skills, tools, technical toolkit, competencies, and languages sections;
- simple interests or additional information sections;
- malformed fragments where structure would require invention.

Example:

```json
{
  "heading": "TECHNICAL TOOLKIT",
  "items": [
    "Salesforce, Excel, SQL, Tableau, Looker Studio, Zendesk, Notion"
  ]
}
```

### Structured Object Items

Use structured objects when the source contains an entry with a title-like line,
date/location/employer metadata, optional subtitle, and bullet-like details.

Section types that normally use structured objects:

- experience, professional background, research experience, and leadership;
- education and academic training;
- projects, selected work, portfolio, and class projects;
- certifications, awards, publications, and presentations when they include
  enough entry-level metadata to structure without invention.

Mixed item types inside one section are allowed only when the source itself is
mixed. For example, a `CERTIFICATIONS` section can contain one standalone
certification string and one structured award entry. Prefer not to mix types in
new synthetic fixtures unless the mixed structure is an intentional benchmark
case.

## Structured Entry Fields

A structured section item is an object with these fields:

| Field | Type | Presence | Empty value | Meaning |
| --- | --- | --- | --- | --- |
| `title` | string | required | never empty | Primary label for the entry: role, institution, project, certification, award, publication, or presentation. |
| `meta` | string or null | required, nullable | `null` if absent | Date range, completion date, term, year, or compact metadata line closest to the title. |
| `subtitle` | string or null | required, nullable | `null` if absent | Secondary line such as employer, degree, location, project type, issuer, or context. |
| `bullets` | array of strings | required | `[]` | Bullet text, continuation lines, coursework, honors, or entry details. |

Preserve source wording in these fields except for whitespace cleanup. Do not
infer missing dates, employers, degrees, issuers, or locations.

### Experience Example

```json
{
  "title": "Library Technology Assistant, Cornell University Library",
  "meta": "Aug 2024-May 2026",
  "subtitle": "Ithaca, NY",
  "bullets": [
    "Resolved 10-15 weekly student support tickets involving printing, classroom displays, and account access.",
    "Created a short troubleshooting checklist that reduced repeat escalation for common scanner setup issues."
  ]
}
```

### Education Example

```json
{
  "title": "Cornell University, College of Computing and Information Science, Ithaca, NY",
  "meta": "May 2026",
  "subtitle": "Bachelor of Science in Computer Science, Minor in Biology",
  "bullets": [
    "GPA: 3.41; Dean's List, Spring 2025",
    "Relevant Courses: Data Structures, Databases, Web Programming, Human-Computer Interaction"
  ]
}
```

### Project Example

```json
{
  "title": "Course Planner Web App",
  "meta": "Jan-May 2026",
  "subtitle": "Class project",
  "bullets": [
    "Built a React and Flask prototype that let classmates compare course combinations against graduation requirements.",
    "Created SQLite seed data and validation checks for duplicate courses and missing prerequisites."
  ]
}
```

### Certification Or Award Example

```json
{
  "title": "Certified Salesforce Administrator",
  "meta": "2025",
  "subtitle": "Salesforce",
  "bullets": []
}
```

For a simple certification line such as `AWS Certified Cloud Practitioner,
2025`, a plain string is also valid if the source does not present it as a
structured entry.

## Skill Normalization

Root `skills` is normalized benchmark truth. Section text remains
source-faithful.

Use these rules for root `skills`:

- Extract skills only from explicit skills-equivalent sections such as `SKILLS`,
  `TOOLS`, `TECHNICAL TOOLKIT`, `CORE COMPETENCIES`, or equivalent headings.
- Do not infer skills from experience, education, projects, or publications.
- Keep first-observed casing for canonical display unless the corpus has an
  established spelling, such as `SQL`, `VBA`, `EPA`, `NEPA`, `GWAS`, or
  `ACE/ADE`.
- Trim whitespace and remove duplicate values after case-insensitive and
  punctuation-insensitive comparison.
- Ignore category labels such as `Languages`, `Platforms`, or `Methods` when
  they are only grouping headers.
- Preserve independently meaningful multi-word concepts, such as `customer
  onboarding analytics` or `structural load calculations`.
- Drop pure proficiency modifiers such as `basic`, `advanced`, `beginner`, or
  `expert` when they only modify a skill. For example, `SQL basics` becomes
  `SQL`. Keep the modifier only if it is part of a named concept.
- Split slash-combined or comma-combined skills when each side is independently
  meaningful, such as `AWS/GCP` into `AWS` and `GCP`.
- Keep relationship-preserving stack phrases when splitting would create a
  misleading fact. `Python/Django` may remain `Python/Django` if the source
  presents it as one stack phrase and the benchmark is not asserting separate
  proficiency in both. If separate skills are required for a fixture, write both
  explicitly in the source section.
- For parenthetical content, extract the parent term and independently
  meaningful parenthetical items. `Statistical modeling (GWAS, ACE/ADE)` becomes
  `Statistical modeling`, `GWAS`, and `ACE/ADE`.
- Preserve acronyms and expanded forms as separate skills only when both appear
  and both are useful benchmark targets. If the expanded form is merely a gloss
  for an acronym, prefer the acronym used elsewhere in the corpus.
- Normalize punctuation only when it does not change meaning. Do not rewrite
  `STAAD.Pro`, `C++`, `C#`, `Node.js`, or `ACE/ADE` into lossy forms.

Skills-normalization example:

```json
{
  "heading": "SKILLS",
  "items": [
    "Advanced SQL; basic Python; AWS/GCP; VBA macros; EPA and NEPA permitting; Statistical genetics (GWAS, ACE/ADE)"
  ]
}
```

Root skills:

```json
[
  "SQL",
  "Python",
  "AWS",
  "GCP",
  "VBA",
  "EPA",
  "NEPA",
  "Statistical genetics",
  "GWAS",
  "ACE/ADE"
]
```

## Location Handling

The root `location` is the candidate's primary contact/header location. It is
the only location currently scored by `scripts/benchmark.py`.

Use these rules:

- Prefer the explicit header/contact location over locations in body sections.
- Preserve non-US formats in `raw`; normalize only `city` and `country` when
  confidence is high.
- Employer, education, project, research, award, or certification locations
  belong inside the relevant structured entry text, usually `subtitle` or
  `title`, depending on source layout.
- Secondary locations should not be promoted to root `location`.
- If body sections contain locations but the header has none, set root
  `location` to `null` unless the source clearly labels one body location as
  the candidate's address.
- For conflicting candidate-level locations, choose the most explicit current
  contact/header value and record the conflict in `notes`.
- For fictional, malformed, or ambiguous locations, preserve the visible text in
  `raw` and leave unresolved components empty.

Secondary-location example:

```json
{
  "location": {
    "city": "Jersey City",
    "country": "United States",
    "raw": "Jersey City, NJ"
  },
  "sections": [
    {
      "heading": "PROFESSIONAL BACKGROUND",
      "items": [
        {
          "title": "Revenue Operations Associate, Clearpath Software",
          "meta": "Jan 2024-Present",
          "subtitle": "New York, NY",
          "bullets": [
            "Maintain Salesforce fields and weekly pipeline dashboards."
          ]
        }
      ]
    }
  ]
}
```

The employer location stays in `subtitle`; the root location remains the
candidate contact location.

## Malformed Or Ambiguous Source Content

Golden annotations should preserve intentional benchmark traps and correct only
accidental fixture-generation mistakes.

Use these rules:

- Truncated text: preserve visible text exactly after whitespace cleanup. If the
  truncation prevents confident structure, use a plain string and explain in
  `notes`.
- Mislabeled section headings: preserve the heading as written. Label item
  structure by content. For example, project entries under `CERTIFICATIONS`
  should stay under the `CERTIFICATIONS` heading but may use project-style
  structured objects.
- Project content under a certification or award heading: structure the entries
  if possible and record the mismatch in `notes` if it is intentional.
- Missing dates: set `meta` to `null`; do not invent dates.
- Ambiguous employer/title ordering: preserve the visible ordering in `title`
  when no confident split exists. Record uncertainty in `notes`.
- Layout artifacts: remove repeated page numbers, obvious column-break debris,
  bullets without content, and duplicated headers/footers unless the artifact is
  an intentional parser trap.
- Source typos: preserve typos in section text and structured fields. Normalize
  root `skills` only when the intended skill is unambiguous and already covered
  by corpus spelling.
- Intentional benchmark trap: keep the trap in the golden and describe the
  expected annotation decision in `notes`.
- Accidental fixture-generation mistake: fix the golden if the source PDF is
  correct; otherwise open a separate issue for fixture repair.
- Uncertainty: record it in `notes` as a string or object. Use an object when
  multiple uncertainties need separate keys.

Ambiguous-source example:

```json
{
  "notes": {
    "ambiguities": [
      "The CERTIFICATIONS heading contains one project-like entry; preserve the heading and structure the item by content.",
      "The second role has no visible dates, so meta is null."
    ]
  },
  "sections": [
    {
      "heading": "CERTIFICATIONS",
      "items": [
        {
          "title": "Neighborhood Air Quality Dashboard",
          "meta": "2025",
          "subtitle": "Community project",
          "bullets": [
            "Mapped EPA sensor exports and published a weekly summary."
          ]
        }
      ]
    }
  ]
}
```

## Golden Schema Versus Parser Output

The V2 golden schema is broader than current parser output.

Current `scripts/benchmark.py` adapts parser output into this scoring shape:

```json
{
  "submission_id": "resume_201",
  "skills": ["Python", "SQL"],
  "location": {
    "city": "Ithaca",
    "country": "United States",
    "raw": "Ithaca, NY"
  },
  "metadata": {
    "parser_name": "libelle",
    "runtime_ms": 12.34
  }
}
```

Current scoring uses:

- root `skills`;
- root `location`;
- resolver-normalized `skills_resolved`.

Current parser output does not produce these V2 golden fields in the benchmark
adapter:

- `resume_id`;
- `source_persona`;
- `persona`;
- `name`;
- `email`;
- `phone`;
- `links`;
- `notes`;
- `sections`.

Current benchmark scoring does not score `name`, `email`, `phone`, `links`,
`notes`, or any `sections` content. Future structural evaluators should treat
`sections` as golden truth, but should not assume current parser parity.

## Schema Identification And Corpus Membership

Do not infer schema version from directory alone. Identify a golden by shape:

- V1-shaped goldens have `submission_id`, `skills`, `location`, and usually
  `notes`, with no required `sections`.
- V2-shaped goldens have `resume_id`, candidate contact fields, `links`,
  `skills`, `notes`, and required `sections`.

Current benchmark layout:

- `backend/benchmarks/golden_json/*.json`: root corpus. As of this spec, these
  are legacy V1-shaped goldens for `embed_link_01`, `embed_link_02`,
  `high_signal_01`, `high_signal_02`, `low_signal_01`, `low_signal_02`,
  `multi_col_01`, `multi_col_02`, `non_usa_01`, and `non_usa_02`.
- `backend/benchmarks/resumes/*.pdf`: root corpus PDFs matched by the default
  benchmark invocation.
- `backend/benchmarks/golden_json/v2/*.json`: V2 slice goldens for
  `resume_201` through `resume_210`.
- `backend/benchmarks/resumes/v2/*.pdf`: V2 slice PDFs for `resume_201` through
  `resume_210`.

Default invocation:

```bash
python scripts/benchmark.py
```

This reads PDFs directly under `backend/benchmarks/resumes` and goldens directly
under `backend/benchmarks/golden_json`. It does not recurse into `v2/`.

Explicit V2 slice invocation:

```bash
python scripts/benchmark.py \
  --pdf_dir backend/benchmarks/resumes/v2 \
  --golden_dir backend/benchmarks/golden_json/v2
```

For future tooling:

- identify schema by required fields, not by path;
- identify corpus or slice by an explicit manifest when one exists;
- until a manifest exists, path may be used only as a corpus hint;
- the future V2 structural evaluator should default to V2-shaped goldens in the
  intended V2 corpus or manifest, and should fail closed if both root and slice
  contain V2-shaped fixtures with no explicit selection.

Directory migration or manifest-based corpus membership would be useful, but it
is outside this issue. Propose it separately with an impact assessment before
moving files.

## Complete Valid V2 Golden

```json
{
  "resume_id": "resume_999",
  "source_persona": "Synthetic benchmark example",
  "persona": "Early Career Data Analyst",
  "name": "Jordan Lee",
  "email": "jordan.lee@gmail.com",
  "phone": "(555) 010-0199",
  "location": {
    "city": "Chicago",
    "country": "United States",
    "raw": "Chicago, IL"
  },
  "links": [
    "linkedin.com/in/jordanlee",
    "github.com/jordanlee"
  ],
  "skills": [
    "SQL",
    "Python",
    "Tableau",
    "Excel",
    "EPA"
  ],
  "notes": "Example fixture for the V2 annotation specification.",
  "sections": [
    {
      "heading": "SUMMARY",
      "items": [
        "Data analyst focused on public-sector reporting and operational dashboards."
      ]
    },
    {
      "heading": "EXPERIENCE",
      "items": [
        {
          "title": "Data Analyst, Civic Metrics Lab",
          "meta": "Jun 2024-Present",
          "subtitle": "Chicago, IL",
          "bullets": [
            "Built SQL quality checks for monthly EPA reporting extracts.",
            "Maintained Tableau dashboards used by program managers."
          ]
        }
      ]
    },
    {
      "heading": "EDUCATION",
      "items": [
        {
          "title": "University of Chicago",
          "meta": "May 2024",
          "subtitle": "Bachelor of Science in Statistics",
          "bullets": [
            "Coursework: Regression, Databases, Environmental Policy"
          ]
        }
      ]
    },
    {
      "heading": "SKILLS",
      "items": [
        "Advanced SQL, basic Python, Tableau, Excel, EPA reporting"
      ]
    }
  ]
}
```

## Invalid Schema Example

This is invalid because it omits required V2 root fields, uses the V1
`submission_id` field instead of `resume_id`, and makes `sections.items` an
object instead of an array:

```json
{
  "submission_id": "resume_999",
  "skills": "SQL, Python",
  "location": "Chicago, IL",
  "sections": [
    {
      "heading": "SKILLS",
      "items": {
        "text": "SQL, Python"
      }
    }
  ]
}
```
