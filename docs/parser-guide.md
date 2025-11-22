# Libelle Parser Guide

> Version: v0.1 (Rule-based parser, zero external AI dependencies)
> Status: Active development
> Last updated: 2025-11-22


## Known Limitations (v0.1)

- Limited support for non-English resumes
- Reduced accuracy on creative / non-standard formats (e.g. design resumes)
- Phone/location extraction is basic and region-biased
- No timeline normalization (dates not yet standardized)
- No cross-field consistency reconciliation (e.g. name vs email check)

These are known, accepted trade-offs for the MVP.

---

This document explains how Libelle’s resume parser works today, how it is evolving, and how you can safely contribute to improving it.

Audience:
- Python developers
- Backend contributors
- AI / NLP contributors
- Data & QA contributors
- System designers working on Pathfinder / Sentinel

---

## Purpose of the Parser

The Libelle parser turns unstructured resume data into structured, analyzable fields.

Its goals are:
- Extract meaningful data from uploaded resumes
- Normalize inconsistent formats
- Support future categorization, inference, and matching between people and projects 
- Provide internal confidence scoring for data quality
- Support human review and correction

The parser is not a hiring decision engine.
It is an interpretation and structuring tool.

Accuracy and ethics matter more than speed.

---

## Data Sources for Development

The parser is currently tested using:

- A small internal test corpus (hand-curated resumes)
- Live beta submissions when available

A larger legacy dataset is available and may be integrated.

Access to data requires signing the **Libelle Data Handling Agreement**.

## Current Inputs

The parser accepts:

- PDF resumes (primary input)
- Optional metadata from the frontend:
  - name
  - email
  - location
  - interests
  - experience level

PDFs are received via the `/api/upload` endpoint and passed into the parser through the service layer.

---

## Current Parser Outputs (v0.1)

The Libelle parser currently produces structured JSON for the following fields.

Each field includes:
- `value` — the extracted data
- `confidence` — a score between 0.0 and 1.0

| Field | Description | Example Value |
|------|------------|------|
| `name` | Full name (best guess) | `"Jane Doe"` |
| `emails` | One or more detected emails | `["jane@email.com"]` |
| `phones` | Detected phone numbers | `["+13125551212"]` |
| `locations` | City / region mentions | `["Chicago, IL"]` |
| `skills` | Extracted skill keywords | `["Python", "Data Analysis"]` |
| `education` | Schools / degrees | `["BS Computer Science - MIT"]` |
| `work_experience` | Roles, companies, durations | `["Software Engineer at X (2020–2023)"]` |
| `project_experience` | Notable projects | `["Libelle intake system"]` |

Example structure:

```json
{
  "skills": {
    "value": ["Python", "FastAPI", "SQL"],
    "confidence": 0.78
  }
}
```

Each field returns:

```text
{
  "value": "...",
  "confidence": 0.0 – 1.0
}
```

An additional **overall_confidence** score will be derived in a future version as an aggregate of key field confidences.

⚠️ In v0.1, this data is only stored internally and is not returned to the frontend.


---

## Relation to Storage Schema (Google Sheets)

Each parsed field maps to a column pair in the Libelle data sheet:

| Parser Output | Sheet Column | Sheet Confidence Column |
|------|------|------|
| `name.value` | `parsed_name` | `parsed_name_conf` |
| `emails.value` | `parsed_email` | `parsed_email_conf` |
| `locations.value` | `parsed_location` | `parsed_location_conf` |
| `skills.value` | `parsed_skills_json` | `parsed_skills_conf` |
| `education.value` | `parsed_education` | `parsed_education_conf` |
| `work_experience.value` | `parsed_work_experience_json` | `parsed_work_experience_conf` |
| `project_experience.value` | `parsed_project_experience_json` | `parsed_project_experience_conf` |

Phone fields are currently extracted but not yet written to the Sheet in v0.1 
| `phones.value` | `parsed_phones` | `parsed_phones_conf` |

---

## Parsing Approach (Current State)

Libelle currently uses a **hybrid rule-based approach**, which may include:

- PDF-to-text extraction
- Regular expressions (regex)
- Keyword scanning
- Pattern matching
- Section detection (e.g. “EDUCATION”, “EXPERIENCE”)
- Heuristic confidence scoring

No external AI model is required to run the current parser.

This is deliberate:
- Enables offline use
- Improves transparency
- Avoids dependency risk
- Keeps costs low

Future versions may experiment with LLM-assisted parsing, but the rule-based core will remain.

---

## File Structure

Parser-related code is located in:

```
/backend/app/services/
  ├── parser_service.py
  ├── pdf_utils.py
  ├── regex_patterns.py
  ├── text_cleaner.py
```

If you are improving parsing logic, you will most likely be editing:

- `parser_service.py` → main logic
- `regex_patterns.py` → detection rules
- `text_cleaner.py` → normalization

---

## How Confidence Is Calculated

Each field’s confidence score is based on:

- Match strength
- Context detection
- Redundancy
- Pattern reliability

For v0.1, this is a heuristic system (not ML).

Example:

```text
- Direct email regex match = high confidence
- Capitalized two-word string near top = medium confidence for name
- Skills repeated in multiple sections = higher confidence
```

These heuristics are intentionally **transparent and editable**.

---

## Local Testing

You are encouraged to test the parser locally using:

✅ Your own resume  
✅ Sample/resume templates  
✅ The `/test_data` folder (if provided)

You should **not** use:

❌ Other people’s resumes  
❌ Real submissions without express permission  
❌ Anything scraped or unclear in origin  

---

## Ethics & Data Handling

All contributors must sign the **Libelle Data Handling Agreement** before accessing any internal dataset.

This protects:
- The applicant
- You
- The organization
- The mission

Key principles:

- Consent-first
- Minimal exposure
- No redistribution
- No training external models on raw data

When in doubt, ask.

---

## How to Contribute

Some high-impact contribution ideas:

- Improve skill extraction accuracy
- Reduce false positives in name detection
- Improve education parsing
- Handle international formats
- Add new confidence heuristics
- Add unit tests for edge cases

Start here:
- Look for TODOs in parser files
- Check GitHub Issues with the `parser` label
- Ask in the **#libelle-parser-pod** channel

We welcome first-time contributors.

---

## The Bigger Picture

Libelle’s parser is not just a technical tool.

It is part of a larger effort to:
- Respect people’s stories
- See them more clearly
- Connect them more intentionally
- Remove bias and opacity from systems

You’re not just writing code.

You’re shaping how people are seen.

Welcome to the work.
