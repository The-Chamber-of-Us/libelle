# Current structural parsing diagnosis — #301

The current heuristics warrant focused follow-up: **6 of 10 deliberately
selected examples show section ownership, boundary, header, or entry-grouping
problems**. Three affect scored skills; three are unscored V2 work/project
observations. This is a diagnostic sample, not an estimated corpus failure rate.
No parser behavior or structured experience model is changed.

## Evidence and method

Baseline: `e04ab03213ca7a18eb3a5e867c42314c9119a7d4`, September 30, 2026,
Python 3.11.8. Two fresh Libelle-only runs completed without parser errors:

| Corpus | Fixtures | skills micro-F1 | skills_resolved micro-F1 | location micro-F1 |
| --- | ---: | ---: | ---: | ---: |
| Root benchmark directory (10 V1-shaped, 10 V2-shaped) | 20 | 0.655 | 0.670 | 0.733 |
| `resumes/v2` and matching goldens | 10 | 0.644 | 0.644 | 0.824 |

The reproduction commands below generate `report.csv`, `summary.md`,
`summary.json`, `examples.md`, and `run_log.json` for each benchmark run.
These reports and the per-fixture diagnostic traces are generated outputs, not
checked-in files; the compact results and representative observations are retained
here.
The runner does not recurse into `v2`, hence separate runs. These scores are
baselines, not improvements or a controlled comparison between corpora.

Cases were selected from scored errors plus V2 goldens with projects before
work, nonstandard headings, and multiple work entries. Each generated trace records
the source PDF/golden paths and hashes, extracted section lines, heading decisions,
projected skill text, and current parser output. Only repository benchmark
fixtures were used; no private resumes or external services were accessed. Initial
identity/contact blocks are omitted from traces. The two dense-skills PDFs were
also rendered and visually reviewed: both visibly have separate skill/work columns.
Other observations were checked against extracted source text and golden JSON.

The local September 8 run (`4de3b24`, five generated layout-regression PDFs)
was inspected for context only. Its different corpus and revision cannot establish
improvement or regression here. The historical #265 `multi_col_02` description
is treated as a hypothesis to recheck, not a current result.

## Scored field evidence

Counts below are **TP / FP / FN for raw skills**, except the location row.
Labels identify the demonstrated cause, not every possible contributor.

| Fixture | Counts | Label | Source → current output and diagnosis |
| --- | --- | --- | --- |
| `dense_skills_01` | 37 / 46 / 12 | section overlap or bleed | The visible two-column PDF is classified `SINGLE_COLUMN`. Projected skills interleave `Key Skills` content with `JUL 2018 – FEB 2021`, employer text and work descriptions. Output includes `clayburn apps` and `account creation by 35%.`. Ownership is lost before skill tokenization; wrapped phrases also cause misses. |
| `dense_skills_02` | 0 / 0 / 22 | section ended too early | `AMBIGUOUS` layout falls back to flattened order: `SKILLS`, blank, `WORK EXPERIENCE`, then interleaved content. The legitimate adjacent-column work header stops skill capture before `Content Strategy`. Projection contains only `SKILLS`; no skills reach the resolver. This is not a missed skills header or a false header. |
| `resume_204` | 4 / 22 / 3 | missed section header; skills section bleed | After the real skill list, `METHODS TRAINING` and `PROFESSIONAL SERVICE` are neither general nor skill-stop headers. Both sections enter projection and output, including `graduate methods sequence` and `2025-2026`. Golden `sections[]` separates them. The three skill misses also involve qualifiers/combined languages, so not every error in this row is structural. |
| `multi_col_02` | 6 / 11 / 6 | final field-output error unrelated to section boundaries | Current `MULTI_COLUMN` projection contains skill-column text, not the historical employer/date bleed. `Environmental Testing` + `Procedures` and `Compound and Stereo` + `Microscopy` become separate skills. The source phrases span lines; `extract_skills()` tokenizes each line independently. The general `_group_into_entries()` helper is not involved in skills. |
| `header_contact_01` | 14 / 16 / 16 | final field-output error; canonicalization/scoring effect | Projection retains the correct skill column, but `Confidentiality & FERPA` / `Compliance` split apart. Parentheses spanning lines survive as fragments (`calendar)`). Resolved scoring changes counts to 17 / 13 / 13 even though resolver coverage is zero: punctuation normalization can match fragments without recovering phrases or resolving aliases. |
| `embed_link_01` | 7 / 0 / 3 | final field-output error unrelated to structure; golden mismatch | The complete projected line `Data visualization (Matplotlib, Tableau, PowerBI)` reaches `extract_skills()`, which removes parenthesized content. The three misses are `matplotlib`, `powerbi`, and golden spelling `tableu`. No section was missed; fixing boundaries alone cannot recover these, and `Tableau` versus `tableu` is a separate annotation/normalization concern. |
| `non_usa_01` | location: 0 / 0 / 1 | final field-output error unrelated to structure | Source contact line says `LVIV, UKRAINE`; output location is empty. `extract_location()` checks early lines for US state codes or remote/hybrid, independently of sections. Skills score 6 / 0 / 0. |

