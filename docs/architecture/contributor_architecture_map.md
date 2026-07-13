# Contributor Architecture Map

Issue #311. Read this first. It explains Libelle's system model — how
volunteer intake data moves through the system, which components own which
state, and what you must not accidentally violate — in one place, so you can
work on individual issues safely without reconstructing the architecture from
old PRs and Slack threads.

Target reading time: ~30 minutes including the linked contracts.

## 1. What Libelle is

Libelle is a trusted volunteer intake and reviewer workflow system for
nonprofit projects. At a high level:

> A volunteer submits interest and optionally a resume → the system preserves
> the raw evidence → the parser and resolver derive structured signals →
> `/snapshot` assembles reviewer-facing records → a reviewer takes ops
> actions → history and errors remain traceable.

The point is not just moving data from a form into a dashboard. The point is
preserving enough context, ownership, and failure visibility that reviewers
can **trust what they are seeing**: where a value came from, whether it is
raw or derived, whether the pipeline partially failed, and who changed
reviewer state.

## 2. Core data flow (current v0.4 system)

```text
Volunteer
  ↓
Public intake form            (frontend/src/components/intake/IntakeForm.tsx)
  ↓
Submission record             (submissions tab — append-only, immutable)
  ↓
Resume upload → Google Drive  (deterministic {submission_id} filename)
  ↓
Parser pipeline               (backend/parser.py, async background task)
  ↓
Parser results                (parser_results tab — append-only per run)
  ↓
Resolver                      (backend/resolver/ — normalizes parser output)
  ↓
Resolved / canonical fields   (resolver-owned columns of parser_results)
  ↓
GET /snapshot                 (backend/services/dashboard_service.py)
  ↓
Reviewer dashboard            (frontend Inbox / ParserResults / Ops / Errors)
  ↓
Ops status / notes            (ops tab, via POST /ops/update)
  ↓
Ops events / errors           (ops_events + errors tabs — append-only)
```

Storage is a 4-tab Google Sheet (`submissions`, `parser_results`, `ops`,
`errors`, plus the optional `ops_events`) defined in
`backend/sheet_schema.py`, with resume files in Google Drive. Startup
validation (`backend/validator.py`) refuses to boot against a sheet whose
tabs or headers drift from the repo-owned schema.

## 3. Direction of travel (future-facing)

The current system is the first half of a longer arc:

```text
Intake → Identity Layer → Document Understanding → Normalization
       → Canonical Representation → Reviewer Workflow → Matching → Audit History
```

A shallow resume tool would go `Resume → extracted JSON → matching`.
Libelle deliberately does not, because matching built directly on raw parser
strings inherits every extraction error invisibly. The intended model is:

> volunteer intent → stable identity → evidence preservation →
> interpretation → reviewer trust → matching

**Matching sits on top of trustworthy records.** If the system cannot explain
where a value came from, whether it is raw or derived, and whether the
pipeline partially failed, matching on it would launder uncertainty into
false confidence. Parser and resolver behavior exists today; a fuller
canonical representation and the matching layer are direction-of-travel —
do not assume they exist when reading issues that mention them.

## 4. Submission identity: `submission_id`

`submission_id` is a UUIDv4 generated at intake. It is the **canonical
internal key** — everything attaches to it:

- the raw `submissions` row
- the Drive resume file (deterministic `{submission_id}` filename)
- every `parser_results` row
- resolver output
- the current `ops` row
- `errors` rows
- `ops_events` history rows
- intake and parser log lines

Names change, emails change, files get renamed. None of them are safe join
keys, and none of them are unique. When composing data across tabs, **join by
`submission_id` only** — `/snapshot` does exactly this and nothing else.

## 5. A submission's lifecycle

Libelle is not one synchronous operation; it is a pipeline whose stages
succeed, fail, or run at different times. Through time:

1. A volunteer submits the public form.
2. The backend generates a `submission_id` and returns it in the API
   response.
3. If a resume is included, the file is uploaded to Drive under the
   deterministic filename, and the outcome (`uploaded`/`failed`/`missing`)
   is finalized.
4. The raw submission row is **appended** to `submissions` — and is now
   immutable.
5. The background parser task runs (carrying the same `submission_id`) and
   **appends** a `parser_results` row.
6. The resolver normalizes the parser output into the resolver-owned columns
   of that row.
7. `GET /snapshot` assembles a reviewer-facing record from whatever sources
   exist right now.
8. A reviewer updates status or notes through the dashboard
   (`POST /ops/update`); `ops` stores the latest reviewer state, and
   `ops_events` appends per-field history when the tab exists.
9. Any stage that degrades appends failure evidence to `errors`.

