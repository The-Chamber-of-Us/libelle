# V2 Corpus Validation and Structure Evaluation

This package is an experimental evaluator for the V2 benchmark golden JSON
contract. The source of truth for that contract is
`backend/benchmarks/v2_annotation_spec.md` from #320, especially the
representation of `sections[]`.

The package is intentionally separate from `scripts/benchmark.py` and does not
change production parsing, intake, resolver behavior, or V1 benchmark scoring.

## Validate Goldens

```bash
python -m backend.benchmarks.v2_evaluation.validate_v2_goldens \
  --pdf-dir backend/benchmarks/resumes \
  --golden-dir backend/benchmarks/golden_json \
  --summary-out /tmp/v2-validation.json
```

The validator walks directories recursively, so mixed root/V2 layouts are
supported. V1-shaped fixtures are skipped with an explicit message unless
`--include-v1` is provided. A fixture is treated as a V2 candidate when it has
either `resume_id` or `sections`; this catches malformed partial V2 fixtures
instead of silently skipping them.

Validation determines evaluation eligibility. Invalid V2 fixtures are reported
as invalid and are not scored.

## Score Current Parser Fields

```bash
python -m backend.benchmarks.v2_evaluation.score_v2_structure \
  --pdf-dir backend/benchmarks/resumes/v2 \
  --golden-dir backend/benchmarks/golden_json/v2 \
  --prediction-dir /path/to/current_parser_output_json \
  --summary-out /tmp/v2-structure-summary.json
```

Prediction JSON may be either current raw parser output, such as
`{"skills":{"value":[...]}, "locations":{"value":[...]}, "phones":{"value":[...]}}`,
or the existing benchmark adapter shape for comparable fields. If no prediction
exists, supported metrics are reported as `not evaluated` instead of receiving
artificial zeroes.

## Baseline Metrics

Normalization is deterministic: values are trimmed, lowercased, stripped of
ASCII punctuation, and whitespace-collapsed. Matching is exact after
normalization. Duplicates are collapsed for set-style fields.

Supported metrics:

- skills precision, recall, and F1
- location component matching for `country`, `city`, and `raw`
- phone exact matching after digit normalization

Unsupported comparisons are surfaced as `not evaluated`, including `sections[]`,
section headings, entry counts, structured `title`/`meta`/`subtitle`, bullet
text, bullet ordering, and semantic section equivalence.

## Parser Output Capability Audit

Current `backend/parser.py` output is available for evaluation of:
`phones`, `locations`, and `skills`.

Structurally present but not yet comparable:

- `education`, `work_experience`, and `project_experience` are coarse arrays of
  strings. They do not preserve section headings, entry field boundaries,
  subtitles, metadata fields, or bullets in the V2 schema.
- `backend/benchmarks/layout_spike/` contains exploratory PyMuPDF
  header-scoped extraction scripts. Those scripts can print grouped section
  text for inspection, but they do not emit the canonical V2 JSON shape and are
  not wired into parser, intake, or benchmark flows.

Unsupported today:

- Full `sections[]`
- source-faithful section headings
- structured item shape with required `title`, `meta`, `subtitle`, and
  `bullets`
- bullet-level text scoring
- ordering metrics

Not evaluated by this package:

- V1 skill/location benchmark scores
- resolver quality
- fuzzy, semantic, embedding, or LLM-as-judge scoring
