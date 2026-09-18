# #387 investigation: skill semantic lineage

## Decision: B — bounded hardening is justified

Investigated checkout: `742ab5225fb6d6f494972a3bd9a1717ada1321ff`.
This document is the proposed issue comment. No production behavior changed.

The current system distinguishes **parser-normalized observations** from
**Resolver V1 conclusions**, but does not record evidence-level provenance.
`resolved_skill_ids` alone cannot explain a capability assertion.

One concrete existing boundary warrants a separately reviewed follow-up:
**the durable worker discards positioned PDF text and bypasses the existing
layout-aware `parse_resume_pdf` operation**. The same PDF can therefore produce
different skill observations in the worker and the canonical parser/benchmark.
This is reproducible without a new evidence model or resolver changes.

The frozen PRD does **not** require an Organizational Knowledge Foundation,
capability model or semantic retrieval in v0.5. Its release is Assisted
Understanding plus human coordination. Richer evidence/capability relationships
are possible post-v0.5 work, to be earned through observed need.

PRD assessed: [Libelle v0.5 — Contributor Coordination, FINAL / FROZEN](https://docs.google.com/document/d/1YZM9KpWiDGgX8AXwUtvfhGj9ZSj_ovI3nHPh483fLj8/edit),
dated September 7, 2026, sections 1–34, supplied in full as pasted text. The
comparison below uses that text. The issue's knowledge-foundation framing is
out of alignment with this frozen release boundary; it is retained below only
as a future-direction question, not an implementation requirement.

## 1. Actual execution paths

Intake uploads the PDF, writes the submission with `drive_file_id`, then enqueues
`parse_resume` (`backend/services/intake_service.py`, `finalize_submission` flow).
Raw intake `skills_raw` is separate from PDF-derived skills and is not the
Resolver input on this path.

```text
submissions + Drive PDF → parser_jobs → ParserWorker._execute_attempt
  → _run_parser: download_file → extract_text_from_pdf_bytes → parse_resume
  → persist_parser_result_if_missing(submission_id, parser_run_id)
  → _add_resolver_output → resolve_extracted_profile
  → persist_resolver_output_for_parser_result(same submission/run pair)
  → job authoritative_parser_run_id
  → assemble_snapshot_records → GET /snapshot
```

`ParserWorker` is the active intake/deployment path on the investigated `main`
revision, instantiated by `backend/parser_worker.py` and
`scripts/run_parser_worker_service.py`.

The repository also contains a materially different parsing operation exercised
by benchmarks/tests:

```text
benchmark / tests
  → parse_resume_pdf → extract_pdf_text_from_bytes
  → project_skill_sections → _parse_resume_with_skill_text
```

`parser_service.parse_and_update` also calls `parse_resume_pdf`, but has no
non-test caller in this revision. It enriches and appends a result; the durable
worker persists parser output first and fills resolver fields later. These are
not two equivalent active production paths. Here, “canonical PDF parser” names
the existing `parse_resume_pdf` operation, not the deployed worker's entrypoint.
Tracing only `parse_and_update` would miss the live intake/deployment path.

Code anchors at the investigated revision:

- [Intake](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/services/intake_service.py#L270), [worker execution and parser call](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/services/parser_worker.py#L82).
- [Positioned PDF extraction](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/services/pdf_text_extraction.py#L24), [skill ownership projection](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/services/skill_section_projection.py#L259), [canonical PDF parser](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/services/resume_pdf_parser.py#L10).
- [Skill tokenization](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/parser.py#L221), [Resolver adapter](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/services/parser_service.py#L73), [pure Resolver V1](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/resolver/resolver.py#L13), [shipped aliases](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/resolver/knowledge/aliases_v1.json).
- [Run persistence](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/storage/sheets_repo.py#L393), [row serialization](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/storage/sheets_repo.py#L638), [schema](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/sheet_schema.py).
- [Snapshot composition](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/services/dashboard_service.py#L75), [run selection](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/services/dashboard_parser_results.py#L91), [API models](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/api/models/dashboard.py), [read and reviewer-write routes](https://github.com/The-Chamber-of-Us/libelle/blob/742ab5225fb6d6f494972a3bd9a1717ada1321ff/backend/api/routes/dashboard.py).

## 2. Boundary inventory

| Boundary | Representation and information preserved/added | Transformation/loss and reconstruction |
| --- | --- | --- |
| Source → PDF extraction | Drive reference belongs to submission/job. Extraction produces flattened text plus `ExtractedPdfText.positioned_pages`, page dimensions and text-block coordinates. | Text extraction ignores image blocks; there is no OCR here. Sidecar and extracted text are transient. PDF can be inspected/re-extracted if retained and accessible; no per-run content digest or immutable source revision is stored. A Drive ID is not proof of the exact historical bytes. |
| Extraction → skill ownership | Canonical path classifies single/multiple/ambiguous columns and collects text under explicit skill headings. Ambiguous layout uses first-section fallback. | Projection emits synthetic `SKILLS` text plus layout classification, without token-to-source links. Caller retains only projected text. Page/block/heading ownership and excluded candidates are not persisted. Worker instead takes flattened text directly, losing the sidecar before ownership decisions. Reprocessing can recover current interpretation, not a stored historical decision. |
| Ownership → parser output | `skills = {value: List[str], confidence: float}`. Other parsed fields include work/projects. Skill confidence is 1.0 for nonempty output, otherwise 0.0. | Removes category prefixes and parenthetical content, splits delimiters, normalizes Unicode/whitespace/case. `Python (5 years)` becomes `python`. No token spans or rejection reason. Source spelling/context requires PDF; `parsed_skills_raw` is not verbatim source text. |
| Parser → Resolver input | `ExtractedProfileV1(submission_id, skills, location_raw, meta)`. Skills are copied, not replaced; runtime meta names the adapter. | Skill confidence, work/project context and all geometry are absent from Resolver input. `parser_run_id` is not in this input schema, although the worker carries it externally. |
| Resolver input → result | Exact lookup of normalized keys in shipped aliases. Output: canonical skill list, unknown strings, counts/coverage, resolver and alias versions. | Deduplicates canonical IDs and normalized unknown keys; unknowns retain first input spelling. No per-observation mapping edge or match reason. Input meta is replaced by version meta. Original input list remains in `parsed`, so duplicates and alias observations can be re-evaluated with the correct historical code/map. |
| Result → durable row | Same `(submission_id, parser_run_id)` contains JSON strings for `parsed_skills_raw`, `resolved_skill_ids`, `unknown_skills`; scalar coverage, versions, timestamp and parsed location. | Adapter retains coverage rounded to 3 decimals but omits counts and structured resolved location. Writer averages four parser confidences, rounded to 2 decimals; no per-skill confidence survives. Most parser fields, including work/projects, are not stored. Lists themselves round-trip as JSON, preserving parsed order/duplicates. |
| Durable rows → snapshot | Separate `raw`, `parsed`, `resolved`, `parser_job`, `ops`, `errors` layers; selected run ID in `parsed`; derived health/result states and numeric scores. | Only one parser result is projected. Historical rows remain in storage. Succeeded jobs require resolvable authority, with no latest-result fallback; legacy/no-authority selection uses timestamp and run-ID tie-break. Drive ID, full error history/details and ops events are not projected. These omissions are read-model choices, not destruction of durable artifacts. |
| Snapshot → API | `GET /snapshot` returns `ReviewerSubmissionSnapshot`; the three skill fields remain strings containing JSON arrays. | API adds no evidence or resolution linkage. Consumers must decode the strings and preserve layer meaning. PDF access is separately mediated through `/resumes/{submission_id}`. |

Persistence nuance: initial parser rows are appended per run; the worker then
updates that run's resolver-owned columns in place. It is inaccurate to describe
the full resolver history as immutable append-only events. There is no separate
resolution-attempt identity, resolution timestamp or per-skill decision log.

Replay nuance: successful probes store `resolver_version="v1"` and
`aliases_version="1.0.0"`, but `parser_version=""`. Neither parser entrypoint
stamps a parser version. No dependency/code hash or alias-map content hash is
recorded. The repo supports reproducing this investigated revision, but a stored
row alone cannot prove which historical code and bytes produced it.

## 3. Concrete traces

The offline probe executes actual PDF extraction, both parser entrypoints,
Resolver V1, both worker persistence functions, snapshot assembly and API model
validation. Drive download and Sheets transport are replaced with synthetic I/O.

For the simple cases both parser entrypoints agree. Below, arrays are shown
decoded for readability. Persisted/API fields contain their JSON serialization.

| Actual source text | Parser value = Resolver input | Resolver result | Persistence → snapshot/API |
| --- | --- | --- | --- |
| Literal one-line `SKILLS: Python` | `[]`, confidence 0 | IDs `[]`, unknowns `[]`, coverage 0 | Parsed and resolved arrays remain empty. Current heading patterns require a standalone heading. The requested example does **not** currently produce Python. |
| `SKILLS:` then newline `Python` | `["python"]`, confidence 1 | IDs `["python"]`, unknowns `[]`, coverage 1 | `parsed.parsed_skills_raw='["python"]'`; `resolved.resolved_skill_ids='["python"]'`; unknowns `'[]'`. |
| `SKILLS` then `Python3` | `["python3"]` | IDs `["python"]`, unknowns `[]`, coverage 1 | Parser observation `python3` and resolver conclusion `python` remain separately inspectable in the same run. |
| `SKILLS` then `Postgres` | `["postgres"]` | IDs `[]`, unknowns `["postgres"]`, coverage 0 | Observation survives both parsed and unknown fields. **No Postgres/PostgreSQL alias is shipped**; no canonical PostgreSQL conclusion can be claimed. |
| `SKILLS` then `QuuxLang` | `["quuxlang"]` | IDs `[]`, unknowns `["quuxlang"]`, coverage 0 | Unknown is inspectable downstream; original capitalization exists only in the source. Successful unknown-only resolution projects `zero_matches` / `empty_success`. |
| `SKILLS / Python / PROJECTS / Built reports using Docker` (slashes here denote newlines) | `["python"]` | IDs `["python"]`, unknowns `[]` | Project narrative never enters skill resolution. `Docker` is neither a resolved skill nor a Resolver unknown. The PDF retains the narrative; no rejected-skill record is generated. |

For the Python example, the persisted aggregate parser confidence is `0.25`:
name, email and location confidences are zero and skill confidence is one.
This is not a probability that the person has Python capability.

Additional normalization/deduplication probe:

```text
SKILLS
Languages: Python (5 years), Python3, QuuxLang, quuxlang

parser / persisted parsed list: [python, python3, quuxlang, quuxlang]
resolver IDs:                 [python]
resolver unknowns:            [quuxlang]
stats: input_count=3, resolved_count=2, unknown_count=1, coverage=2/3
persisted coverage:           0.667
```

`resolved_count` counts matched unique input keys, not canonical IDs. The
parenthetical duration is already gone before Resolver. Deduplication loses
multiplicity in Resolver output, but the persisted parser list retains it.
The mapping can be recomputed with the matching code/map, not recovered from
the one-element canonical list alone.

### Layout/ownership probe: actual worker versus canonical parser

Rendered the five existing `backend/benchmarks/layout_regression/cases.json`
fixtures and passed each through `ParserWorker._run_parser` and `parse_resume_pdf`.

| Fixture | Canonical skill observations | Actual worker observations |
| --- | --- | --- |
| `fragmented_flow` | python, sql | same |
| `wide_skill_start` | python, sql, docker, aws, kubernetes, terraform, fastapi, postgresql, redis, git, github actions | same |
| `ambiguous_columns` | python | same; Docker deliberately excluded by conservative ownership |
| `crossing_lane_start` | python, sql | python |
| `genuine_columns` | python, sql, docker, git, aws | empty |

In `genuine_columns`, an interleaved work heading stops flattened-text skill
capture before Python is reached. Worker persistence and API therefore contain
empty skill lists. The canonical path recovers the owned skill lists and excludes
work/project narrative. Ownership is established in the parser/projection, not by
Resolver. Recognized canonical output is narrower still: this alias map resolves
Python, while SQL/Docker/Git/AWS are unknowns.

## 4. Human review

The current API has no skill-specific correction, rejection, or approval model.
Reviewer routes write workflow `status` and `notes`; initial creation can also
set `tags` and `contact_tracking`. Request models ignore extra fields, so sending
`resolved_skill_ids` does not create a correction. Routes derive the actor from
internal authentication headers; `ops_write_service` dispatches to repository
writers. Current state lives in `ops`, with `updated_at` / `updated_by`.

`append_ops_event_rows` records field, old/new values, actor, timestamp, action
and source on a best-effort basis. Missing optional `ops_events` or append failure
does not block the workflow write. Events have no parser-run or skill association.

The probe uses the real ops service/repository to write `status="reviewed"` and
`notes="Do not rely on Python"`; the parser result stays unchanged and the API
still returns the machine-resolved Python alongside separate human notes.
Thus machine interpretation and reviewer prose remain distinguishable, but
`reviewed` does not mean a particular skill was validated or rejected. A future
consumer cannot turn those notes/tags/statuses into capability judgments safely.

## 5. Reconciliation with the frozen v0.5 PRD

### Release requirements and concrete implications

The PRD makes the existing architecture the spine (§7), separates source,
deterministic derivation, AI interpretation, human takeaway and coordination
(§8), and keeps Reviewer Snapshot distinct from Assisted Understanding (§9).
It calls for one reviewer-initiated, bounded model invocation (§§12–13), a
point-in-time generation receipt (§20), and a small coordination loop (§§17–19).
The reasoning model is explicitly not a database schema (§10).

| Frozen requirement | Finding from the current trace | Smallest implication for v0.5 |
| --- | --- | --- |
| Distinguish supplied, derived, generated and human-authored information (§§6, 8, 9, 28) | Raw form data, parsed observations, resolved IDs and ops state remain separate. PDF wording/context is not preserved in `parsed_skills_raw`. | Keep those labels in model input and the reviewer surface. Identify `python3 → python` as deterministic derivation, not a verbatim résumé claim or verified competence. Store generated interpretation separately; no Resolver/Snapshot redesign is needed. |
| Bounded, purpose-relevant model context; evidence is not instruction (§§12–13, 28) | Snapshot contains contact and operational fields alongside useful evidence. Professional résumé content can be retrieved separately; parser rows omit most narrative. | Build an explicit allowlisted payload in the new feature. Do not serialize the whole snapshot or send the whole PDF indiscriminately. Exclude default-disallowed contact, authentication, storage identifiers and unrelated metadata before invocation; treat evidence content as untrusted data. This is new feature work, not a current capability. |
| Inspect/reconstruct exactly what was sent (§§13, 20, 22, 28) | Current PDF references, parser run IDs and version labels do not freeze the model input. Source bytes and selected snapshot rows can change; parser cleanup is lossy. | Persist the actual bounded model-bound content or a manifest that resolves to exact retained versions, including Organizational Context content/version and the transformations applied. A hash, Drive reference, current snapshot or parser version label alone cannot reconstruct the input. Keep backend correlation metadata outside model-bound evidence where it is not allowed. |
| Durable, point-in-time generations; regeneration preserves history (§§11, 20, 28) | Parser results are machine derivations, with resolver fields filled in place. They are not generation receipts. | Add the narrow receipt contemplated by §20: generation/submission IDs, time/initiator, model/prompt/context versions, bounded input or reconstructable manifest, output and status. Retain prior generations. No generalized provenance graph or immutable rewrite of parser history is necessary. |
| Grounded observations and provisional possibilities; zero is valid (§§5, 14–15, 28) | Canonical IDs lack source excerpts and omit unknowns/context; empty extraction can be a parser miss. Coverage measures alias matching, not competence. | Use relevant supplied evidence alongside labelled derived data. Make the evidence supporting an observation inspectable through the bounded inputs. Do not infer lack of ability from an empty list, treat a canonical ID as competence, or manufacture a possibility. The PRD does not mandate token-level source-span storage. |
| Human takeaway separate from generation; coordination remains human-owned (§§17–19, 28) | Ops notes/status are human-owned, but there is no skill-specific adjudication. | Reuse ops where its semantics suffice and separately scope the minimum takeaway/why/next-action/revisit support. Lack of skill-level approval history is not a v0.5 blocker; generated text must not silently become a takeaway or change workflow. No CapabilityAssociation model is required. |
| Failure preserves deterministic workflow (§§21, 25, 28) | Current deterministic evidence and ops boundaries can remain independent of a new generation. The existing Resolver failure projection has a separately reproduced defect. | Isolate generation failures/status and invalid output; leave evidence, takeaway and workflow unchanged. Triage the current Resolver failure defect separately rather than using its success-like projection as proof that resolution completed. |
| Narrow scope and existing-system protection (§§23–25) | Rich provenance, source spans, complete parser replay metadata and capability associations are absent. | Their absence does not authorize adding them in v0.5. Use a small payload builder and generation receipt for the actual input-audit requirement. Preserve deterministic parser/resolver behavior and existing repository boundaries. |

**Does information loss block the frozen release?** It blocks using a flattened
skill list or a later snapshot as the *sole* evidence/input receipt. It does not
require pre-v0.5 provenance schema changes: the new Assisted Understanding path
can preserve its actual bounded inputs at invocation time, using available form,
professional résumé and labelled derived content. It must record gaps honestly
when source content is unavailable. This preserves what the new operation saw;
it does not retroactively prove the original parser's exact source bytes or
historical interpretation.

The worker's loss of recoverable skills is still a concrete existing-path
correctness problem. Fixing that bounded integration would improve the evidence
available to review, but does not itself satisfy the model-input receipt,
instruction isolation, generation history or coordination release gates.

### Issue's conceptual chain: future direction, not a v0.5 requirement

§24 explicitly excludes capability ontologies, person/relationship/knowledge
graphs, embeddings and semantic contributor search. §§30–32 defer richer
capability representation and retrieval until actual use earns them. The
following inventory answers #387's future-chain question without importing it
into the frozen release scope.

| Future chain component | Existing foothold | Concrete gap for evidence-backed knowledge/retrieval |
| --- | --- | --- |
| Person → Submission | Submission UUID and raw contact/form fields | No person identity/merge semantics; email is not an implemented Person relationship. |
| Submission → Evidence | Submission/job Drive reference; retrievable PDF | No immutable source version/digest or evidence object; availability and historical byte identity are not guaranteed by the result row. |
| Evidence → Extraction | Parser run and normalized skill strings | No source spans, excerpts, section ownership/rejection records or complete extractor version. Worker also bypasses the existing layout operation. |
| Extraction → Resolution | Co-located parsed/resolved lists, unknowns, version labels | No explicit per-observation mapping/decision; replay requires the actual historical implementation and map. |
| Resolution → Capability Association | Submission-level canonical IDs; separate ops layer | No person association, evidence strength, skill-level human judgment, or approval history. |
| Knowledge View / Retrieval | Reviewer snapshot already separates data owners | Selected-run summary is not a provenance graph or proof of capability; missing output cannot establish absence of capability. |

If later work earns a richer capability model, existing artifacts can seed it
as **legacy machine observations**:
use submission/run identity, preserve parsed strings and unknowns, respect job
authority, and retrieve the source when available. Re-extraction should be a new
interpretation with explicit lineage, not a claim that historical source context
was durably recorded. Never treat `resolved_skill_ids`, resolver coverage,
aggregate parser confidence or workflow `reviewed` as sufficient provenance.

## 6. Smallest next action (proposal only)

Proposed follow-up title: **Route durable parser worker through the existing
layout-aware PDF parser**.

Bounded scope for review:

- Make `ParserWorker._run_parser` use existing `parse_resume_pdf(downloaded_bytes)`.
- Verify the real worker path on `genuine_columns`, `crossing_lane_start` and
  narrative exclusion; compare its persisted/API observations to the canonical
  operation, including after re-downloading source bytes.
- Retain retry/run identity, lease checks, parser-before-resolver persistence,
  authority selection and error behavior.
- Do not change Resolver aliases/semantics, ownership rules, Snapshot schemas,
  introduce new domain models, or automatically backfill historical rows.

This is outcome **B**, because useful spatial information already exists and is
unnecessarily discarded before the established ownership operation. Review this
scope separately before implementation. This recommendation is grounded in a
reproduced current-path defect, not an unapproved future capability model.
The v0.5 input receipt belongs to the narrowly scoped Assisted Understanding
feature; richer evidence-level domain relationships and comprehensive historical
parser replay are post-v0.5 possibilities, not frozen release requirements.

Two additional observed limitations should be carried into triage rather than
silently fixed here: unsupported inline headings, and the resolver-failure state
projection failure below. Neither justifies inventing a provenance framework.

## 7. Validation and limits

Run from repository root:

Prerequisite: install `backend/requirements.txt` and
`backend/requirements-dev.txt` in `backend/.venv`. The probe establishes the inert
`GOOGLE_SHEET_ID=offline-skill-lineage-test-sheet` default before importing backend
modules, so no `.env`, Google credentials or live Sheet is required. An existing
environment value is left unchanged; Sheets operations still use synthetic I/O.

```sh
backend/.venv/bin/python docs/architecture/investigate_skill_lineage.py > /tmp/issue-387-traces.json
backend/.venv/bin/python -m pytest backend/tests/test_skill_section_projection.py backend/tests/test_layout_regression_corpus.py backend/tests/test_parser_service.py backend/tests/test_parser_worker.py backend/tests/test_sheets_persistence_boundary.py backend/tests/test_dashboard_parser_results.py backend/tests/test_dashboard_route.py backend/tests/test_ops_write_service.py -q
```

- Probe: **12 cases completed**, checking parsed-list preservation, resolved and
  unknown API round-trip, raw-layer separation, and unchanged parser rows after
  an ops write. Output includes extraction/projection, both parser results,
  Resolver input/output, pre/post-resolver rows, ops events and API representation.
- Review follow-up: **12 cases completed with `GOOGLE_SHEET_ID` unset and dotenv
  loading disabled**, using
  `env -u GOOGLE_SHEET_ID PYTHON_DOTENV_DISABLED=1 backend/.venv/bin/python docs/architecture/investigate_skill_lineage.py`.
  No live Google setup was needed. The unrelated known test failure below was
  not changed by this follow-up.
- Existing focused suite: **105 passed, 1 failed, 10 warnings**. Failure:
  `test_durable_path_preserves_owned_state_and_selects_authority[True]` expects
  `resolver_state='not_run'`, but receives `'zero_matches'`. Reproduced alone
  (**1 failed, 9 warnings**).
- Cause visible in code: parser-only persistence serializes empty resolver lists
  as `'[]'`; `_has_resolver_output` treats any nonblank resolver field as output.
  Thus a Resolver exception can project as zero matches/empty success despite a
  durable `RESOLVER_FAILED` error. The error artifact survives; the success-like
  projection alone is unsafe evidence of completed resolution. Separate triage
  should use the existing regression and preserve parser output/authority.
- This is local synthetic-I/O evidence, not a live Google Sheets/Drive, deployed
  worker, HTTP authentication or frozen-PRD acceptance test. API route and ops
  behavior are additionally covered by the existing focused tests.
- Full-PRD reconciliation is complete against the supplied September 7 frozen
  text. It changes the scope interpretation, not the recorded code trace or test
  results. This documentation-only reconciliation does not validate unimplemented
  v0.5 features or satisfy their release gates.
- The investigation findings have been posted as a comment on
  [#387](https://github.com/The-Chamber-of-Us/libelle/issues/387), satisfying the
  issue-comment deliverable. No follow-up implementation has been performed.
