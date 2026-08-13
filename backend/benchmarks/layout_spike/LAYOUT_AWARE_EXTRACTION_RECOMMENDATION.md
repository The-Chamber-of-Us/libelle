# Layout-aware extraction — recommendation report

> `backend/benchmarks/layout_spike/LAYOUT_AWARE_EXTRACTION_RECOMMENDATION.md` · Libelle v0.3 benchmark corpus
>
> Based on findings from [PR #274 — PyMuPDF x/y multi-column layout spike](https://github.com/The-Chamber-of-Us/libelle/pull/274).
>
> **Scope note:** this comparison measures skills and location extraction only, reusing `scripts/benchmark.py`'s existing scoring functions. The V2 `sections` annotations are not scored in this comparison and are retained for future benchmark expansion.

---

## 1. Corpus changes

### Cases added (this PR)

| File | Category | Person | Notes |
|------|----------|--------|-------|
| `multi_col_01` | multi-col · replaced | Aria Novak | Updated PDF with selectable text layer; old version was image-only |
| `multi_col_03` | multi-col · new | Dara Okonkwo | True two-column: career summary + experience left, skills/education/certs/awards right |
| `multi_col_04` | multi-col · new | Jordan Castellano | True two-column; skills under non-standard "Areas of Expertise" heading |
| `multi_col_05` | multi-col · new | Elizabeth Cline | Two-column with grouped skill sub-headers (Software, Design, Soft Skills) |
| `dense_skills_01` | multi-col · new | Aaliya Nasser | Two-column; 49-item dense skills sidebar labeled "Key Skills" |
| `dense_skills_02` | multi-col · new | Leila Fontaine | Two-column; skills bullet list in left sidebar alongside right work-experience column |
| `header_contact_01` | multi-col · new | Denise Okafor | Two-column; 20+ skill items in left sidebar, prose experience in right column |
| `sparse_skill_01` | multi-col · new | Jordan Mitchell | Two-column; sparse 5-item skills list, personal-statement callout box |
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

A standalone comparison script (`backend/benchmarks/layout_aware_extraction/compare_layout_aware.py`) ran the full 20-resume corpus through both current production extraction and the hardened layout-aware prototype, scoring both against the same golden JSONs via the same scoring functions as `scripts/benchmark.py` (imported, not duplicated — see scope note above). `scripts/benchmark.py` itself was not modified. The comparison run fails loudly if any PDF/golden JSON pair is missing, so this reflects the full claimed 20-resume corpus.

**Safeguard accuracy on single-column resumes: 0 false positives out of 10.** Every genuinely single-column resume fell back to production extraction exactly — delta = 0.000 in all 10 cases (`single_col_layout_trap_01/02`, `embed_link_01/02`, `high_signal_01/02`, `low_signal_01/02`, `non_usa_01/02`). This holds after all fixes described below — no new false positives were introduced at any stage.

**Safeguard sensitivity on true multi-column resumes: 6 of 10 trigger layout-aware extraction.** `dense_skills_01`, `dense_skills_02`, `multi_col_05`, and `project_heavy_01` (4 resumes) still fall back to production despite being genuine multi-column layouts, meaning current thresholds remain too conservative for some legitimate two-column layouts.

**Final results on the 6 cases where layout-aware extraction triggers:**

| Resume | Prod F1 | LA F1 | Delta | Verdict |
|---|---|---|---|---|
| `header_contact_01` | 0.000 | 0.467 | **+0.467** | Real improvement — sidebar skills recovered |
| `multi_col_01` | 0.500 | 0.667 | **+0.167** | Real improvement |
| `multi_col_02` | 0.258 | 0.381 | **+0.123** | Confirmed fix — see below |
| `multi_col_03` | 0.360 | 0.562 | **+0.202** | Real improvement, newly recovered after header-detection fix |
| `multi_col_04` | 0.000 | 0.387 | **+0.387** | Real improvement — golden JSON now populated per the finalized V2 grouped-skills rule (PR #345); "Areas of Expertise" content is treated as skills-equivalent, making this resume's skill extraction meaningfully scorable |
| `sparse_skill_01` | 0.400 | 0.556 | **+0.156** | Confirmed fix — see below |

**Root cause of the two regressions — confirmed, not hypothesized.** Diagnostic output (`diagnostics.json`, generated per-resume for every triggered case: production text, layout-aware text, extracted skills for both, and exact skill-level diffs against gold) traced both original regressions to the same bug: `_get_flat_blocks()` flattened all lines within a PyMuPDF text block into a single space-joined string, discarding the internal line breaks that separate individual skill items and, in `sparse_skill_01`'s case, separate a trailing content line from an immediately following section header. This corrupted both header detection (a header glued to preceding text is no longer recognizable as a standalone header) and multi-item skill lists (collapsed into one unreadable string). Fixing `_get_flat_blocks()` to preserve line breaks (joining lines with `\n` instead of flattening to a single string) resolved both cases with zero skills lost in either (`lost_in_la: []` in both diagnostics entries), confirmed by rerunning the full comparison.

---

## 5. What causes missed detections, and what was fixed

**Header detection bug — found and fixed.** `_is_header()` previously lowercased text before checking `.isupper()`, making the uppercase-detection path permanently unreachable. This was fixed to check case before lowercasing. `HEADER_KEYWORDS` was also expanded to cover corpus headings not previously recognized (`profile`, `career summary`, `key skills`, `areas of expertise`, `short courses`, `technical toolkit`, `core competencies`, `specialised skills`). This fix alone recovered `multi_col_03` from a missed case to a correctly triggered improvement (+0.202), with zero new false positives introduced on the single-column corpus.

**Text-flattening bug — found and fixed.** As detailed in Section 4, `_get_flat_blocks()` was collapsing multi-line blocks into single strings, which was the confirmed root cause of both prior regressions. Both `multi_col_02` and `sparse_skill_01` are now net improvements after this fix.

**Remaining open issue: safeguards still too conservative on some true multi-column resumes.** `dense_skills_01`, `dense_skills_02`, `multi_col_05`, and `project_heavy_01` still fall back to production despite being genuine two-column layouts. This is a distinct, still-unresolved issue from the two fixed above — likely related to `MIN_BLOCKS_PER_LANE`, `MIN_VERTICAL_OVERLAP_RATIO`, or `MIN_HEADERS_ACROSS_LANES` being tuned too strictly for these particular layouts, but this has not yet been diagnosed with the same rigor as the two confirmed bugs above and should not be assumed without further investigation.

---

## 6. Safeguards implemented and next steps

Current safeguards (`backend/benchmarks/layout_aware_extraction/layout_aware_extraction.py`):

- Minimum block count per detected lane (≥ 3 blocks)
- Vertical overlap validation between lanes (≥ 30% of page height)
- Isolated header/contact block exclusion (lane confined to top/bottom 15% of page height is rejected)
- Sustained two-column structure requirement (headers must be present in both lanes)
- Low-confidence fallback to production extraction when any safeguard fails

**Next steps:**

- Diagnose why the remaining 4 true multi-column resumes still fall back, using the same diagnostics-first approach that resolved the two confirmed bugs above, before adjusting any threshold values
- Investigate the tokenization gap responsible for `multi_col_02`'s remaining distance from a perfect score (e.g. gold `"environmental testing procedures"` vs. LA's separate `"environmental testing"` + `"procedures"`) — a normalization issue distinct from the now-fixed corruption bug
- `sparse_skill_01`'s `la_skills` output includes some noise from a personal-statement callout box (e.g. `"jordan"`, `"mitchell"` as stray entries) — a precision issue worth a future look, separate from the recall bug that was fixed
- **Known limitation, not a current bug:** `extract_text_from_pdf_layout_aware()` sets its top-level `layout_aware_used` flag via `any(...)` across all pages of a document. For a hypothetical multi-page resume where some pages trigger layout-aware extraction and others fall back, the joined result would not guarantee byte-identical production text on the fallback pages the way it does for single-page documents. All fixtures in this corpus are single-page, so this does not affect the reported results above — flagged here as follow-up work before this prototype is tested against multi-page resumes.

All safeguards are implemented as real, testable code with explicit thresholds — not inline conditionals — so they can be tuned and re-benchmarked independently.

---

## 7. Recommendation

**Keep experimental — do not adopt.**

The approach shows promise, and the safeguards appear conservative on this corpus (zero false positives across all 10 single-column controls), but both detection coverage and text reconstruction required further validation before this iteration — and that validation is now largely complete. Two confirmed bugs (header detection, block text flattening) have been root-caused via diagnostic evidence and fixed, converting two prior regressions into improvements with zero regressions remaining across the full 20-resume corpus. One open issue remains: 4 of 10 true multi-column resumes still fail to trigger layout-aware extraction at all, which has not yet been diagnosed with the same rigor.

Before revisiting adoption: diagnose why the remaining 4 multi-column cases don't trigger, address the tokenization and callout-box noise issues noted above, and re-run this comparison. Revisit the adopt/defer decision once detection coverage across true multi-column resumes is more complete and consistent, with continued zero regression on single-column resumes.