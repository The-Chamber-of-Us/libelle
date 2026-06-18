# PyMuPDF X/Y & Multi-Column Layout Spike — Findings

**Status:** Observation only. No production code was modified as part of this spike.
**Related issue:** PyMuPDF x/y & multi-column layout research spike

---

## 1. Files inspected

| File | Why selected |
|---|---|
| `multi_col_02.pdf` (Lina Calder) | Suspected multi-column / reading-order issue — floating text-box layout |
| Volunteer resume (real, non-synthetic — filename withheld) | Suspected multi-column / reading-order issue — sidebar-style two-column layout |
| `embed_link_01.pdf` (Daniel Foster) | Clean single-column control |
| `high_signal_01.pdf` (Rohan Mehta) | Dense skills resume, with sub-header-labeled skill groups |
| `Jadhav_Riya.pdf` | Project-heavy / academic-style resume |

---

## 2. PyMuPDF extraction modes inspected

- `get_text("text")` — plain text, raw storage order
- `get_text("blocks")` — current production extraction (sorted globally by `(y0, x0)`)
- `get_text("blocks")` + x0 clustering — custom column-aware sort (per-lane `y0` sort)
- `get_text("dict")` — block/line/span structure with bounding boxes
- `page.find_tables()` — attempted; **not available** in the installed PyMuPDF version (`AttributeError: 'Page' object has no attribute 'find_tables'`). Requires PyMuPDF 1.23+. Not evaluated further in this spike.
- Custom header-scoped grouping (built on top of `get_text("dict")` + column lanes) — bucketed content under the nearest header above it within the same column lane

External reference: PyMuPDF's `multi_column.py` utility (via `column_boxes()`) was tested independently as a conceptual comparison point. It was **not copied into Libelle** per the issue's licensing guardrail — our column detection and header-scoping logic was written independently using `get_text("blocks")` / `get_text("dict")` directly.

---

## 3. Plain text vs x/y coordinate view, per file

### Lina Calder (`multi_col_02.pdf`)
- **Plain text:** Headers and content scattered with no usable order (e.g. all section headers grouped together near the top, separate from their content).
- **Current production (`blocks`, global y0/x0 sort):** Confirmed interleaving — e.g. an Education entry (`B.Sc. Environmental Science`) appears directly inside the Experience block, between a date range and a company name.
- **Column-aware (x0 clustering):** No interleaving. Boundary detected at x=105.2. Left lane (Education, Skills, Tools, Soft Skills) and right lane (Experience, Projects, References) each read correctly top-to-bottom.
- **Header-scoped:** Cleanest result. Every section's content is grouped under its correct header, in both lanes, matching the human reading order exactly.
- **Does coordinate view match human reading order better?** Yes, clearly.

### Volunteer resume — sidebar two-column layout
- **Current production:** The "About Me" paragraph is split mid-sentence and interleaved with Contact info lines — the worst interleaving observed in this spike.
- **`column_boxes()` (external reference tool):** Detected 3 regions; correctly isolated the left sidebar (Contact/Education/Skills/Languages) and most of the right column (Projects & Experience), but split the "About Me" paragraph across two of the three regions.
- **Does coordinate view match human reading order better?** Yes, substantially — though not perfectly, since paragraph-spanning text can still get cut across detected regions.

### Daniel Foster (`embed_link_01.pdf`) — control
- **Current production:** No interleaving issues (as expected — single column).
- **Column-aware:** Boundary detection produced a **false positive** — `DANIEL FOSTER` (name, large/centered text) was isolated into its own "right column" lane while every other block landed correctly in the left lane.
- **Header-scoped:** All section content (Objective, Experience, Education, Skills, Project, Certifications) correctly grouped under headers in the left lane. Impact of the false-positive column split was cosmetic only — the name ended up alone in `[no header]` on the right, with no effect on any other field.

### Rohan Mehta (`high_signal_01.pdf`) — dense skills
- **Current production:** No interleaving (single column resume).
- **Column-aware:** False positive again — boundary detected at x=263.4 because the contact info block (email/phone/location) is right-aligned near the bottom of the page. Everything else landed correctly in the left lane.
- **Header-scoped:** Skills sub-header labels (`Structural Engineering:`, `Geotechnical & Hydrology:`, etc.) were preserved as intact labels rather than flattened into the skill list — correct behavior for this resume's structure. All sections grouped correctly under their headers.

### Riya Jadhav (`Jadhav_Riya.pdf`) — project-heavy / academic
- **Current production:** No interleaving (single column resume), reads top to bottom correctly via plain block sort.
- **Column-aware:** False positive, and this time **damaging**. Boundary detected at x=106.3. All section headers (`SKILLS`, `PROJECTS`, `EXPERIENCE`, `EDUCATION`) ended up isolated in the right lane as empty placeholders, while all actual section content landed in the left lane under `[no header]`. The header-to-content association was fully broken.
- **Header-scoped:** Failed for this file — see above. This is the clearest example in the spike of the column-detection heuristic causing harm rather than help.
- **Does coordinate view match human reading order better?** No — worse than current production for this file.

