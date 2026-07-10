# Libelle Engineering Principles

This document defines the durable engineering standards behind the v0.4 Trusted
Intake work and future Libelle releases. It is a contributor-facing guide for
making architecture and implementation decisions across intake, parser,
resolver, snapshot, reviewer workflow, and audit/error handling.

The goal is practical alignment. These principles explain how Libelle should be
engineered; the companion architecture contracts define the detailed state,
ownership, precedence, and history rules.

## Stewardship posture

Libelle is maintained for The Chamber of Us (TCUS) as civic, volunteer-centered
infrastructure. The system handles records that represent real people, not just
rows in a tool.

Contributors should choose designs that preserve evidence, make state visible,
keep business rules in the backend, and remain operable by a small team.

## Principles

### 1. Traceability over cleverness

Favor systems whose behavior can be inspected, explained, and audited over
systems that are difficult to reason about.

When architectural tradeoffs exist, prefer explicit state, deterministic
behavior, and observable workflows over hidden automation or implicit
assumptions.

Examples:

- Preserve pipeline history instead of rewriting it.
- Prefer explicit state transitions over inferred behavior.
- Make failures visible instead of silently recovering.
- Join records by `submission_id`, not by mutable or ambiguous user fields.

### 2. Evidence first

Raw data, derived data, and reviewer-owned data represent different sources of
truth and must remain separate.

The system should preserve enough information for reviewers and maintainers to
understand:

- what was submitted,
- what was generated,
- what failed,
- and what reviewers changed.

Accordingly:

- Submitted data should not be overwritten by parser output.
- Parser output does not overwrite submitted data.
- Resolver output does not overwrite parser output.
- Reviewer notes remain reviewer-owned.
- Historical and event records should be append-only where practical.
- Derived snapshot data is never treated as canonical storage.

### 3. Failure is part of the system

Distributed systems experience partial failure. A failed upload, parser run,
resolver job, or snapshot generation should not cause a submission to disappear
from reviewer visibility.

Whenever possible, preserve successful work, record failures explicitly, and
continue presenting the submission in an understandable state. Failure should be
represented as data rather than hidden by application logic.

The system should distinguish between different classes of failure. For example,
an image-based or low-text PDF should be classified differently from a parser
section-boundary failure.

### 4. Backend owns business rules

Business logic belongs in the backend.

The backend is responsible for:

- validating state transitions,
- enforcing invariants,
- deriving submission health,
- exposing a consistent read model,
- and deriving actor attribution for protected reviewer writes.

The frontend should display backend-derived state rather than independently
calculating or interpreting pipeline status. This prevents different clients
from implementing conflicting interpretations of the same record.

### 5. Human-centered review

Volunteer records represent real people.

The system should make records understandable, reviewable, and recoverable even
when processing is incomplete.

Valid submissions include:

- complete submissions,
- submissions without resumes,
- partially processed submissions,
- and failed processing attempts.

Reviewer visibility takes precedence over presenting an artificially clean
dashboard. A degraded record should still explain what is known, what is
missing, and which stage owns the current state.

### 6. Governance through architecture

Operational safeguards should be implemented through system design rather than
relying solely on contributor discipline.

Examples include:

- authenticated reviewer access,
- audited resume access,
- append-only historical records,
- explicit ownership of data,
- deterministic state transitions,
- backend-owned write validation,
- and consistent source-of-truth precedence.

The architecture should naturally encourage correct behavior.

### 7. Build for a small team

Libelle intentionally uses lightweight infrastructure. Rather than introducing
unnecessary complexity, the system should compensate with:

- deterministic processing,
- explicit state models,
- append-only history,
- auditability,
- idempotent operations,
- observable failures,
- and narrow, testable contracts.

Simplicity is preferred when it preserves reliability and maintainability.

## Contributor standards

New Libelle work should follow these standards:

1. Define the owner of every new field before writing it.
2. Preserve raw volunteer-submitted data as canonical evidence of what the
   volunteer provided.
3. Store derived parser, resolver, health, and snapshot values separately from
   raw submission data.
4. Validate reviewer workflow state and protected writes in the backend.
5. Represent partial success and failure as explicit state, error rows, or
   stage-specific metadata.
6. Keep no-resume, partially processed, and failed-processing submissions
   visible to reviewers.
7. Prefer idempotent operations for retryable pipeline steps.
8. Add tests for state contracts, ownership rules, and failure behavior when
   changing shared pipeline semantics.
9. Avoid frontend-only interpretations of canonical pipeline state.
10. Keep architecture documents and contract code synchronized when changing
    state, ownership, precedence, or reviewer visibility rules.

## Relationship to architecture contracts

These principles are implemented through Libelle's architecture contracts:

- [State Transition Contract](state_contract.md) defines canonical state models,
  allowed transitions, derived submission health, failure handling, reviewer
  visibility, and system invariants.
- [Field Ownership Contract](field_ownership_contract.md) defines which pipeline
  stage owns each field so raw, parsed, resolved, reviewer-owned, error, and
  snapshot-derived data remain separate.
- [System-of-Record Precedence Rules](system_of_record_precedence.md) define
  which data source wins when raw submission data, parser output, resolver
  output, reviewer ops state, errors, and snapshot assembly disagree or are
  incomplete.
- [Ops Event History](ops_event_history.md) defines the append-only,
  best-effort governance history for reviewer workflow changes.

Future architectural work should follow these principles and extend the existing
contracts rather than introducing competing interpretations of submission state.
