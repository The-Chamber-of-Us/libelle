# Synthetic Benchmark Spike (#191)

Time-boxed uncertainty-reduction experiment for issue
[#191](https://github.com/The-Chamber-of-Us/libelle/issues/191).

Generates a deterministic, template-based synthetic benchmark corpus and runs
it through `scripts/benchmark.py` to determine whether the cheap path
already produces useful parser/resolver signal — before committing to the
heavier MCP/agent architecture in epic #138.

## Layout

```
synthetic/
  generator/   profile + scenario generation, gold emitter
  templates/   Jinja2 resume templates (5 known categories + adversarial)
  catalogs/    skill and location catalogs
  out/         generated artifacts (gitignored)
    pdfs/
    golden_json/
    runs/
  findings/    SPIKE_191.md and follow-up notes
```

## Quickstart

All commands run from the **repo root**.

```bash
# Spike-local venv. Doesn't change backend/requirements.txt prod pin.
python3 -m venv .venv
.venv/bin/pip install -r backend/benchmarks/synthetic/requirements.txt

# macOS WeasyPrint system deps:
brew install pango cairo gdk-pixbuf libffi

# Generate 30 cases (20 known + 10 adversarial — one per adversarial template).
# DYLD_FALLBACK_LIBRARY_PATH lets cffi find Homebrew's pango/cairo on Apple Silicon.
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python backend/benchmarks/synthetic/generator/generate.py \
    --seed 42 --count 30 --adversarial-ratio 0.34

# Internal consistency check (verifies gold's location.raw appears in extracted PDF text).
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python backend/benchmarks/synthetic/generator/consistency_check.py
# -> 30/30 cases passed consistency check

# Run the benchmark harness against the generated corpus.
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python scripts/benchmark.py \
    --pdf_dir backend/benchmarks/synthetic/out/pdfs \
    --golden_dir backend/benchmarks/synthetic/out/golden_json \
    --out backend/benchmarks/synthetic/out/runs
```

Note: `--adversarial-ratio 0.34` (not the 0.30 default) ensures all 10
adversarial templates fire at `--count 30`. With 0.30, only 9 fire — the
last adversarial template is missed.

## Annotation versioning (#347)

Annotation derivation is versioned independently of profile generation and
rendering. The synthetic `Profile` (`generator/schema.py`) remains the single
source of truth; `--annotation-version` selects which schema `gold.json` is
written in:

```bash
# Default: labeling_rules_v1.md shape ({"submission_id", "skills", "location", "notes"})
.venv/bin/python backend/benchmarks/synthetic/generator/generate.py --seed 42 --count 30

# Canonical V2 shape (backend/benchmarks/v2_annotation_spec.md)
.venv/bin/python backend/benchmarks/synthetic/generator/generate.py \
  --seed 42 --count 30 --annotation-version v2
```

`derive_gold_v2()` maps `Profile.experience`/`Profile.education` into V2
`sections[]` (structured `title`/`meta`/`subtitle`/`bullets` entries) and
`Profile.skills`/`Profile.tools` into a plain-string `SKILLS` section, in
that fixed order. This is a derivation-order convenience, not a literal
rendered layout — the Profile IR doesn't carry template section ordering.
`links` is always `[]`; `Profile` has no link field to derive from yet.

## Determinism

Same `--seed` reproduces the same generated text content and gold targets.
Byte-identical PDFs across machines are **not** guaranteed (font fallbacks
drift). The reproducibility contract is: stable extracted text +
content fingerprint, per #191 FR-4.

## Anti-footgun reminders (from #191)

- Do not modify `backend/parser.py`, resolver, alias map, or
  `scripts/benchmark.py` inside this spike.
- Bugs found here become separate follow-up issues.
- Synthetic-only data: no real PII, no copied real-world resumes.
