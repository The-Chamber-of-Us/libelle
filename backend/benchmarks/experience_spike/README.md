# Structured experience prototype (#303)

V2 `sections[]` can supply structured expected entries, and current parser strings
can supply comparable raw-text predictions. Continue toward formal evaluation,
but establish a heading taxonomy and preserve entry/field ownership first. The
current parser often retains work text while splitting an annotated entry into
several strings; token survival alone does not establish structured extraction.
No production parser or existing benchmark scoring was changed.

## Reproduce and evidence boundary

From the repository root:

```sh
backend/.venv/bin/python scripts/benchmark_experience.py --out /tmp/issue303-experience
backend/.venv/bin/python -m pytest backend/tests/test_experience_eval.py backend/tests/test_benchmark_parser_path.py backend/benchmarks/v2_evaluation/tests/test_v2_evaluation.py -q
```

The default sample is all ten public synthetic V2 PDF/golden pairs,
`resume_201`–`resume_210`, under `resumes/v2` and `golden_json/v2`. This is a
synthetic sample, not a real-resume population estimate. The runner requires
valid, nonempty V2 PDF/golden pairing via the existing V2 validator and uses
`extract_text_from_pdf_path(pdf) → parse_resume(text)`. That is the requested
flattened-text path. The existing canonical PDF benchmark uses
`parse_resume_pdf`, including skill projection; experience currently consumes
flattened text in both paths. This spike does not evaluate Resolver output.

Generated `experience_report.csv` contains counts and diagnostic labels.
`experience_summary.json` records the source revision, results, aggregate
accounting, and every unmapped heading with its item count.
`experience_traces.json` retains
PDF/golden SHA-256 hashes, extracted source text, actual parser output,
expected/predicted entries, field coverage, excluded headings, and the separate
start-at-zero project probe. Artifacts are generated on demand in the explicit
output directory and are not source-controlled evidence. The source revision
identifies the checkout used for that run, so it changes at subsequent PR heads.
`--out` is required; running without it cannot recreate artifacts beside this
report.

The existing `scripts/benchmark.py` formally scores skills, skills_resolved, and
location. The V2 evaluator also evaluates supported top-level fields and
explicitly leaves experience structure unsupported. These spike outputs are
exploratory diagnostics, with no formal experience precision, recall, or F1.

## Shape and adapters

[experience_eval.py](../experience_eval.py) defines `ExperienceEntryV1`:

```text
entry_type: work | project | unknown
title, meta, subtitle: string | null
bullets: list[string]
raw_text: string
source_section: string | null
```

`extract_expected_experience_entries` maps each item of each recognized V2
section separately, preserving ordering and repeated sections. Dict items retain
title/meta/subtitle/bullets; raw text joins those fields with newlines. String
items remain raw text with null fields and empty bullets. Missing `sections[]`
raises an error rather than masquerading as zero annotated entries. The helper
reuses canonical V2 section validation, including required structured fields
and nonempty titles, and additionally rejects blank item text. The runner
validates the full paired corpus before PDF parsing, including missing pairs,
malformed JSON, non-V2 fixtures, filename/ID mismatches, and malformed fields.
Validation failures abort the run before reports are written.

Heading normalization collapses whitespace, lowercases, expands `&` to `and`,
and removes trailing colons. Work headings are experience, work experience,
professional experience, employment, employment history, relevant experience,
job experience, career history, work history, research experience, engineering
experience, and professional background. The added research heading follows
the role/lab/responsibility guidance in [labeling_rules_v2.md](../labeling_rules_v2.md);
the canonical [V2 annotation spec](../v2_annotation_spec.md) also supports
structured professional-background, research, and portfolio entries. Project
headings are projects, project experience, technical projects, selected projects,
additional projects, portfolio projects, project highlights, more projects,
machine learning projects, and analytics projects at work. These explicit
categories include the named project sections present in this slice.

Unmapped headings are excluded from type-specific counts and separately
accounted for by heading and item count in the summary and traces. This inventory
includes unrelated sections such as education; it does not label every unmapped
item as eligible experience. `unknown` is reserved in the schema. Mixed headings
such as `SELECTED REPORTING WORK` and `Additional Campus Work` remain visible
for taxonomy review rather than disappearing from the evidence.

`extract_predicted_experience_entries` unwraps parser `{value, confidence}`
fields or accepts direct lists. Each parser string becomes one entry under its
output field's type, with raw text preserved. Title/meta/subtitle/source_section
are null and bullets empty: the parser has lost these boundaries. Empty bullets
here mean unavailable structure, not proof of no bullet content. Unsupported
field/item shapes and blank entries raise errors. Both prediction fields must
exist; missing fields or wrappers without `value` are instrumentation errors.
Explicit empty lists remain valid zero-output predictions. No titles, employers,
dates, or bullet ownership are inferred.

## Comparison method

Raw text uses Unicode NFKC, case folding, Unicode word-token extraction, and
unique-token sets. For every expected entry, the best same-type prediction has
Jaccard overlap `|expected ∩ predicted| / |expected ∪ predicted|`; CSV overlap
is the mean of these per-entry maxima. Empty-vs-empty overlap is zero; a type
with no expected entries has null aggregate overlap. Predictions can be reused
across expected entries. This is not one-to-one matching and gives no PRF.

Traces also record expected-token coverage against the union of all same-type
prediction strings, including title/meta/subtitle and each bullet. This exposes
text survival across fragments, without asserting correct field extraction,
entry association, token order, or date semantics. Missing annotated field text
has null coverage. Repeated words and common tokens can inflate overlap.

