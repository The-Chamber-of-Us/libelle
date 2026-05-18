# AI in Libelle: Staged Approach

## Why this note exists

A lot of people hear “AI” and think of one giant category. That is not how we should think about Libelle. For Libelle, different kinds of AI belong at different stages, for different reasons.

This note gives contributors a simple shared picture of:

- What belongs in **v0.3**
- What might come in **v0.4** and **v0.5**
- Where ML, NLP, LLMs, SLMs, OCR, and maybe RL could fit
- What guardrails matter so we do not overcomplicate the system too early

This is not a hard roadmap. It is a practical way of thinking about how AI could fit into Libelle over time.

---

## The Main Idea

Libelle should **earn the right** to use more advanced AI.

That means:

1. First, build a reliable system.
2. Then, measure how it performs.
3. Then, add bounded intelligence where it clearly helps.
4. Keep source-of-truth data inspectable and trustworthy.

In other words, do not start with “how do we add AI?”

Start with:

> What problem are we solving, and what is the safest useful tool for this stage?

One more important point: even in v0.3, offline AI experiments can still matter. The point is not to avoid AI entirely. The point is to make sure experiments feed a measurable improvement loop rather than quietly becoming production truth before the system is ready.

---

## Core Architecture Principle: Deterministic Spine, Non-Writable Intelligence

Libelle should separate the system that writes truth from the systems that interpret, suggest, or summarize.

The core pipeline should remain a deterministic spine:

```text
Submission + resume
→ parser
→ shared text cleanup
→ resolver / alias map
→ canonical outputs, unknowns, and coverage
→ reviewer snapshot
→ human workflow state
```
This spine is the only path that writes persistent state through explicit backend contracts.

AI systems, including SLMs, LLMs, embeddings, clustering, or ranking tools, should operate as non-writable intelligence layers unless explicitly gated. They may produce:

- reviewer summary drafts
- role-fit suggestions
- alias suggestions
- anomaly flags
- benchmark case drafts
- clustering outputs

But they should not silently overwrite:

- raw submissions
- parser results
- resolver outputs
- workflow status
- reviewer notes
- benchmark truth

Core invariant:

> **No probabilistic system may modify persistent state without an explicit deterministic or human gate.**

In short:

> **Deterministic services and authenticated humans can write state. AI can suggest, annotate, and evaluate.**

---

## Progression at a Glance

| Phase | Focus | AI Role | Key Examples | Human-in-Loop | Risk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **v0.3** | **Hardening** | Experimental & Learning | Parser benchmarks, synthetic datasets, OCR pre-processing | **Yes** | Low |
| **v0.4** | **Assistance** | Bounded Support | Resolver suggestions, reviewer summaries, anomaly checks | **Yes** | Low-Med |
| **v0.5** | **Intelligence** | Grounded & Integrated | Retrieval, ranking, internal maintenance agents | **Yes / Partial** | Medium |

---

## A Simple Way to Think About Libelle

Libelle has a few core layers where different AI methods fit:

- **Intake:** A person fills out a form and may upload a resume.
- **Parsing:** The system tries to extract useful information from text.
- **Resolution:** The system tries to normalize messy values into something more structured, such as “React.js” and “reactjs” mapping to `react`.
- **Review:** A human reviewer searches, filters, reads, and updates status.
- **Improvement Loop:** We benchmark, analyze failures, and improve the system over time.

---

## What Belongs in v0.3

v0.3 should stay mostly deterministic, auditable, and easy to debug.

Focus includes:

- Stable intake flow and clean schema.
- Append-only records and explicit error logs.
- Parser benchmark harness and **Resolver V1**.
- Clear separation of raw data vs. derived data.
- Reviewer workflow surfaces that make system state inspectable.

### AI in v0.3: Mostly Offline / Experimental

Good uses:

- **Parser Benchmarking:** Synthetic dataset creation and offline NLP tests.
- **Data Rehydration:** OCR experiments on image-based PDFs outside the production path.
- **Signal Analysis:** Analyzing unknown skills to inform the manual alias map.
- **Sandbox R&D:** Exploring reviewer summary ideas in a local or experimental environment.

Not ideal for v0.3:

- Black-box automation.
- Fully automated matching.
- Silent AI-written workflow state.
- Anything that makes failures harder to explain.

Simple rule for v0.3:

> AI can help us learn, but it should not yet be the foundation of trust.

---

## What Likely Belongs in v0.4

By v0.4, if the core system is stable, AI can start helping in bounded ways.

### 1. Resolver Assistance: ML / Embeddings

When the deterministic resolver cannot map a skill, an embeddings layer could suggest the top likely matches.

Example workflow:

```text
Unknown skill
→ model suggests top 3 likely matches
→ human reviews
→ alias map improves
```
The model suggests. The resolver and human review process decide what becomes durable.

### 2. Better Parsing Experiments: NLP / LLM / SLM

If benchmark data is strong enough, we can compare deterministic parsing against NLP, LLM, or SLM-assisted extraction to measure whether precision or recall improves.

The goal is not to replace the deterministic parser by default.

The goal is to ask:

> Does the intelligent method measurably outperform the baseline without reducing trust or debuggability?

