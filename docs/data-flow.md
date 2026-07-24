# Libelle Data Flow (v0.1)

This document describes how data moves through the Libelle system from the moment a volunteer submits the form to the moment their information is stored for internal use.

It is intended for:
- Backend developers
- Data contributors / analysts
- Privacy & governance reviewers
- System designers

---

## Core Principle

**Data in Libelle flows in one direction only.**

There is no circular data movement.

This is intentionally designed to:
- Reduce risk
- Prevent leakage
- Simplify debugging
- Maintain a clean audit chain

User
  ↓
API (FastAPI /intake)
  ↓
Google Drive (PDF storage)
  ↓
Google Sheets (base row)
  ↓
Parser (background task)
  ↓
Google Sheets (structured data)

---

## Public Endpoint (Current Reality)

Endpoint:

POST /intake

Payload:
	•	file (PDF only)
	•	No additional form fields yet
	•	No metadata assumed
	•	No tokens on frontend

---

## Step-by-Step Lifecycle

### 1. User submits a PDF file

Validation in main.py checks:
	•	✅ file extension is .pdf
	•	✅ file contains extractable text
	•	✅ content is not empty

If it fails:
400 error → nothing is stored

---

### 2. File is uploaded to Google Drive

Handled by:
drive_sync.upload_pdf()

Returns:
	•	drive_file_id

This happens before any parsing.

---

### 3.  Base row is written to Google Sheets

Handled by:
write_base_row()

Columns populated (current schema):

Column
Purpose
A
Timestamp
J
resume_file_id
K
resume_file_url

This creates the first permanent record.

---

### 4.  Parser job is queued (background task)

Scheduled via:
background_tasks.add_task(_parse_and_update, ...)

Frontend receives only:
{
  "status": "success",
  "submission_id": "abc123",
  "message": "File accepted. Parser job queued."
}

No parsed data is exposed in v0.1.

---

### 5.Parser processes the resume

In _parse_and_update():
parsed = parse_resume(text)

The parser extracts:
	•	name
	•	emails
	•	phones
	•	locations
	•	skills
	•	education
	•	work_experience
	•	project_experience

Each output includes:
	•	value
	•	confidence (0.0 – 1.0)

Raw full text is not stored in the sheet.

---

### 6. Structured data written to Sheet

Handled by:

update_resume_in_sheet()

Written to columns L → AB, including:

Column
Field
L
parser_status
M
parser_confidence_overall
N
parsed_name
O
parsed_name_conf
P
parsed_email
Q
parsed_email_conf
R
parsed_location
S
parsed_location_conf
T
parsed_education
U
parsed_education_conf
V
parsed_skills_json
W
parsed_skills_conf
X
parsed_work_experience_json
Y
parsed_work_experience_conf
Z
parsed_project_experience_json
AA
parsed_project_conf
AB
reserved (raw text placeholder)


The timestamp in column A is also updated.

---

Error Handling Model

Stage
Outcome
Validation fails
Nothing stored
Drive upload fails
Nothing stored
Base sheet write fails
File still stored
Parser fails
Row exists for review
Final sheet update fails
File + base row preserved

There are no silent failures.

Every submission is traceable by Drive ID.


Privacy & Access Model

Surface
Can access
Cannot access
Frontend
success state only
stored files, parsed data
Backend runtime
full pipeline (temp)
long-term secrets
Google Drive
resume PDFs
parsing logic
Google Sheets
structured data
raw PDFs
Contributors
role-based
full dataset

Access requires:
	•	Signed Data Handling Agreement
	•	Explicit permission
	•	Logged access

  Not Yet Implemented (Planned)
	•	Frontend metadata injection (name, location, links)
	•	Consent checkbox logic
	•	Database (Postgres)
	•	Full local / on-device nodes
	•	Encrypted storage
	•	AI-assisted parsing (opt-in)
	•	Matching engine

  Summary

Libelle v0.1 is:
	•	One-directional
	•	Ethical by design
	•	Auditable
	•	Modular
	•	Safe for iteration

It is intentionally minimal and correct — not maximal and fragile.




### 7. Parsed Data is Written to the Sheet

The results of parsing are updated into the **same row** created earlier:

| Sheet Column | Example |
|------|------|
| parsed_name | Jane Doe |
| parsed_email | jane@email.com |
| parsed_skills_json | ["Python", "SQL"] |
| parsed_work_experience_json | [...] |
| parser_confidence_overall | 0.78 |

This row now represents the **full structured snapshot** of that volunteer.

---

### 8. Confirmation is Returned to the User

The frontend receives a simple response:

```json
{
  "status": "success",
  "submission_id": "abc123",
  "message": "Your application has been received"
}
```

No parsed data is returned to the user in v0.1.
All advanced insights remain internal only.

⸻

Error Handling

Libelle is designed to fail gracefully and visibly.

Stage
Failure Outcome
Validation
User receives error, nothing stored
Drive Upload
Submission stops, error logged
Sheet Write
File still stored, status = error
Parser
Record exists, status = needs review

No silent failures. No mystery loss.

Every submission is traceable.

Privacy Model

Surface
Can Access
Can NOT Access
Frontend
Only form fields + success state
Stored files, parsed data
Backend
Everything during processing
Long-term secrets
Drive
Resume PDFs
Parsing logic
Sheet
Structured data
Raw PDF text
Contributors
Limited, role-based
Full unmasked dataset

Access requires:
	•	Signed Data Handling Agreement
	•	Explicit permission
	•	Logged access

Future States (Not Yet Implemented)

Data flow is designed to support:
	•	PostgreSQL instead of Google Sheets
	•	Encrypted file storage
	•	On-device processing in Pathfinder Nodes
	•	AI-assisted inference (opt-in only)
	•	Fully local deployments

These are architectural options, not current practice.