---

## 4. Multi-column / reading-order findings

- **Does PyMuPDF expose enough x/y information to identify column structure?** Yes. Block-level `bbox` data (from both `get_text("blocks")` and `get_text("dict")`) is sufficient to detect column boundaries via x0 clustering, at least for the layouts in this sample.
- **Does block order match the expected human reading order?** Not by default. Current production's global `(y0, x0)` sort does not match human reading order on multi-column resumes (Lina, volunteer resume). It does match human reading order on single-column resumes.
- **Are there cases where current plain-text output interleaves columns or sections?** Yes — confirmed and reproducible on both multi-column sample files.
- **Would reading one visual column at a time likely produce a better parser input?** Yes, for genuinely multi-column resumes. The column-aware and header-scoped views were measurably cleaner than current production on Lina's and the volunteer resume.
- **Are there cases where x/y data looks noisy or unreliable?** Yes. The column-boundary heuristic produced false positives on 3 of 3 single-column resumes tested, triggered by isolated blocks (a name, or contact info) sitting at an x0 far enough from the page's main content to look like a second column. In most cases this was cosmetic (Daniel, Rohan), but in one case (Riya's resume) it actively broke header-to-content association.

---

## 5. Secondary observations

- **Section grouping:** Header-scoped grouping (bucketing content under the nearest header above it, per lane) worked very well on multi-column resumes and most single-column resumes, when the column-boundary heuristic didn't misfire.
- **Header/body relationships:** Confirmed via `bbox` inspection that header blocks are visually and spatially distinguishable (all-caps formatting, isolated bbox above their section's content) — supports the idea that header detection logic could be enhanced with position data later, though this spike did not need it since text-level ALL CAPS + keyword matching was already sufficient to identify headers correctly across all 5 files.
- **Dense skills blocks:** On Rohan's resume, the sub-header-labeled skill groups (`Structural Engineering: ...`) were preserved as single blocks by `get_text("blocks")` — coordinate data wasn't necessary to keep these intact, since they were already single blocks in plain text.
- **Contact/header grouping:** Contact info blocks were generally isolated as their own block by PyMuPDF, which is what triggered most of the false-positive column detections in this spike — worth keeping in mind if column detection logic is ever pursued further.

---

## 6. Text-only sufficiency check

| Observed issue | Could a text-only heuristic solve it? |
|---|---|
| Multi-column interleaving (Lina, volunteer resume) | **No.** This is a genuine extraction-layer information-loss problem — the column structure isn't recoverable from plain text alone once columns have been interleaved by global y0/x0 sort. |
| False-positive column detection on single-column resumes (Daniel, Rohan, Riya) | This is a problem **introduced by the x/y approach itself**, not solved by it. A simple safeguard (e.g. minimum block count per lane, or checking that both lanes have vertically overlapping content across most of the page) would likely prevent most false positives — this is a refinement to the layout-aware approach, not a text-only alternative. |
| Skills sub-header label preservation (Rohan) | **Yes** — already handled correctly by plain block-level extraction; x/y data added no value here. |
| Header/content association in normal single-column resumes | **Yes** — already works via text-level header keyword + ALL CAPS detection; x/y data only matters once a column split is (correctly or incorrectly) triggered. |

**Conclusion:** Interesting but not currently necessary for single-column resumes — text heuristics already handle them well. The x/y approach is necessary specifically for genuinely multi-column layouts, but currently is not reliable enough to apply unconditionally across all resumes due to false-positive column detection.

---

## 7. Recommendation

**Useful later, but not needed for v0.3.**

X/y coordinate data and block-level column detection clearly identify and fix real reading-order failures on multi-column resumes (2 of 5 sample files showed confirmed interleaving in current production, both resolved cleanly by column-aware + header-scoped extraction). However:

- The column-boundary heuristic in its current exploratory form produces false positives on single-column resumes (3 of 3 single-column files tested), and in one case actively broke header/content association.
- Before this could be safely introduced to production, the boundary-detection heuristic would need hardening (minimum-blocks-per-lane checks, vertical-overlap validation between lanes, or similar safeguards) to avoid regressing single-column resumes, which make up the majority of the benchmark corpus.
- Given that, this is not a drop-in replacement for current extraction yet, and the existing benchmark failures for multi-column resumes are a known, bounded subset of the corpus — not urgent enough to justify the additional complexity for v0.3.

This spike confirms multi-column reading-order failures are a genuine extraction-layer information-loss problem (not solvable by parser heuristics alone), which justifies revisiting layout-aware extraction in a future milestone once the false-positive issue has a clear mitigation plan.

---

## Appendix: Exploratory scripts

- `inspect_pymupdf_layout.py` — full inspection script covering all 6 extraction modes (plain text, current production blocks, column-aware blocks, dict view with header flags, table detection, header-scoped grouping)
- `test_layout_extraction.py` — lighter CLI-runnable version covering only the two modes that proved useful (column-aware, header-scoped), for quick ad hoc testing: `python test_layout_extraction.py <pdf_path>`

Both scripts are exploratory only and are not imported by any production code path.