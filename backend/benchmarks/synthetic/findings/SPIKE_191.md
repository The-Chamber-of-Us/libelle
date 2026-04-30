# Spike #191 — Findings

**Question.** Does a cheap, deterministic, template-based synthetic generator produce
cases that surface meaningful parser/resolver/alias-map signal — before we
commit to the heavier MCP/agent architecture in #138?

**Short answer.** Yes, decisively. 30 generated cases (seed=42) surfaced one
previously-undocumented parser bug, six confirmed-but-now-reproducible failure
modes, and a structural gap in `scripts/benchmark.py` that masks alias coverage.

---

## Reproduction

```bash
# Setup (spike-local, doesn't touch backend/requirements.txt prod pin)
python3 -m venv .venv
.venv/bin/pip install -r backend/benchmarks/synthetic/requirements.txt
brew install pango cairo gdk-pixbuf libffi   # macOS WeasyPrint deps

# Generate 30 cases (20 known, 10 adversarial — one per adversarial template)
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python backend/benchmarks/synthetic/generator/generate.py \
    --seed 42 --count 30 --adversarial-ratio 0.34

# Internal-consistency check (re-extract PDF text, verify gold matches rendered)
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python backend/benchmarks/synthetic/generator/consistency_check.py
# -> 30/30 cases passed consistency check

# Benchmark
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python scripts/benchmark.py \
    --pdf_dir backend/benchmarks/synthetic/out/pdfs \
    --golden_dir backend/benchmarks/synthetic/out/golden_json \
    --out backend/benchmarks/synthetic/out/runs
```

Same `--seed` reproduces identical content, gold targets, and benchmark scores.
PDFs are not byte-identical across machines (font fallback drift); the
reproducibility contract is *stable extracted text*, per #191 FR-4.

---

## Artifact structure

```
backend/benchmarks/synthetic/
├── generator/      schema.py, generate.py, consistency_check.py
├── templates/      14 Jinja2 templates: 5 known + 9 adversarial + base CSS
├── catalogs/       skills.json (~85 skills), locations.json (US + non-US + remote + fictional)
├── out/            (gitignored)
│   ├── pdfs/                {case_id}.pdf
│   ├── golden_json/         {case_id}.json   (benchmark-compatible)
│   ├── manifest.json        per-case category, probes, alias_stress_skills
│   └── runs/{ts}/           summary.md, summary.json, report.csv, examples.md
└── findings/       this note
```

## Synthetic-only / no-PII

All identities are sampled from a 15-name fictional roster (`SYNTHETIC_NAMES` in
`generate.py`); emails follow `name@example.test` (RFC-2606 reserved); phones use
`555-` prefix; companies/institutions are made up. No real-world resumes were
copied. Skills come from a hand-curated catalog grounded in `aliases_v1.json`
plus domain terms already present in the existing `backend/benchmarks/` corpus.

---

## Headline numbers

| Field    | Micro-P | Micro-R | Micro-F1 | Macro-F1 | TP  | FP | FN |
|----------|---------|---------|----------|----------|-----|----|----|
| skills   | 0.719   | 0.637   | 0.675    | 0.608    | 156 | 61 | 89 |
| location | 1.000   | 0.133   | 0.235    | 0.133    | 4   | 0  | 26 |

Read the location row carefully: precision is 1.000 *only because* the parser
recovers location in just 4 of 30 cases — and as the next finding shows, those
4 are recovered for the wrong reason.

---

## Findings

### Finding 1 — NEW parser bug (not in `parser-guide.md`)

**Contact-line filter is too coarse: lines containing email or phone are
dropped entirely, taking the location with them.**

`backend/parser.py:97` filters `candidate_lines` for `extract_location` by
running an email/phone/URL regex against the *whole line*. When contact info
is rendered as a single line (`email | phone | location`), the line matches
the email regex and is excluded — so the parser never sees the location.

Reproducible on every known-template case (`syn_000`, `syn_005`, `syn_010`,
`syn_015`, `syn_020`, …). All 20 known cases were rendered with parser-friendly
"City, ST" location strings, yet only 4 score location correctly.

**Why those 4 still pass.** They pass *coincidentally*: the parser falls
through to a later line and picks up the **first experience entry's location
header** (e.g. `San Francisco, CA | 2022 – Present`), which happens to match
the contact city. Verified on `syn_004_embed_link` and `syn_022_adv_paren_groups`
— in both, the contact line was filtered, but an experience line in the
first-15 window matched and shared the city.

**Implication for existing corpus.** The 10 hand-built cases in
`backend/benchmarks/{resumes,golden_json}/` very likely score location
correctly only by the same coincidence. Any case where the experience
location differs from the contact location should fail. This is a
significant false-confidence risk in the current benchmark.

Will open as follow-up issue.

### Finding 2 — Six confirmed-but-now-reproducible parser failure modes

Each had a dedicated adversarial template; all failed exactly as predicted
from reading `parser.py`. Listing case_id so the failure is reproducible from
seed 42 alone.

| #  | Case                            | Boundary                                                        | Result            |
|----|---------------------------------|-----------------------------------------------------------------|-------------------|
| 2a | `syn_020_adv_tools_header`      | Plain `Tools` header (parser only matches `Tools & Technologies`) | skills FN=7, F1=0 |
| 2b | `syn_021_adv_tech_stack`        | `Tech Stack` header (not in pattern list)                        | skills FN=6, F1=0 |
| 2c | `syn_027_adv_allcaps_header`    | `Technical Toolkit` header (all-caps, non-standard wording)      | skills FN=5, F1=0 |
| 2d | `syn_029_adv_unconventional_delim` | Skills separated by ` / ` (not in `[•,·;\|]` split set)      | skills FN=9, FP=1 |
| 2e | `syn_022_adv_paren_groups`      | `Group (a, b, c)` not split — contradicts `labeling_rules_v1.md` | skills FN=9, FP=7 |
| 2f | `syn_023_adv_spelled_state`     | Spelled-out US state (`Austin, Texas` not in 2-letter abbrev set) | location FN=1     |

