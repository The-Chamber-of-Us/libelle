# Libelle Knowledge Improvement Loop

**Status:** Architecture Principle (Living Document)

**Purpose:** Describe how Libelle improves the quality and
trustworthiness of its understanding over time without losing track of
what changed or why.

------------------------------------------------------------------------

## Why This Exists

Libelle should not improve by making individual components more
sophisticated in isolation.

Instead, Libelle should improve by asking a simple engineering question:

> **Meaning changed. Why?**

Meaning can change because of:

-   changes in source evidence
-   document extraction
-   parser behavior
-   resolver interpretation
-   taxonomy or alias knowledge
-   storage or migration
-   snapshot composition
-   benchmark annotation
-   software defects

The goal is not to immediately determine the answer automatically.

The goal is to preserve enough evidence that contributors can determine
the answer with increasing confidence over time.

------------------------------------------------------------------------

## Core Principle

Libelle intentionally separates different kinds of information.

``` text
Source Evidence
        ↓
Machine Extraction
        ↓
Canonical Interpretation
        ↓
Human Review / Judgment
        ↓
Current Understanding
```

Each layer represents a different kind of meaning.

Improving one layer must not silently rewrite another.

------------------------------------------------------------------------

## What "Meaning" Means

Within Libelle:

-   **Expected meaning** is the interpretation represented by the
    versioned benchmark fixture (golden data).
-   **Observed meaning** is the interpretation produced by a particular
    execution of the Libelle pipeline.
-   A **semantic difference** is the structured difference between those
    two representations.

This definition keeps engineering discussions concrete and measurable.

------------------------------------------------------------------------

## The Knowledge Improvement Loop

``` text
Evidence Fixture
        ↓
Pipeline Execution
        ↓
Observed Meaning
        ↓
Expected Meaning
        ↓
Meaning Changed?
        │
        ├── No
        │      ↓
        │  Preserve regression evidence
        │
        └── Yes
               ↓
        Investigate attribution
               ↓
      Determine appropriate owner
               ↓
      Improve / Correct / Accept
               ↓
       Preserve regression evidence
               ↓
             Repeat
```

------------------------------------------------------------------------

## What "Benchmark" Means

Today, the benchmark is primarily implemented through the Python
benchmarking tooling.

Conceptually:

``` text
Benchmark

=

Evidence Fixtures
+
Expected Meaning
+
Pipeline Execution
+
Comparison
+
Diagnostics
+
Regression Evidence
```

The benchmark should help contributors answer:

-   What evidence was evaluated?
-   What meaning was expected?
-   What meaning was observed?
-   What changed?
-   What should be investigated next?

It should not attempt to automatically determine every root cause.

------------------------------------------------------------------------

## Failure Signals vs. Attribution

Signals are not diagnoses.

Example signal:

``` text
possible_layout_or_section_issue
```

does **not** mean:

``` text
layout reconstruction definitely failed
```

Signals help contributors decide what to inspect.

Libelle should prefer **honest uncertainty over false diagnostic
precision**.

------------------------------------------------------------------------

## Meaning Changed. Why?

``` text
Meaning Changed

↓

Why?

├── Extraction?
├── Layout / Reading Order?
├── Parser?
├── Resolver?
├── Taxonomy?
├── Alias Map?
├── Snapshot?
├── Migration?
├── Benchmark Annotation?
└── Bug?
```

A benchmark mismatch should not automatically be interpreted as a parser
failure.

Likewise, benchmark fixtures themselves may require correction.

------------------------------------------------------------------------

## Domain Ownership

  Layer                         Primary Owner
  ----------------------------- ---------------
  Submitted evidence            Intake
  Extracted evidence            Parser
  Canonical interpretation      Resolver
  Human workflow decisions      Operations
  Reviewer-facing composition   Snapshot
  Expected benchmark meaning    Evaluation

------------------------------------------------------------------------

## Maturity Roadmap

### Today

-   benchmark fixtures
-   golden annotations
-   parser evaluation
-   resolver evaluation
-   TP / FP / FN metrics
-   precision / recall / F1
-   resolver coverage
-   run metadata
-   FN-aware reporting
-   Zero-TP reporting
-   regression artifacts

### Near Term

-   lightweight failure signals
-   low-F1 and total-error prioritization
-   raw-vs-resolved comparison
-   companion diagnostic artifacts
-   stronger regression cases

### Future

-   richer provenance
-   cross-stage semantic comparison
-   storage migration validation
-   interpretation version comparison
-   progressively stronger attribution support

------------------------------------------------------------------------

## Relationship to the Release Roadmap

The release roadmap describes **what Libelle becomes**.

The Knowledge Improvement Loop describes **how Libelle continuously
improves**.

``` text
v0.3  CAPTURE
        ↓
v0.4  TRUST
        ↓
v0.5  PRESERVE
        ↓
v0.6  EXPLAIN
        ↓
v0.7  REMEMBER
        ↓
v0.8  UNDERSTAND
        ↓
v0.9  CONNECT
        ↓
v1.0  MOBILIZE
```

The dependency order is more important than the version numbers.

------------------------------------------------------------------------

## Guiding Principle

The benchmark should not care **where** a fix lands.

It should care whether **meaning became more trustworthy**.

Possible owners include:

-   extraction
-   parser
-   resolver
-   taxonomy
-   alias knowledge
-   migration
-   snapshot composition
-   benchmark annotation

That separation keeps evaluation independent from implementation.

------------------------------------------------------------------------

## Long-Term Vision

Over time, Libelle should increasingly be able to answer:

-   Why does Libelle believe this capability exists?
-   Which evidence supports that interpretation?
-   Which parser and resolver versions produced it?
-   Did a migration preserve the same meaning?
-   Did an alias or taxonomy change alter the interpretation?
-   Which component should engineering investigate next?

The objective is not perfect automation.

The objective is continuous improvement supported by transparent
evidence.

------------------------------------------------------------------------

## One-Sentence Summary

> **The Knowledge Improvement Loop is Libelle's engineering approach for
> detecting when meaning changes, helping contributors understand why,
> improving the appropriate part of the system, and preserving that
> learning as future regression evidence.**