The first three rows demonstrate structural involvement in scored skill errors.
The next four prevent over-attributing tokenization, normalization, golden spelling,
and geographic coverage problems to header detection.

## Supporting V2 observations — no structural scores

| Fixture | Label | Golden/source → current output |
| --- | --- | --- |
| `resume_201` | work/project boundary observation | Golden `PROJECTS` precedes `EXPERIENCE`. Production starts project search at the work-end `SKILLS` line, returning `[]`. Calling the existing project extractor from index zero yields eight coarse strings, proving recognizable project content was excluded by the start index. Those eight strings are not eight correctly extracted projects; the golden has two items under `PROJECTS`. |
| `resume_202` | entry grouping problem | Golden `EXPERIENCE` has three jobs. Current output contains 15 strings: titles/dates, standalone cities, and individual bullets. Extracted blank lines and bullet prefixes trigger `_group_into_entries()` flushes; `Austin, TX` and `Reduced incident response time by 38%...` become separate entries. This establishes fragmentation without defining a replacement model. |
| `resume_203` | missed section header; work/project boundary observation | Golden `TECHNICAL PROJECTS` has two items before `EXPERIENCE`. Production returns no projects. The heading is not recognized by `_is_section_header()` or the project's start patterns; even searching from index zero returns `[]`. Both heading vocabulary and search ordering are relevant, unlike the ordering-only demonstration in resume_201. |

These are observations about coarse string output, not formal work/project recall
or accuracy. The scored skill mismatches in these fixtures are separate: for
example, resume_201 emits `basic spanish` against golden `Spanish` while correctly
stopping skills at `ADDITIONAL PROJECTS`.

## Interpretation and instrumentation gaps

Of seven scored examples, three demonstrate section-level involvement. All three
supporting V2 examples demonstrate structural problems: **6/10 overall**. Among
the six, two show layout/ownership-dependent collection errors, one shows missed
stop headings, one shows entry fragmentation, one shows project ordering loss,
and one combines missed project heading and ordering. Labels overlap. Wrapped
skill phrases in two other cases are line/token interpretation errors, excluded
from this strict section/grouping count. This review does not establish recurring
false headers or garbled-header normalization failures; no positive example of
either was verified.

The current path is PDF extraction → `project_skill_sections()` →
`_parse_resume_with_skill_text()`. Skills use projected text; work/projects use
flattened text. `_collect_section_lines()` and `_is_section_header()` still matter,
but projection has its own collection pass and broader skill-local heading rules.
Consequently, attributing all skill errors directly to the general collector would
be misleading. See [parser.py](../../parser.py),
[PDF parser](../../services/resume_pdf_parser.py), and
[skill projection](../../services/skill_section_projection.py).

The main benchmark scores only skills, skills_resolved, and location. Its adapter
drops work/project/education output; failure examples are truncated samples and
do not explain boundary decisions. The generated traces supply observation data,
not new scoring. `skills_resolved` normalizes both predicted and golden sets with
alias lookup and fallback keys; it is not the count of skills successfully
resolved by Resolver V1. The 14-alias map and low coverage must not be interpreted
as structural recall. Location scoring accepts matching country even when city
differs, so a location TP does not certify correct city extraction.

The separate [V2 evaluator](../v2_evaluation/README.md) now supports skill,
location-component, and phone comparisons, but still marks headings, sections,
entry counts, bullet text/order, and structured items as **not evaluated**.
It was not used to assign structural metrics here. Future diagnosis would benefit
from recording projection ownership and start/stop decisions alongside scored
rows, and separately evaluating section boundaries/grouping. No name, email,
education, work/project, or confidence-calibration improvement is claimed.

Follow-up is justified for layout-dependent ownership, heading coverage,
work-end-dependent project search, and fragmentation at blank lines/bullets.
Token reconstruction and annotation/canonicalization deserve separate tracking.
This spike neither prototypes the #303 experience model nor selects a replacement
architecture.

## Reproduce

From the repository root, using the existing backend environment. To reproduce
these historical results, use the baseline commit listed above for the parser,
benchmark runner, fixtures, and goldens, with this diagnostic script available.
Running against later revisions may produce different results:

```bash
backend/.venv/bin/python scripts/benchmark.py --out /tmp/issue301-root
backend/.venv/bin/python scripts/benchmark.py --pdf_dir backend/benchmarks/resumes/v2 --golden_dir backend/benchmarks/golden_json/v2 --out /tmp/issue301-v2
backend/.venv/bin/python backend/benchmarks/structural_spike/inspect_current.py --out /tmp/issue301-traces
```

The benchmark commands create timestamped run directories under
`/tmp/issue301-root/` and `/tmp/issue301-v2/`, each containing the five report
files listed above. The diagnostic command writes ten `<fixture_id>.json` files
directly under `/tmp/issue301-traces/`; the fixture IDs in the tables identify the
corresponding traces. Source PDFs and goldens are in `backend/benchmarks/resumes/`
and `backend/benchmarks/golden_json/`, with `resume_201`–`resume_204` in their
respective `v2/` subdirectories.

The trace probe calls current parser helpers and the canonical PDF parser; it
does not reproduce their logic. Source hashes allow checking fixture drift.
Run logs preserve original commands/environment; timings and timestamps vary.
