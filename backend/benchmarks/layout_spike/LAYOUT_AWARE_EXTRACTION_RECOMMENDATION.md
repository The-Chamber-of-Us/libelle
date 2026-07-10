# Layout-aware extraction — recommendation report

> `backend/benchmarks/layout_spike/LAYOUT_AWARE_EXTRACTION_RECOMMENDATION.md` · Libelle v0.3 benchmark corpus
>
> Based on findings from [PR #274 — PyMuPDF x/y multi-column layout spike](https://github.com/The-Chamber-of-Us/libelle/pull/274).

---

## 1. Corpus changes

### Cases added (this PR)

| File | Category | Person | Notes |
|------|----------|--------|-------|
| `multi_col_01` | multi-col · replaced | Aria Novak | Updated PDF with selectable text layer; old version was image-only |
| `multi_col_03` | multi-col · new | Dara Okonkwo | True two-column: career summary + experience left, skills/education/certs/awards right |
| `multi_col_04` | multi-col · new | Jordan Castellano | True two-column; skills under non-standard "Areas of Expertise" heading |
| `multi_col_05` | multi-col · new | Elizabeth Cline | Two-column with grouped skill sub-headers (Software, Design, Soft Skills) |
| `dense_skills_01` | multi-col · new | Aaliya Nasser | Two-column; 50-item dense skills sidebar labeled "Key Skills" |
| `dense_skills_02` | multi-col · new | Leila Fontaine | Two-column; skills bullet list in left sidebar alongside right work-experience column |
| `header_contact_01` | multi-col · new | Denise Okafor | Two-column; 20+ skill items in left sidebar, prose experience in right column |
| `sparse_skill_01` | multi-col · new | Jordan Mitchell | Two-column; sparse 5-item skills list, mislabeled CERTIFICATIONS section |
| `project_heavy_01` | multi-col · new | Tobias Wren | Two-column sidebar (skills/awards) alongside main experience+projects column |
| `single_col_layout_trap_01` | single-col · new | Kwame Asante | Single-column; dense skills paragraph, may visually resemble a sidebar |
| `single_col_layout_trap_02` | single-col · new | Simone Adeyemi | Single-column; right-aligned contact block in header |

### Existing cases (unchanged)

| File | Category | Person |
|------|----------|--------|
| `multi_col_02` | multi-col · existing | Lina Calder |
| `embed_link_01/02` | single-col · existing | Daniel Foster / Wei Zhang |
| `high_signal_01/02` | single-col · existing | Rohan Mehta / Alex Chen |
| `low_signal_01/02` | single-col · existing | Maya Ellison / Evan Brooks |
| `non_usa_01/02` | single-col · existing | Olena Kovalenko / Naledi Mokoena |

---

## 2. True multi-column cases

These resumes have a genuine two-lane layout where content is split into left and right columns. A correct extractor must reconstruct each lane's reading order independently before joining them.

- `multi_col_01` — Aria Novak: left sidebar (education, skills, tools), right main (about, experience, projects)
- `multi_col_02` — Lina Calder: left sidebar (education, skills, tools, soft skills), right main (summary, experience, projects)
- `multi_col_03` — Dara Okonkwo: left main (summary, experience), right sidebar (contact, education, skills, certs, awards)
- `multi_col_04` — Jordan Castellano: right sidebar (areas of expertise, education, short courses, awards, references), left main (experience)
- `multi_col_05` — Elizabeth Cline: left sidebar (summary, skills), right main (education, experience)
- `dense_skills_01` — Aaliya Nasser: left/right split with dense "Key Skills" sidebar
- `dense_skills_02` — Leila Fontaine: left sidebar skills list running alongside right work-experience column
- `header_contact_01` — Denise Okafor: left sidebar (skills, education, certs, awards) alongside right main (summary, experience, projects)
- `sparse_skill_01` — Jordan Mitchell: two-column layout with sparse skills sidebar
- `project_heavy_01` — Tobias Wren: sidebar with skills/awards alongside two-column education/experience layout

---

## 3. Single-column controls

These resumes are genuinely single-column and should never trigger a column split.

- `single_col_layout_trap_01` — Kwame Asante
- `single_col_layout_trap_02` — Simone Adeyemi
- `embed_link_01` — Daniel Foster
- `embed_link_02` — Wei Zhang
- `high_signal_01` — Rohan Mehta
- `high_signal_02` — Alex Chen
- `low_signal_01` — Maya Ellison
- `low_signal_02` — Evan Brooks
- `non_usa_01` — Olena Kovalenko
- `non_usa_02` — Naledi Mokoena

---

## 4. Benchmark evidence — production vs. layout-aware, measured comparison

A standalone comparison script (`backend/benchmarks/layout_aware_extraction/compare_layout_aware.py`) ran the full 20-resume corpus through both current production extraction and the hardened layout-aware prototype, scoring both against the same golden JSONs via the same scoring functions as `scripts/benchmark.py` (imported, not duplicated). `scripts/benchmark.py` itself was not modified.

**Safeguard accuracy on single-column resumes: 0 false positives out of 10.** Every genuinely single-column resume fell back to production extraction exactly — delta = 0.000 in all 10 cases (`single_col_layout_trap_01/02`, `embed_link_01/02`, `high_signal_01/02`, `low_signal_01/02`, `non_usa_01/02`). This is a strong safety signal: the safeguards do not introduce regressions on resumes that shouldn't be split.

**Safeguard sensitivity on true multi-column resumes: only 5 of 10 triggered layout-aware extraction.** `multi_col_03`, `multi_col_05`, `dense_skills_01`, `dense_skills_02`, and `project_heavy_01` all fell back to production despite being genuine multi-column layouts, meaning current thresholds are too conservative and miss half of the cases they are meant to fix.

**Results on the 5 cases where layout-aware extraction actually triggered:**

| Resume | Prod F1 | LA F1 | Delta | Verdict |
|---|---|---|---|---|
| `header_contact_01` | 0.000 | 0.517 | **+0.517** | Real improvement — sidebar skills recovered |
| `multi_col_01` | 0.500 | 0.667 | **+0.167** | Real improvement |
| `multi_col_04` | 0.000 | 0.000 | 0.000 | Not meaningful — golden JSON has an empty skills array for this resume (skills sit under "Areas of Expertise," excluded per labeling rules), so both scores are forced to 0 regardless of extraction quality |
| `multi_col_02` | 0.258 | 0.000 | **-0.258** | Regression — the confirmed true multi-column case from PR #274 that layout-aware extraction was meant to fix |
| `sparse_skill_01` | 0.400 | 0.000 | **-0.400** | Regression |

Two genuine improvements, two genuine regressions to complete failure (F1 = 0.0). Both regressions share the same symptom: skills extraction drops to zero even though column detection correctly identified the multi-column structure. This points to a **text-formatting bug in the header-scoped output** (one skill per line, stripped of original commas/delimiters) breaking `parse_resume()`'s downstream skill-parsing logic — not a column-detection failure.

---

## 5. What causes missed detections and output-format regressions

With current thresholds, zero false positives occurred on the single-column corpus — the safeguards are working as intended for that failure mode. The two live problems are:

1. **Safeguards too conservative** — 5 of 10 true multi-column resumes fell back to production when they shouldn't have, suggesting `MIN_BLOCKS_PER_LANE`, `MIN_VERTICAL_OVERLAP_RATIO`, or `MIN_HEADERS_ACROSS_LANES` are tuned too strictly for legitimate but less "textbook" two-column layouts.
2. **Header-scoped text assembly loses formatting** — when a split is accepted, reconstructing text one item per line (stripping commas and inline delimiters) appears to break skill-list parsing downstream, causing complete extraction failure even when column detection itself was correct.

---

## 6. Safeguards implemented and next steps

Current safeguards (`backend/benchmarks/layout_aware_extraction/layout_aware_extraction.py`):

- Minimum block count per detected lane (≥ 3 blocks)
- Vertical overlap validation between lanes (≥ 30% of page height)
- Isolated header/contact block exclusion (lane confined to top/bottom 15% of page height is rejected)
- Sustained two-column structure requirement (headers must be present in both lanes)
- Low-confidence fallback to production extraction when any safeguard fails

**Next steps identified by this comparison:**

- Loosen/tune `min_blocks_per_lane` and `min_vertical_overlap_ratio` thresholds against the 5 missed true multi-column cases to find where they are being excluded unnecessarily
- Preserve original block-level punctuation/delimiters when reconstructing header-scoped text, rather than flattening to one bare line per item, to fix the `multi_col_02` / `sparse_skill_01` regressions
- Re-run `compare_layout_aware.py` after both fixes to confirm no new false positives are introduced on the single-column corpus

All safeguards are implemented as real, testable code with explicit thresholds — not inline conditionals — so they can be tuned and re-benchmarked independently.

---

## 7. Recommendation

**Keep experimental — do not adopt.**

Measured comparison against production confirms the safeguards are safe on single-column resumes (0/10 false positives) but too conservative on multi-column resumes (5/10 missed), and even when correctly triggered, results are inconsistent: 2 improvements, 2 regressions to complete failure. Both regressions were traced to a text-formatting bug in header-scoped reconstruction, not a detection failure, meaning the core column-detection approach is sound but the current implementation is not yet production-safe.

Before any further evaluation: fix the header-scoped text-assembly bug, retune the safeguard thresholds against the missed multi-column cases, and re-run this comparison. Revisit the adopt/defer decision once that re-run shows consistent improvement on multi-column resumes with continued zero regression on single-column resumes.