### 3. Reviewer Assistance: LLM / SLM

AI tools may generate short summaries, highlighted skills, or “why this person may be relevant” notes to save reviewer time.

These should remain advisory. A reviewer should always be able to inspect the raw submission, parsed output, and resolved output separately.

### 4. Quality Monitoring: Anomaly Detection

Simple ML may help identify:

- malformed inputs
- weak parser outputs
- spikes in unknown skills
- suspicious resolver coverage changes
- benchmark regressions

These are flags, not final decisions.

---

## What Likely Belongs in v0.5

As the data foundation strengthens, more ambitious AI becomes realistic.

Possible areas:

- **Matching and Ranking:** Surfacing likely volunteers for specific project needs.
- **Grounded Explanations:** Summaries and explanations for why a candidate was ranked or suggested.
- **Internal Maintenance Helpers:** Agent-like tools to assist with alias-map updates, failure clustering, and dataset prep.
- **Knowledge Retrieval:** Connecting reviewer decisions to project needs, role definitions, or prior contribution patterns.

### Note on Oversight

In v0.5, features like ranking may become partially automated to handle scale, but high-stakes actions should remain human-verified.

Examples of high-stakes actions:

- final reviewer notes
- status changes
- role recommendations that affect outreach
- canonical data updates
- alias-map changes

---

## Terminology Map: Where Tools Fit

- **Machine Learning (ML):** Ranking, anomaly detection, matching, and pattern finding.
- **Natural Language Processing (NLP):** Resume parsing, text extraction, and summarization.
- **Embeddings / Semantic Similarity:** Unknown skill suggestions and fuzzy-but-safe resolver assistance.
- **SLMs / Small Language Models:** Local or narrow models for summaries, role-fit suggestions, unknown-skill clustering, and benchmark assistance.
- **LLMs / Generative AI:** Bounded use for summaries, explanation layers, drafting suggestions, and structured analysis.
- **OCR:** Primarily for benchmark dataset preparation or image-based resume experiments; not yet ideal for live production intake.
- **Deep Learning:** Possible under the hood for ranking or parsing later; not a goal in itself.
- **Reinforcement Learning (RL):** Possible much later for scheduling, retry prioritization, or queue ordering, but not relevant to v0.3.

---

## Important Guardrails

1. **Keep source-of-truth data separate.** Raw user data must stay raw.
2. **Separate state from interpretation.** AI outputs may inform review, but they should not silently become system-of-record data.
3. **Human-in-the-loop beats silent automation.** Suggestions are better than hidden decisions.
4. **Benchmark before trust.** If we claim a feature is better, we must be able to measure it.
5. **Simpler beats fancier when the system is young.**
6. **Reduce burden, do not increase confusion.** AI should make review faster without reducing trust.
7. **AI is a tool, not a goal.** Measurable benefit to the mission comes first.
8. **Model outputs must be attributable.** If an AI-generated suggestion is stored, it should be tied to model/version/context where practical.
9. **Do not let AI create a second truth.** There should be one canonical system state, with AI suggestions clearly marked as suggestions.

---

## How We Judge AI Success

### Parsing and Extraction

AI helps only if:

- parser accuracy improves on benchmark data
- extracted fields improve relative to the deterministic baseline
- failure modes remain explainable
- OCR pre-processing produces usable text from image-based resumes
- improvements are reproducible across benchmark runs

### Resolution and Normalization

AI helps only if:

- unknown skills decrease over time
- resolver suggestions reduce manual cleanup
- alias-map improvements lead to measurable gains
- canonical mappings remain deterministic and reviewable
- resolver coverage improves without hiding uncertainty

### Reviewer Experience

AI helps only if:

- reviewer time-to-triage goes down
- summaries reduce reading burden without hiding important raw details
- explanations make review faster without reducing trust
- reviewers can still inspect raw, parsed, resolved, workflow, and error layers separately

### Matching and Ranking

AI helps only if:

- surfaced candidates become more relevant
- precision and recall improve
- ranking remains interpretable
- reviewer judgment is supported, not bypassed
- the system can explain why a candidate was surfaced

---

## What This Means for Volunteers

You do not need to be an AI specialist to help.

Useful contributions include:

- Annotate a small batch of resumes for parser benchmarking.
- Analyze unknown skills from benchmark outputs.
- Test OCR on a subset of image-based PDFs.
- Review top resolver suggestions for quality.
- Propose UX improvements for reviewer-facing summaries.
- Create synthetic benchmark cases.
- Compare parser outputs against gold labels.
- Help document where AI suggestions should remain non-authoritative.

The most important contribution is not “adding AI.”

The most important contribution is making Libelle more trustworthy, measurable, and useful.

---

## Short Version

- **v0.3:** Deterministic pipeline + benchmarks + trustworthy review flow.
- **v0.4:** Bounded AI assistance for parsing, resolver suggestions, summaries, and anomaly checks.
- **v0.5:** Stronger retrieval, ranking, and grounded internal helpers.

The goal is not to “add AI” for its own sake.

The goal is to build a trustworthy deterministic coordination system first, then add intelligence in places where it clearly helps, can be measured, and does not compromise the system of record.
