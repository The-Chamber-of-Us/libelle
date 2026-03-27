# AI in Libelle: staged approach

## Why this note exists

A lot of people hear “AI” and think of one giant category. That is not how we should think about Libelle.

For Libelle, different kinds of AI belong at different stages, for different reasons. This note gives contributors a simple shared picture of:

* what belongs in v0.3
* what might come in v0.4 and v0.5
* where ML, NLP, LLMs, OCR, and maybe RL could fit
* what guardrails matter so we do not overcomplicate the system too early

This is not a hard roadmap. It is a practical way of thinking about how AI could fit into Libelle over time.

## The main idea

Libelle should earn the right to use more advanced AI.

That means:

* first build a reliable system
* then measure how it performs
* then add bounded intelligence where it clearly helps
* keep source-of-truth data inspectable and trustworthy

In other words, do not start with “how do we add AI?”
Start with “what problem are we solving, and what is the safest useful tool for this stage?”

## Progression at a glance

**Phase: v0.3**
**Focus:** Hardening
**AI role:** Deterministic pipeline plus offline experiments

**Phase: v0.4**
**Focus:** Assistance
**AI role:** Bounded suggestions, resolver assistance, reviewer summaries, quality checks

**Phase: v0.5**
**Focus:** Intelligence
**AI role:** Retrieval, ranking, grounded LLM features, internal agent-like helpers

## A simple way to think about Libelle

Libelle has a few core layers:

### Intake
A person fills out a form and may upload a resume.

### Parsing
The system tries to extract useful information from text.

### Resolution
The system tries to normalize messy values into something more structured.
*Example: “React.js” and “reactjs” may both map to a canonical skill like react.*

### Review
A human reviewer searches, filters, reads, and updates status.

### Improvement loop
We benchmark, analyze failures, and improve the system over time.

Different AI methods fit into different layers.

## What belongs in v0.3

v0.3 should stay mostly deterministic, auditable, and easy to debug.

That means the focus should be on:

* stable intake flow
* clean schema
* append-only records where appropriate
* parser benchmark harness
* Resolver V1
* explicit errors and logs
* reviewer-facing workflow
* clear separation of raw data vs derived data

## What AI should look like in v0.3

Mostly offline, experimental, or assistive.

**Good examples:**
* parser benchmarking
* synthetic dataset creation
* OCR experiments on the side
* analyzing unknown skills
* testing semantic matching ideas offline
* exploring reviewer summary ideas in a sandbox

**Not ideal for v0.3 core product flow:**
* black-box automation replacing source-of-truth logic
* fully automated matching
* broad agent workflows
* anything that makes failures harder to explain

### Simple rule for v0.3
AI can help us learn, but it should not yet be the foundation of trust.

## What likely belongs in v0.4

By v0.4, if the core system is stable, AI can start helping in bounded ways.

### Resolver assistance
When the deterministic resolver cannot map a skill, an ML or embeddings layer could suggest likely matches.
*Example: Unknown skill comes in → model suggests top 3 likely canonical IDs → human reviews → alias map improves*

**Why this is good:**
* high leverage
* low risk
* human stays in control

### Better parsing experiments
If benchmark data is strong enough, we can compare deterministic parsing to NLP or LLM-assisted extraction.

**Why this is good:**
* measurable
* benchmarkable
* still controlled

### Reviewer assistance
LLM or NLP tools could help generate:
* short summaries
* highlighted skills
* “why this person may be relevant” notes

**Why this is good:**
* saves reviewer time
* helps humans without replacing them

### Quality monitoring
We may use ML or simple anomaly detection to identify:
* malformed inputs
* weak parser outputs
* spikes in unknown skills
* strange failure patterns

## What likely belongs in v0.5

By v0.5, if the data foundation is stronger and Postgres is primary or near-primary, more ambitious AI becomes realistic.

### Matching and ranking
Help surface likely volunteers for a project or need.

### Grounded LLM explanations
*Examples: “Why was this person surfaced?” or “Summarize this application for the reviewer.”*

### Internal maintenance helpers
Possible agent-like tools that help with:
* alias-map updates
* benchmark analysis
* failure clustering
* dataset preparation

At that point, AI is no longer just experimental. It becomes part of the product and operations layer.

## Terminology map: where tools fit

### Machine Learning (ML)
Broad category. Most likely useful for:
* ranking
* anomaly detection
* matching
* pattern finding

### Natural Language Processing (NLP)
Useful for:
* resume parsing
* text extraction experiments
* semantic matching
* summarization

### Embeddings / semantic similarity
Very promising for:
* unknown skill suggestion
* fuzzy-but-safe resolver assistance
* similarity search later

### LLMs / Generative AI
Most useful when bounded and grounded.
**Good examples:** reviewer summaries, explanation layers, drafting suggestions, internal maintenance assistance.
**Bad early use:** replacing trustworthy structured logic, silent decision-making with weak traceability.

### OCR
Helpful when PDFs are image-based.
**Good near-term use:** benchmark dataset preparation, side experiments.
*Not yet ideal as part of the live production intake path unless intentionally scoped.*

### Deep Learning
Possible under the hood for parsing or ranking later, but should not be treated as a goal by itself.

### Reinforcement Learning (RL)
Probably not the main early answer for Libelle. RL may fit later for niche optimization problems such as:
* workflow scheduling
* retry prioritization
* queue ordering

Longer term, agent-like or adaptive systems might also help with alias-map maintenance or suggestion workflows, but only after we have stronger benchmark data, reviewed examples, and clear success metrics.

## Important guardrails

1. **Keep source-of-truth data separate:** Raw user-entered data should stay raw. Raw parsed outputs should stay visible. AI-derived outputs should be clearly labeled as derived.
2. **Human-in-the-loop beats silent automation early:** If the system is unsure, suggestions are better than hidden decisions.
3. **Benchmark before trust:** If we claim something is better, we should be able to measure it.
4. **Simpler beats fancier when the system is young:** A clear deterministic system with logs is better than impressive ambiguity.
5. **AI should reduce reviewer burden, not increase confusion:** If an AI feature makes the system harder to understand, it is probably too early.

## How we would judge AI success

Any AI feature should earn its place through measurable outcomes.

**Examples:**
* parser accuracy improves on the benchmark set
* unknown skills decrease over time
* resolver suggestions reduce manual cleanup
* reviewer time-to-triage goes down
* summaries reduce manual reading burden without hiding important raw details
* anomaly detection catches weak inputs or pipeline failures earlier
* matching or ranking helps reviewers find relevant people faster

This matters because “interesting” is not enough. For Libelle, AI should be useful, measurable, and trustworthy.

## What this means for volunteers

Volunteers do not need to be “AI specialists” to contribute to this direction.

Useful contribution areas include:
* parser benchmarking
* synthetic datasets
* OCR preprocessing experiments
* resolver improvement
* alias-map design
* reviewer UX for AI-assisted features
* anomaly detection ideas
* ranking and matching concepts
* backend architecture that keeps AI bounded and auditable

## Short version

The likely progression for Libelle is:
* **v0.3:** deterministic pipeline plus benchmarks plus trustworthy review flow
* **v0.4:** bounded AI assistance for parsing, resolver suggestions, summaries, and quality checks
* **v0.5:** stronger retrieval, ranking, grounded LLM features, and possibly internal agent-like helpers

The goal is not to “add AI” for its own sake. The goal is to build a trustworthy system first, then add intelligence in places where it clearly helps and can be measured.
