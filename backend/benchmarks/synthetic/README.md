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

```bash
# from repo root
pip install -r backend/benchmarks/synthetic/requirements.txt
# macOS WeasyPrint system deps:
brew install pango cairo gdk-pixbuf libffi

# Generate corpus + run benchmark
python backend/benchmarks/synthetic/generator/generate.py --seed 42 --count 30
python scripts/benchmark.py \
  --pdf_dir backend/benchmarks/synthetic/out/pdfs \
  --golden_dir backend/benchmarks/synthetic/out/golden_json \
  --out backend/benchmarks/synthetic/out/runs
```

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