Count differences suggest possible splits/merges/misses; counts do not prove
their causes. Low overlap uses an exploratory 0.25 threshold. Possible type
confusion requires opposite-type best overlap ≥0.25 and >0.15 above same-type
best. Additional-project coverage below 0.5 is flagged. Possible bleed checks
unmapped section items with at least eight whitespace words and ≥0.6 token
coverage in combined predictions. These are inspection cues, not calibrated
classifiers. No type-confusion cue fired in this run.

## Results

Counts below use the explicit heading map; zero mapped entries does not mean a
resume has no work or projects under other headings. Overlap is rounded.

| Resume | Work expected/predicted | Project expected/predicted | Work overlap | Project overlap | Projects from index 0 |
|---|---:|---:|---:|---:|---:|
| 201 | 1/4 | 4/0 | .3590 | .0000 | 8 |
| 202 | 3/15 | 0/0 | .3319 | — | 0 |
| 203 | 2/9 | 2/0 | .3360 | .0000 | 0 |
| 204 | 2/0 | 0/0 | .0000 | — | 0 |
| 205 | 1/4 | 3/0 | .4412 | .0000 | 14 |
| 206 | 2/0 | 2/0 | .0000 | .0000 | 0 |
| 207 | 2/8 | 2/0 | .4125 | .0000 | 0 |
| 208 | 2/0 | 0/0 | .0000 | — | 0 |
| 209 | 2/7 | 2/20 | .3812 | .4384 | 20 |
| 210 | 2/8 | 4/0 | .4517 | .0000 | 0 |

There are **19 mapped work entries across all ten fixtures**, versus 55 parser
strings. Seven of ten fixtures have excess work output counts; the other three
(204, 206, 208) miss their work sections entirely. The previous narrow map counted
13 work entries across seven fixtures and excluded those three misses; its 7/7
fragmentation observation was not a corpus-level result.

There are **19 mapped project entries across seven fixtures**, versus 20 parser
strings. Six of seven project-bearing fixtures (201, 203, 205, 206, 207, 210)
have no project predictions. Fixture 209 produces excess output and section
bleed. Remaining mixed/unmapped sections are separately inventoried rather than
treated as valid negatives. These totals mix fragments and complete annotated
entries and must not be interpreted as true/false positives.

Representative evidence checked against goldens, extracted PDF text, and parser
output in the traces:

- **201: ordering and additional projects.** The golden has two `PROJECTS`
  items before `EXPERIENCE`, then two `ADDITIONAL PROJECTS` items after skills.
  Actual project output is empty. `work_end=44` starts searching after the
  earlier projects; starting at zero yields eight fragments from the first
  project section. It still does not recover additional projects. The work
  entry becomes four strings (title/date, location, two bullets), yet its
  combined raw-token coverage is 1.0.
- **202: retained text, lost grouping.** Three professional-experience entries
  become 15 strings. Each expected entry has combined work-token coverage 1.0,
  while best-entry overlap is only .303, .298, and .395. Titles, metadata, and
  bullet text survive somewhere, but no structured ownership survives.
- **203: heading miss.** Two `TECHNICAL PROJECTS` entries produce no project
  output even at index zero. The prototype recognizes this heading; the parser
  project patterns recognize only `PROJECTS` and `PROJECT EXPERIENCE`.
- **205: `work_end` sensitivity.** Three expected projects produce zero actual
  strings; index zero produces 14 strings. The probe establishes sensitivity,
  not successful structured recovery or a proposed production fix.
- **204/206/208: complete work-section misses.** Two research roles, two
  engineering roles, and two professional-background roles are annotated in
  the respective goldens and present in source text, but produce no work output.
- **209: verified section bleed.** Two mapped entries, Budget Splitter under
  `PROJECTS` and Subway Delay Notes under `More Projects`, correspond to 20
  project strings. Source text shows `SKILLS & INTERESTS`,
  `ADDITIONAL CAMPUS WORK`, `MORE PROJECTS`, and `COURSEWORK` after that entry;
  the project output includes their content. These headings are not recognized
  as general parser stop boundaries. `More Projects` is now an expected project
  section rather than an unrelated-section bleed label. The cue correctly prompts
  inspection here, but its union coverage alone would not prove bleed.

## Gaps and next steps

The map now includes unambiguous work/project headings in this slice. Mixed
sections such as `SELECTED REPORTING WORK` (208, two items), `Additional Campus
Work` (209, two items), leadership, selected impact, and design research still
require explicit type policy. Their headings and item counts remain in the
unmapped inventory. No conclusion claims complete semantic classification of
all V2 items.

Focused regressions protect the corrected aggregate accounting, newly included
work misses, 202's full text coverage with fragmentation, 203's unsupported
heading, 205's separate index-zero diagnostic, and 209's bleed and additional
project accounting. Invalid input tests distinguish instrumentation failures
from valid empty parser output, and the CLI requires an explicit output directory.
Targeted validation: **50 tests passed**.

Next, agree on section-type labels (including mixed/research/volunteer cases)
and fixture eligibility; preserve source section and entry/bullet boundaries in
an experimental parser path; then define deterministic one-to-one matching,
unmatched-entry handling, field-specific measures, and ambiguity policy with
reviewed examples. This prototype demonstrates feasible adapters and actionable
diagnostics. It does not demonstrate reliable structured extraction, employer
normalization, timeline reconstruction, candidate matching, or parser improvement.
