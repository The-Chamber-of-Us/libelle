# BettyAnn's synthetic generator artifacts — issue #238

Reviewed 2026-10-09. Recommendation: **split into smaller follow-up issues**.
Keep the generator experimental; prepare an artifacts-only import after human
review and a small, backward-compatible filename-support change. This review
provides the PR plan required by [#238](https://github.com/The-Chamber-of-Us/libelle/issues/238).
It does not admit cases to the maintained corpus.

## Evidence boundary

- Artifact source: cached `origin/dev/138-synth-benchmark-data`, commit
  `0543fbf87d2c5fc86b8fbce0090689a9a97aa3b0` (BettyAnn, 2026-05-10).
- Current harness/parser: `c139ed1fe18587c726a60d24da78f85fffdeb4e0`.
- Live `git ls-remote origin 'refs/heads/*synth*'` did not advertise the source
  branch. The public issue-comments API returned an empty list. This is a
  review of the identified cached commit, not a claim about an unseen later
  revision. Preserve that source revision before relying on remote availability.
- Reviewed generator, MLX helper, dependency snapshot, `scripts/DELIVERABLE.md`,
  branch benchmark changes, all 30 source/gold/PDF triples, and report files.
- Extracted text and checked IDs, skill values, source/gold agreement, page
  counts, roles, locales, and contacts across all cases. Visually inspected
  `000__resume__librarian`, `004__resume__structural_engineer`, and
  `026__resume__plumber`; this is a visual sample, not full corpus admission.
- Generation was not rerun: no model download, MLX/RenderCV installation, or
  geocoding requests were needed to benchmark the existing PDFs.

## Artifact findings

| Check | Observed result | Integration implication |
| --- | --- | --- |
| Completeness | 30 PDFs, 30 `.synth.json`, 30 `.gold.json`; matching IDs | Preserve each triple together, with source revision and hashes. |
| Naming | `{index:03d}__resume__{role}`; gold `submission_id` matches PDF stem | IDs are stable for this snapshot, but index-based names collide between generation runs. Namespace imported cases and record the original ID. |
| Skills | 248 gold entries; no blank/non-string values; every source `tool` list equals gold `skills` | Existing artifacts are clean on this check. Writer still needs its own normalization/validation boundary. |
| PDF text | 246/248 skills match literal case-insensitive PDF text; two differ only by straight/curly apostrophe in `Geochemist's Workbench` (`012`, `015`) | These are typography differences, not missing rendered skills. Keep scorer normalization changes in a separate issue. |
| Diversity | 12 roles, 12 locales; 28/30 cases outside the US; 29 one-page PDFs and one two-page PDF (`027__resume__plumber`) | Useful international and domain slices; not a representative production distribution. |
| Layout | Grouped skill labels in the first three cases; several themes, bullets, icons, aligned dates, repeated footers | Useful extraction stress. Do not infer the exact selected theme from screenshots. |
| Realism | Readable professional layouts, but names such as “Probably Bus and Sons,” repeated dates/achievement phrasing, and no education section | Keep as targeted synthetic probes; do not present them as realistic population samples. |
| Identity | All use “Penn DePlume” and `penn_deplume@example.org`; generated company names; phones taken from regional `phonenumbers` examples | No copied candidate identity was observed. Reserved email is suitable; example phone validity alone does not establish non-routing safety. Review or replace phones before corpus admission. |
| Historical reports | `report.csv`, `examples.md`, and `run_log.json` under `scripts/benchmark_reports/` contain relative path strings, not report payloads | Keep methodology with historical attribution; request actual run artifacts or use a newly recorded run. |

The MLX helper strips blanks/non-strings from tool lists and umbrella members
before returning them. However, `cvt_resume_dict_to_golden_dict()` merely copies
`resume_dict['tool']`. An isolated execution of that function with
`['Python', '', ' ', None]` returns those same four values. Thus the observed
gold files contain no blanks, and the ordinary generation path filters them,
but the gold writer does not independently enforce that contract. Cleanup
should filter/trim/dedupe strings at derivation and reject malformed list
shapes rather than trusting an LLM response.

## Compatibility and current benchmark signal

The branch already proposes `--json_ext` with `.json` as the default and
`.gold.json` as an option. Current main has no such option and now uses corpus
preflight. Pointing current preflight directly at the mixed artifact directory
discovers 30 PDFs and 60 JSON files, with zero matching stems and 90 errors:
`.gold` and `.synth` remain part of the discovered JSON stems.

For this review only, gold files were copied byte-for-byte into `/tmp` as
`{case_id}.json`; source and PDF bytes were unchanged. All 30 then passed both
current preflight and `validate_generated.py`. The latter's implemented
consistency check verifies `location.raw` text presence, not every skill or
full source/profile semantics; neither success establishes human-reviewed truth.

Python 3.11.8, PyMuPDF 1.22.5, current production parser, and the current 14-entry
alias map produced:

| Field | Micro-P | Micro-R | Micro-F1 | TP | FP | FN |
| --- | --- | --- | --- | --- | --- | --- |
| skills | 0.895 | 0.992 | 0.941 | 246 | 29 | 2 |
| skills_resolved | 0.895 | 0.992 | 0.941 | 246 | 29 | 2 |
| location | 0.667 | 0.067 | 0.121 | 2 | 1 | 28 |

Average resolver coverage was 0.000, with 144 distinct unknown output strings.
Equal raw/resolved scores do not establish good resolver coverage: none of the
emitted terms resolved through this alias map. Footer text was emitted as skills
in 27 cases (26 `1/1` footers and one `2/2` footer), a concrete extraction probe.
The two skills FNs are the apostrophe variants above.

`DELIVERABLE.md` reports historical skills F1 0.865 and location F1 0.125.
Those numbers are not reproduced by the current run. The branch changed scorer
Unicode normalization and used an older parser/harness; original report payloads
and environment evidence are missing. Its attribution of footer/header misses
to `benchmark.py` should be corrected: the harness scores parser output, while
section and footer extraction belong to the parser. International-case dominance
explains the slice, not all individual location misses or their root causes.

## What to preserve

1. Preserve the exact source revision and complete triples as review inputs.
   Import only individually accepted cases into a dedicated synthetic corpus
   slice, rather than replacing the default corpus wholesale. Retain unaccepted
   inputs in an experimental archive with a manifest.
2. Keep `.synth.json` as source/provenance and `.gold.json` as the answer key;
   PDFs remain the parser inputs. Rich work history is useful source context,
   but does not expand the fields scored by this issue.
3. Keep the local-generation methodology and selected failure examples, with
   the historical scores labeled as historical. Replace path-only report files
   with actual reports when preserving a run.
4. Preserve the MLX/Faker/RenderCV code in its experimental source revision for
   now. Do not merge its general `scripts/` helpers, frozen environment, or
   scorer normalization changes wholesale.

## Metadata contract for later slicing

Retain existing `job_title`, `locale`, actual experience/tool counts, `person`,
`experience`, and flat `tool` values. Add a versioned provenance object and case
manifest in a follow-up; unavailable historical values must be explicitly
unknown rather than reconstructed guesses.

| Metadata | Purpose |
| --- | --- |
| Namespaced case ID, original case ID, corpus/run ID, synthetic marker | Identity, collision prevention, and source traceability. |
| Source commit, generator version, seed, effective CLI arguments | Reproduce the generation configuration. The snapshot seeds Python, Faker, and MLX, but does not save that seed in `.synth.json`. |
| Model ID and immutable revision, prompt text/hash/version, sampling settings, raw response or response hash | Explain LLM content; model ID and low temperature alone do not guarantee reproduction. |
| Python/platform and exact Faker, MLX, RenderCV, Typst/font versions | Explain machine and rendering drift. |
| Theme, grouped/flat skills, language/locale, country, role, page count, contact layout, stress tags | Slice parser outcomes. Locale is not proof that all resume content is in that language. |
| Geocoding inputs, cached response and provider/version or offline catalog revision | Remove live Nominatim variability from replay. Local LLM generation is not wholly offline generation. |
| Gold schema/derivation version, PDF/source/gold SHA-256, extracted-text fingerprint | Separate rendering, annotation, and scoring changes. |
| Reviewer, review date, accepted/rejected status, ambiguity notes, synthetic-contact policy | Establish admission evidence independently from schema validity. |

The source is saved before grouped skills are substituted for rendering, so it
does not retain the selected umbrella layout or chosen RenderCV theme. Capture
those render inputs too. Current `.synth.json` is rich content, but incomplete
provenance. New maintained V2 annotations must follow `v2_annotation_spec.md`;
legacy V1 files may remain explicitly versioned compatibility inputs.

## Follow-up PR plan and acceptance criteria

### 1. Support a selected gold suffix throughout benchmark discovery

Add `--json_ext` limited initially to `.json` and `.gold.json`, default `.json`.
Share suffix-aware discovery/ID stripping between preflight and scoring;
strip the complete chosen suffix. With `.gold.json` selected, ignore
`.synth.json` and ordinary JSON files in a mixed output folder. Retain strict
pairing, internal-ID checks, duplicate checks, and `--allow-missing` behavior.
No autodetection or scorer normalization changes are needed.

Acceptance: existing default corpora and scores remain unchanged; mixed-directory
`.gold.json` runs and `--validate-only` select the same cases; malformed gold,
missing pairs, ID mismatches, unsupported suffixes, and empty selected corpora
fail clearly. Cover both preflight and actual CLI scoring with focused tests.

### 2. Review and import selected generated artifacts

Create a dedicated slice, for example
`backend/benchmarks/synthetic/corpora/bettyann_0543fbf/`, with `pdfs/`,
`sources/`, `golden_json/`, and a manifest. Review every admitted PDF visually,
check skills against its explicit section, verify contact-location truth and
ambiguities, and review example-phone safety. Namespace case IDs consistently
across filenames and gold; preserve original IDs and byte hashes in provenance.
Document any annotation/contact edits and rerender if PDF contacts change.

Start with grouped skills, header-versus-experience locations, footer handling,
apostrophe variants, and the two-page case. Reject duplicates that add no stress
value. Run current consistency/preflight gates, applicable canonical V2
validation for new V2 gold, and the existing scoring harness. Include exact
commands, source/harness revisions, environment, real report payloads, and
slice limitations. Passing gates does not substitute for admission review.

### 3. Make generator maintenance an optional later decision

If a maintainer accepts ownership, use
`backend/benchmarks/synthetic/experimental/bettyann/`, alongside the existing
deterministic generator. Use a dedicated venv and dependency file; the parent
`synthetic/requirements.txt` already serves the maintained WeasyPrint generator
and includes backend requirements, so do not append experimental dependencies
there or to `backend/requirements.txt`.

Separate generation (Faker, optional MLX/model, optional cached geocoding) from
rendering (RenderCV/Typst/fonts) and benchmark execution. Make MLX imports lazy
and document Apple Silicon requirements; artifact-only benchmarking must work
without MLX/RenderCV. Replace the branch's 78-package environment snapshot
with direct dependencies plus an optional platform-specific lock. Its
PyMuPDF 1.27.2.3 pin must not replace the backend's 1.22.5 benchmark environment.

Before maintenance: add explicit `--out`, collision/error handling, pure validated
gold derivation, saved render/provenance inputs, deterministic offline replay,
and small tests that require no downloaded model or geocoder. Keep generated
outputs ignored and admit cases only through PR review. No new inference backend
or abstract agent architecture is needed for this cleanup.

## Reproduce the artifact benchmark

Run from repository root with the current backend environment. The source commit
must be locally available; a deleted branch is not a reliable future fetch target.

```bash
mkdir -p /tmp/libelle-238-reproduce
git archive 0543fbf87d2c5fc86b8fbce0090689a9a97aa3b0 \
  scripts/benchmark_generate_synthetic_output \
  | tar -x -C /tmp/libelle-238-reproduce
backend/.venv/bin/python - <<'PY'
from pathlib import Path
root = Path('/tmp/libelle-238-reproduce')
gold = root / 'golden_json'
gold.mkdir(exist_ok=True)
for source in (root / 'scripts/benchmark_generate_synthetic_output').glob('*.gold.json'):
    (gold / (source.name.removesuffix('.gold.json') + '.json')).write_bytes(source.read_bytes())
PY
backend/.venv/bin/python backend/benchmarks/synthetic/generator/validate_generated.py \
  --pdf-dir /tmp/libelle-238-reproduce/scripts/benchmark_generate_synthetic_output \
  --gold-dir /tmp/libelle-238-reproduce/golden_json
backend/.venv/bin/python scripts/benchmark.py \
  --pdf_dir /tmp/libelle-238-reproduce/scripts/benchmark_generate_synthetic_output \
  --golden_dir /tmp/libelle-238-reproduce/golden_json \
  --out /tmp/libelle-238-reproduce/runs
```

## Scope and ready-to-post issue comment

For the original v0.3 scope, exclude MCP/agent orchestration, cloud generation,
automatic corpus admission, new production dependencies, parser/resolver changes,
and new scoring fields. Current V2 annotation infrastructure does not authorize
expanding scoring in #238. Revisit optional generator maintenance after the two
smaller artifact/compatibility steps have owners and reviewed examples.

> Recommendation: **split into smaller follow-up issues**. Review of BettyAnn's
> cached commit `0543fbf` found 30 complete PDF/source/gold triples with useful
> grouped-skill, footer, international-location, and two-page stress cases.
> All 30 pass current validation after temporary suffix conversion. The current
> harness at `c139ed1` scores skills micro-F1 0.941 and location micro-F1 0.121;
> these are a new run, not a reproduction of the historical report.
>
> Keep the generator experimental. First add `.gold.json` selection consistently
> to benchmark preflight and scoring while preserving `.json` defaults. Then
> import only individually reviewed artifacts with provenance and synthetic-contact
> checks. Generator maintenance can follow separately after dependency isolation,
> gold-writer validation, saved provenance/render inputs, and offline replay.
> No parser/resolver changes, production dependencies, agent workflow, or scoring
> expansion are needed. The detailed review and acceptance criteria are in
> `backend/benchmarks/synthetic/findings/REVIEW_238.md`.
