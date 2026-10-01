# Python / PyMuPDF compatibility review (#316)

## Decision

Keep the exact `PyMuPDF==1.22.5` pin and use **CPython 3.11** for backend
development and benchmark contributions. Python 3.12 and later are not supported
by this contributor setup. Do not loosen the pin or substitute a newer version
locally for comparable benchmark results.

The tested replacement, `1.27.2.3`, installs on Python 3.12 but fails five existing
semantic parser regressions. Supporting 3.12 requires a separately validated
dependency/extraction change. This review changes setup guidance, not parser
behavior or corpus annotations.

## Installation findings

[PyPI's 1.22.5 release files](https://pypi.org/project/PyMuPDF/1.22.5/#files)
include CPython 3.11 wheels for macOS ARM64 (11+), macOS Intel (10.9+),
Windows, and Linux x86-64/aarch64 (glibc 2.17+). Their `cp311-cp311` tags do
not support CPython 3.12; this release has no 3.12 or stable-ABI wheel.
Its broad `Requires-Python >=3.7` metadata does not promise wheels for future
Python versions. With no matching wheel, pip falls back to the source archive;
the upstream installation instructions mention SWIG for that path.

On macOS 26.4.1 ARM64, Python 3.12.14 reproduced the missing-wheel failure:

```sh
python -m pip download --only-binary=:all: --no-deps \
  --dest /tmp/pymupdf-wheel-check PyMuPDF==1.22.5
# ERROR: No matching distribution found for PyMuPDF==1.22.5
```

This confirms the wheel incompatibility without invoking a C/C++ source build;
the original contributor's exact Python 3.12.4/SWIG failure was not replayed.
[PyMuPDF 1.27.2.3](https://pypi.org/project/PyMuPDF/1.27.2.3/) installed
successfully in isolated Python 3.11.8 and 3.12.14 environments using
`pymupdf-1.27.2.3-cp310-abi3-macosx_11_0_arm64.whl`. That stable-ABI wheel
supports both runtimes. Successful installation does not establish parser
compatibility.

## Supported benchmark setup

From the repository root, with Python 3.11 installed:

```sh
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --only-binary=PyMuPDF \
  -r backend/requirements.txt -r backend/requirements-dev.txt
python -m pip check
python -m pytest backend/tests -q
python scripts/benchmark.py --parsers libelle
```

The committed benchmark PDFs need no Google credentials, SWIG, compiler, or
WeasyPrint installation. Generating the separate
[synthetic corpus](../backend/benchmarks/synthetic/README.md) still requires its
documented WeasyPrint system libraries. Its requirements now include the backend
requirements so the parser dependencies and PyMuPDF pin remain aligned.

If binary installation fails, check `python --version`, upgrade pip, and confirm
that the OS/architecture matches an upstream wheel. Recreate the virtual
environment with Python 3.11 if necessary; an existing 3.12 environment cannot
be converted by activating a different interpreter. Report unsupported platforms
instead of installing SWIG or removing the binary-only option. Source builds
are outside the supported contributor path; SWIG is not a missing Python
requirement. Python 3.11 CI also requires a PyMuPDF wheel.

## Extraction and benchmark evidence

Validated on 2026-10-01 against source revision `e04ab03`, using macOS ARM64,
Python 3.11.8 (both PyMuPDF versions) and Python 3.12.14 (candidate only).
The same 20 committed PDFs and gold annotations were used throughout.
The default corpus preflight passes with its existing mixed V1/V2 schema warning.

| Check | 1.22.5 / Python 3.11 | 1.27.2.3 / Python 3.11 and 3.12 |
| --- | --- | --- |
| Full backend suite | 527 passed | 522 passed, 5 failed on each runtime |
| Skills micro P / R / F1 | 0.639 / 0.671 / 0.655 | 0.645 / 0.671 / 0.658 |
| Resolved skills micro F1 | 0.670 | 0.673 |
| Location micro F1 | 0.733 | 0.733 |
| Five-case layout corpus skills micro F1 | 0.977 | 0.977 (Python 3.12) |

Exact production flattened text changes on 12/20 committed PDFs. Parser output
changes on 9/20, comparing `_run_libelle`'s parsed result while excluding runtime.
Candidate extraction and parsed results are identical between Python 3.11 and
3.12 across those 20 PDFs plus five layout fixtures. The layout PDFs were
generated once with 1.22.5 and reused for comparison. Their text and parsed
results do not change. The layout regression tests also pass with the candidate,
so this small corpus alone would not detect the upgrade's semantic damage.

The existing `backend/tests/test_pymupdf_semantic_regressions.py` identifies the
following candidate failures; all six tests in that file pass with the old pin:

| Existing test | Candidate failure |
| --- | --- |
| `test_project_heavy_preserves_annotated_projects` | First project title ends at “Young”; its “Adults” continuation and subsequent projects move beyond the Skills section in flattened text. |
| `test_project_heavy_preserves_annotated_work_narrative_continuity` | A new block separator breaks a source work narrative across parser entries. |
| `test_sparse_skill_preserves_clinical_work_experience` | Parsed work experience becomes empty. |
| `test_multi_col_02_preserves_source_education` | Education loses the institution/date facts asserted by the test. |
| `test_high_signal_02_preserves_source_project_identities` | Project titles no longer begin their own semantic entries. |

The skill score improvement reflects three fewer false positives in
`single_col_layout_trap_02`; it does not measure the lost work/project/education
content. Retain these semantic assertions and annotations unchanged when
evaluating another upgrade. A future candidate must preserve those facts as well
as run the full benchmark; matching aggregate scores is insufficient.

To repeat the comparison, use separate Python 3.11 environments with the full
backend and development requirements. Leave one at the repository pin and
explicitly install `PyMuPDF==1.27.2.3` with `--only-binary=PyMuPDF` in the other.
Run the full tests and `scripts/benchmark.py --parsers libelle --out <separate-dir>`
in each. Compare `summary.json` scores and per-resume `report.csv`, excluding
timing. For extraction, compare `extract_pdf_text_from_bytes(pdf.read_bytes()).text`
from `backend/services/pdf_text_extraction.py` on the same PDFs; for parser
results compare the first element returned by `scripts.benchmark._run_libelle`.

Finally, reinstalling the retained pin in the isolated Python 3.11 environment
passed `pip check`, all 527 backend tests, the 20-PDF benchmark with baseline
scores, and the five-case layout consistency/preflight (`BENCHMARK-READY`).
No Linux/Windows installation or live staging deployment was executed locally;
the existing Linux Python 3.11 CI job remains the repository platform check.