Plus three non-USA / location-formatting failures (`syn_003/8/13/18` non_usa,
`syn_024_adv_remote_with_city`, `syn_025_adv_location_late`) covering the
documented `parser-guide.md` known-limitations on non-English / region-biased
location handling — now with reproducible inputs.

### Finding 3 — Negative control passes

`syn_028_adv_no_explicit_skills` has zero explicit Skills section; experience
bullets reference plenty of skills. Gold is empty, parser returns empty,
score is 0/0/0. Confirms the parser does **not** infer skills from experience
text — consistent with `labeling_rules_v1.md`. Useful as a regression guard.

### Finding 4 — Benchmark scorer ignores the alias map

The cleanest signal here. Several alias variants ARE in `aliases_v1.json` —
`reactjs → react`, `python3 → python`, `c# / chash`, `next.js`, `.net` — but
`scripts/benchmark.py:_normalize` only `lower().strip()`s. It never canonicalizes
through the alias map. Examples from `examples.md`:

- gold `react`, parser `react.js` → counted as FP+FN despite alias being known
- gold `python`, parser `python3` → counted as FP+FN despite alias being known
- gold `c#`, parser `csharp` → counted as FP+FN despite alias being known
- gold `next.js`, parser `nextjs` → counted as FP+FN despite alias being known

**This is the single highest-leverage parser/resolver-coverage finding.** The
benchmark cannot measure alias-map effectiveness today. Every alias improvement
will look like a wash on benchmark scores until the scorer wires through the
resolver. This is consistent with #191's note that the harness is currently a
parser benchmark, not a resolver benchmark.

Will open as follow-up issue.

### Finding 5 — Alias-map gaps surfaced

Variants present in our corpus (and common on real resumes) that are **not**
in `aliases_v1.json`:

- `JS ↔ JavaScript` (no entry)
- `TS ↔ TypeScript` (no entry)
- `Postgres ↔ PostgreSQL` (no entry)
- `Mongo ↔ MongoDB` (no entry)
- `K8s ↔ Kubernetes` (no entry)
- `Golang ↔ Go` (no entry)
- `sklearn ↔ scikit-learn` (no entry)
- `Apache Spark / Apache Kafka / Apache Airflow ↔ Spark / Kafka / Airflow` (no entry)
- `BigQuery ↔ Google BigQuery` (no entry)
- `Azure ↔ Microsoft Azure` (no entry)
- `Vue.js ↔ Vue ↔ VueJS` (no entry)
- `Node.js ↔ Node ↔ NodeJS` (no entry)
- `Power BI ↔ PowerBI` (no entry — note variant differs only by spacing)
- `Adobe XD ↔ XD` (no entry)
- `UX Research ↔ User Research` (no entry)

The map currently has ~10 entries (react, python, c++, c#, .net, next.js, nodejs).
Adding the above would not fix the benchmark scoring (Finding 4 blocks that),
but would meaningfully increase resolver coverage in the live path that
`sheets_repo.py` already records (`resolved_skill_ids`, `unknown_skills`).

### Finding 6 — Skills micro-F1 0.675 has a *known* ceiling on this corpus

Even with all parser bugs fixed, this corpus would not approach 1.000 skills F1
because of Finding 4. About 30 of the 61 FPs and 30 of the 89 FNs are alias
mismatches the scorer can't currently resolve. Real ceiling on this corpus,
with current scorer, is approximately 0.80 F1 — assuming all parser bugs
above are fixed.

---

## Conclusion (per #191's required framework)

> 4. **Deterministic generation exposes enough value that the larger
> synthetic benchmark architecture should be rescoped and resumed.**

This is not a "deterministic alone is enough forever" conclusion. It's a
"deterministic was enough to **earn** the next iteration" conclusion. The
spike paid for itself in less than a day:

- **One** previously-undocumented parser bug (Finding 1).
- **Six** reproducible parser failure modes with stable case IDs (Finding 2).
- **One** structural benchmark gap that explains a class of "mysterious" skill
  scoring (Finding 4).
- **~15** concrete alias-map additions (Finding 5).
- **One** negative-control regression guard (Finding 3).

### What I'd do next, in order

1. **Open follow-up issues** for Findings 1, 2 (one per failure mode), 4, 5
   (single bundled), and a regression-guard issue using `syn_028` as a
   permanent fixture.
2. **Land the spike's generator + corpus as a developer tool.** Don't promote
   the synthetic cases into the maintained `backend/benchmarks/{resumes,golden_json}/`
   corpus yet — that requires the human-review staging gate from #145.
3. **Before scoping #138's full agent pipeline:** fix Finding 4 (wire the
   alias map through `_normalize`). Without it, no parser/resolver work
   can be measured properly. Everything else in #138 is downstream of that.
4. **After Finding 4 lands:** consider a bounded LLM variation phase as a
   *comparison layer* against the deterministic baseline — only if it
   demonstrably surfaces failures the deterministic generator missed. Don't
   fund the full agent pipeline on speculative future value.
5. **Out of scope here, but worth flagging:** the existing 10 cases in
   `backend/benchmarks/` should be re-examined under the lens of Finding 1.
   If their location passes are coincidental, the existing corpus is giving
   a false-confident location score today.
