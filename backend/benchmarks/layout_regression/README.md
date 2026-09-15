# PDF skill-ownership regression corpus (#386)

Five synthetic, one-page layouts protect the conservative ownership contract
from #383 / #385: uncertain geometry must not grant unsupported skill ownership.
No private resume data, external service, LLM, or additional PDF dependency is
used. Production parsing, resolver behavior, and benchmark scoring are unchanged.

| Case | Condition protected | Expected parser behavior |
| --- | --- | --- |
| `fragmented_flow` | One visual flow split into blocks; varied x positions, right-aligned email and employment/project dates, bullets and hanging indents | Python and SQL only; no contact, dates, or narrative |
| `wide_skill_start` | Wide heading/content block crosses proposed lanes above narrower EXPERIENCE / PROJECTS; right side has sustained section evidence | Conservative first-section recovery; no work/date leakage or shared projection duplicates |
| `ambiguous_columns` | Two column-looking blocks without enough independent section/content evidence | Python only; later TOOLS / Docker is intentionally not recovered |
| `crossing_lane_start` | A narrow EDUCATION / TECHNICAL SKILLS block crosses the midpoint between column starts | Python and SQL belong only to the left lane; no right-lane narrative |
| `genuine_columns` | Independent sustained columns with interleaved headings and a later right-lane TOOLS section | Recover Python, SQL, Docker, Git, and AWS |

## Inputs and oracle

`cases.json` is the committed source of truth. Each block specifies a baseline
position in PDF points, text, and font size on a 640 × 820 page. Optional
`align: "right"` makes x the right edge. Newlines deliberately keep related
lines in one rendered block; separate insertions represent fragmented content.
The built-in Helvetica font and pinned PyMuPDF in `backend/requirements.txt`
make generation reproducible. File IDs and timestamps are omitted; tests compare
regenerated PDF bytes. Generated files live in ignored `out/` and need not be
committed.

Annotations distinguish actual document `skills` (canonical V1 benchmark gold)
from `expected_skills` (the existing parser contract). In the ambiguous case,
Docker is a legitimate annotated skill but conservative parsing omits it. The
standard benchmark therefore reports that false negative; gold is not weakened
to conceal it. `excluded` lists representative strings that must not appear in
emitted skills, including this deliberate omission. Exact ordered output checks
also reject any unexpected additions and duplicates.

Tests generate durable PDFs and run both `parse_resume_pdf` and the benchmark's
canonical `_run_libelle` path without mocks. They verify every source line survives
rendering, check final skills, and reuse #349's `validate_generated` entry point
(consistency plus canonical preflight). Secondary geometry checks ensure the
rendered fixtures still exercise ambiguity, genuine columns, and wide/narrow
boundary crossings. A projection-line uniqueness assertion catches shared-block
duplication that final parser deduplication could otherwise hide.

## Run from the repository root

```sh
python -m pytest backend/tests/test_layout_regression_corpus.py -q
python backend/benchmarks/layout_regression/generate.py
python backend/benchmarks/synthetic/generator/validate_generated.py \
  --pdf-dir backend/benchmarks/layout_regression/out/pdfs \
  --gold-dir backend/benchmarks/layout_regression/out/golden_json
python scripts/benchmark.py \
  --pdf_dir backend/benchmarks/layout_regression/out/pdfs \
  --golden_dir backend/benchmarks/layout_regression/out/golden_json \
  --parsers libelle
```

The focused tests are included in the existing `pytest tests -q` backend CI path.
Benchmark reporting and failure signals remain owned by #317; this corpus adds
inputs and assertions, not a new report format. These location-free fixtures
target skill ownership, so aggregate location metrics are not an acceptance gate.

## Research provenance and scope

The issue references `backend/benchmarks/experiments/skill_lane_provenance.py`.
That file is absent from this checkout and its available Git history, so it could
not be inspected. No experimental harness was copied. The maintained
`backend/tests/test_skill_section_projection.py` provided the available evidence:
real PyMuPDF generation, fragmented single-flow safety, wide mixed skill-start
blocks, narrow boundary crossings, and conservative first-section fallback.
Those techniques and failure classes are incorporated here with new text,
coordinates, and real extracted block extents. General provenance modeling and
experimental evaluation infrastructure remain outside this corpus.

If a future fixture reveals a new parser bug, preserve the PDF and observed
output as evidence for a separate parser issue; do not change production semantics
or weaken the ownership annotations merely to make this corpus pass.