Because stages are independent, a record can be in many legitimate states:
complete, no resume provided, parser pending, parser failed, resolver failed,
partial success, awaiting reviewer action, reviewed, or broken/contradictory.
This is why the **state contract** exists: each subsystem has its own state
domain (`ResumeState`, `ParserState`, `ResolverState`, `ReviewStatus`), and
the reviewer-facing `SubmissionHealthState` is *derived* from their
composition by `derive_submission_health_state()` in
`backend/core/state_contract.py` — never stored, never guessed by the
frontend. Degraded records stay reviewer-visible; a parser failure is
information, not a reason to hide a volunteer.

## 6. State and ownership model

| Component | Owns |
| --- | --- |
| Intake | Raw volunteer-submitted data (`submissions`, append-only) |
| Drive upload | Resume file reference and upload state |
| Parser | Extracted resume fields (`parser_results`, parser columns) |
| Resolver | Canonical/normalized interpretation (resolver columns) |
| Ops | Reviewer workflow status and notes (`ops`, current state) |
| Errors | Failure evidence (`errors`, append-only) |
| Ops events | Append-only reviewer action history (`ops_events`) |
| `/snapshot` | Derived reviewer read model (never persisted) |

The key lesson: **one subsystem must not silently rewrite another
subsystem's truth.** Parser output never overwrites what the volunteer
typed; resolver output never erases what the parser extracted; reviewer
actions never alter raw, parsed, or resolved values. The exact field-by-field
rules live in the field ownership contract (linked below), with matching
constants in `backend/core/state_contract.py`.

## 7. Parser → resolver → canonical representation

Libelle intentionally separates document extraction from normalization from
(future) matching:

```text
Resume text
  ↓
Parser        — "What does the document literally say?"     (evidence)
  ↓
Resolver      — "What does this mean in normalized terms?"  (interpretation)
  ↓
Canonical     — "What concepts does this map to?"           (future-facing)
  ↓
Matching                                                     (future-facing)
```

Example: a resume says *"Built React dashboards using PostgreSQL."*

- The parser extracts the literal evidence: `React`, `PostgreSQL`
  (`parsed_skills_raw`).
- The resolver normalizes to known skill IDs (`resolved_skill_ids`), keeps
  anything it can't map in `unknown_skills`, and reports
  `resolver_coverage`.
- A future canonical layer could map these to concepts like *frontend
  engineering* or *database-backed application work* for matching against
  opportunity needs.

Parser output is **evidence**, resolver output is **interpretation**, and
canonical representation is what matching should eventually depend on.
Keeping the layers distinct is what lets Libelle preserve uncertainty
(low confidence stays visible, unresolved skills stay listed) and improve
each layer independently.

## 8. Why `/snapshot` exists — and why it is not a database

`/snapshot` is a **derived read model**. It combines submissions, resume
state, parser output, resolver output, ops state, and error summaries into
one reviewer-facing record per submission, each layer labeled by source
(`raw`, `parsed`, `resolved`, `ops`, `errors`) plus the derived
`submission_health_state`.

- Sheets and Drive hold the source records and artifacts.
- Parser/resolver output is derived evidence and interpretation.
- `ops` holds current reviewer workflow state; `ops_events` holds history.
- `errors` holds failure evidence.
- `/snapshot` assembles the current view from those sources — it is the
  system's *current assembled understanding* of a submission, not storage.

Nothing writes `/snapshot` output back to any tab. The dashboard displays
what the backend derived; it does not invent its own trust logic, recompute
health, or reinterpret source boundaries. The assembly rules (which source
wins, what happens when sources conflict or are missing) are specified in
the system-of-record precedence contract linked below.

## 9. Contributor guardrails

Common mistakes that violate the contracts:

- **Do not** join records by email, name, or filename — `submission_id` only.
- **Do not** overwrite raw submitted values with parser/resolver output.
- **Do not** let parser/resolver failures or error rows hide submissions.
- **Do not** duplicate the health-state matrix in the frontend or in the
  snapshot assembler — call `derive_submission_health_state()`.
- **Do not** trust reviewer actor identity from client payloads; the backend
  derives it (`backend/api/internal_actor.py`).
- **Do not** treat `/snapshot` as canonical storage or write it back.
- **Do not** make event history block current reviewer writeback —
  `ops_events` appends are deliberately best-effort.
- **Do not** collapse raw, parsed, resolved, ops, and errors into one
  ambiguous field.
- **Do not** make the UI look cleaner by hiding uncertainty or degraded
  pipeline state — honesty about degradation is a feature.
- **Do not** assume matching can happen directly from raw parser strings
  without normalization and source awareness.

When adding a new field, decide who produces its value and place it with
that owner — the field ownership contract has a decision guide.

## 10. Deeper contracts

- [State transition contract](state_contract.md) — state domains, transition
  validators, the health-state matrix, invariants (#279).
- [Field ownership contract](field_ownership_contract.md) — field-by-field
  ownership for every tab, overwrite rules, where new fields belong (#296).
- [System-of-record precedence](system_of_record_precedence.md) — which
  source wins when sources disagree; `/snapshot` assembly rules (#295).
- [Ops event history](ops_event_history.md) — the append-only `ops_events`
  tab and its best-effort write semantics (#290).
