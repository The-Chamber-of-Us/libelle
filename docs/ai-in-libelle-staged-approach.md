# AI in Libelle: Staged Approach

## Why this note exists
A lot of people hear “AI” and think of one giant category. That is not how we should think about Libelle. For Libelle, different kinds of AI belong at different stages, for different reasons. This note gives contributors a simple shared picture of:

* What belongs in **v0.3**
* What might come in **v0.4** and **v0.5**
* Where ML, NLP, LLMs, OCR, and maybe RL could fit
* What guardrails matter so we do not overcomplicate the system too early

This is not a hard roadmap. It is a practical way of thinking about how AI could fit into Libelle over time.

---

## The Main Idea
Libelle should **earn the right** to use more advanced AI. That means:

1.  First, build a reliable system.
2.  Then, measure how it performs.
3.  Then, add bounded intelligence where it clearly helps.
4.  Keep source-of-truth data inspectable and trustworthy.

In other words, do not start with “how do we add AI?” Start with “what problem are we solving, and what is the safest useful tool for this stage?”

**One more important point:** even in v0.3, offline AI experiments can still matter. The point is not to avoid AI entirely. The point is to make sure experiments feed a measurable improvement loop rather than quietly becoming production truth before the system is ready.

---

## Progression at a Glance

| Phase | Focus | AI Role | Key Examples | Human-in-Loop | Risk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **v0.3** | **Hardening** | Experimental & Learning | Parser benchmarks, Synthetic datasets, OCR pre-processing | **Yes** | Low |
| **v0.4** | **Assistance** | Bounded Support | Resolver suggestions, Reviewer summaries, Anomaly checks | **Yes** | Low-Med |
| **v0.5** | **Intelligence**| Grounded & Integrated | Retrieval, Ranking, Internal maintenance agents | **Yes / Partial** | Medium |

---

## A Simple Way to Think About Libelle
Libelle has a few core layers where different AI methods fit:

* **Intake:** A person fills out a form and may upload a resume.
* **Parsing:** The system tries to extract useful information from text.
* **Resolution:** The system tries to normalize messy values into something more structured (e.g., “React.js” and “reactjs” mapping to `react`).
* **Review:** A human reviewer searches, filters, reads, and updates status.
* **Improvement Loop:** We benchmark, analyze failures, and improve the system over time.

---

## What Belongs in v0.3
v0.3 should stay mostly deterministic, auditable, and easy to debug. Focus includes:
* Stable intake flow and clean schema.
* Append-only records and explicit error logs.
* Parser benchmark harness and **Resolver V1**.
* Clear separation of raw data vs. derived data.

### AI in v0.3 (Mostly Offline/Experimental)
* **Parser Benchmarking:** Synthetic dataset creation and offline NLP tests.
* **Data Rehydration:** OCR experiments on image-based PDFs (outside production path).
* **Signal Analysis:** Analyzing "Unknown" skills to inform the manual alias map.
* **Sandbox R&D:** Exploring reviewer summary ideas in a local environment.

**Not ideal for v0.3:** Black-box automation, fully automated matching, or anything that makes failures harder to explain. 

> **Simple rule for v0.3:** AI can help us learn, but it should not yet be the foundation of trust.

---

## What Likely Belongs in v0.4
By v0.4, if the core system is stable, AI can start helping in bounded ways.

### 1. Resolver Assistance (ML/Embeddings)
When the deterministic resolver cannot map a skill, an embeddings layer suggests the top 3 likely matches.
* **Workflow:** Unknown skill → Model suggests top 3 → Human reviews → Alias map improves.

### 2. Better Parsing Experiments (NLP/LLM)
If benchmark data is strong enough, we compare deterministic parsing to NLP or LLM-assisted extraction to measure precision gains.

### 3. Reviewer Assistance (LLM)
LLM tools generate short summaries, highlighted skills, or “why this person may be relevant” notes to save reviewer time.

### 4. Quality Monitoring (Anomaly Detection)
Using simple ML to identify malformed inputs, weak parser outputs, or spikes in unknown skills.

---

## What Likely Belongs in v0.5
As the data foundation strengthens (Postgres), more ambitious AI becomes realistic.

* **Matching and Ranking:** Surfacing likely volunteers for specific project needs.
* **Grounded LLM Explanations:** Summaries and "reasoning" for why a candidate was ranked.
* **Internal Maintenance Helpers:** Agent-like tools to assist with alias-map updates, failure clustering, and dataset prep.

**Note on Oversight:** In v0.5, features like ranking may become partially automated to handle scale, but high-stakes actions (like final summaries and status changes) remain human-verified.

---

## Terminology Map: Where Tools Fit

* **Machine Learning (ML):** Ranking, anomaly detection, matching, and pattern finding.
* **Natural Language Processing (NLP):** Resume parsing, text extraction, and summarization.
* **Embeddings / Semantic Similarity:** Unknown skill suggestions and fuzzy-but-safe resolver assistance.
* **LLMs / Generative AI:** Bounded use for summaries, explanation layers, and drafting suggestions.
* **OCR:** Primarily for benchmark dataset preparation; not yet ideal for live production intake.
* **Deep Learning:** Possible under the hood for ranking/parsing later; not a goal in itself.
* **Reinforcement Learning (RL):** Possible later for scheduling, retry prioritization, or queue ordering.

---

## Important Guardrails
1.  **Keep source-of-truth data separate:** Raw user data must stay raw.
2.  **Human-in-the-loop beats silent automation:** Suggestions are better than hidden decisions.
3.  **Benchmark before trust:** If we claim a feature is better, we must be able to measure it.
4.  **Simpler beats fancier when the system is young.**
5.  **Reduce burden, don't increase confusion:** AI should make review faster without reducing trust.
6.  **AI is a tool, not a goal:** Measurable benefit to the mission comes first.

---

## How We Judge AI Success

### Parsing and Extraction
* Parser accuracy improves on the benchmark set.
* Extracted fields improve relative to the deterministic baseline.
* OCR pre-processing produces usable text from image-based resumes.

### Resolution and Normalization
* "Unknown" skills decrease over time.
* Resolver suggestions reduce manual cleanup.
* Alias map improvements lead to measurable gains on benchmark data.

### Reviewer Experience
* Reviewer time-to-triage goes down.
* Summaries reduce reading burden without hiding important raw details.
* Explanations make review faster without reducing trust.

### Matching and Ranking
* Surfaced candidates become more relevant (Precision/Recall).
* Search and filtering become more useful without losing interpretability.

---

## What This Means for Volunteers
You don't need to be an AI specialist to help. Bite-sized contributions include:
* Annotate a small batch of resumes for parser benchmarking.
* Analyze "Unknown" skills from benchmark outputs.
* Test OCR on a subset of image-based PDFs.
* Review top-3 resolver suggestions for quality.
* Propose UX improvements for reviewer-facing summaries.

---

## Short Version
* **v0.3:** Deterministic pipeline + benchmarks + trustworthy review flow.
* **v0.4:** Bounded AI assistance for parsing, resolver suggestions, and summaries.
* **v0.5:** Stronger retrieval, ranking, and grounded internal helpers.

**The goal is not to “add AI” for its own sake. The goal is to build a trustworthy system first, then add intelligence in places where it clearly helps and can be measured.**
