# Libelle System Architecture

This document describes how Libelle is structured and how its core components work together.
It is focused on software architecture. Hardware and node deployment live in docs/deployment.md.


Libelle is part of the broader **Pathfinder** vision developed by **[The Chamber of Us (TCUS)](https://www.thechamberofus.org).**.
To understand how Libelle is deployed within that framework and how the software connects to physical infrastructure decisions, see:
`docs/deployment.md`

Audience:
- Backend and frontend developers  
- Designers and researchers  
- Technical contributors  
- System thinkers

---

## Engineering Principles

Contributors should start with
[Libelle Engineering Principles](architecture/engineering_principles.md) before
changing intake, parser, resolver, snapshot, reviewer workflow, or audit
behavior.

The engineering principles define durable project standards across v0.4 and
future releases. The state transition contract and related architecture
contracts define the implementation rules.

---

## What is Libelle?

Libelle is a volunteer-intake and skill-mapping platform built by The Chamber of Us (TCUS).

Its purpose is to:

- Capture volunteer applications
- Store structured data safely
- Enable future matching between people and projects
- Support ethical, transparent collaboration

Libelle is **modular by design**, so its parts can evolve independently.

---

## High-Level Overview

At a high level, Libelle consists of four layers:

1. **Frontend** – Collects volunteer input  
2. **Backend API** – Handles processing and logic  
3. **Services layer** – Interfaces with external systems  
4. **Storage layer** – Where data actually lives  

Data moves only in one direction:

---

## Conceptual Data Flow

Libelle follows a one-way data flow designed to minimize risk, simplify debugging, and maintain data integrity.

```text
User Browser
    ↓
Frontend (React / Vite)
    ↓
Backend API (FastAPI)
    ↓
Service Layer (Drive / Sheets / Parser)
    ↓
Storage (Google Drive + Google Sheets)
```

Data never moves *backwards* between components.

The frontend does **not** talk directly to Google APIs.  
The storage systems do **not** initiate requests.  
The backend is the only orchestrator.

This creates a clean, auditable chain of responsibility.

---

## Layer Breakdown

### 1. Frontend Layer (React)

**Location:** `/frontend/`

**Responsibilities:**

- Renders the volunteer intake form
- Accepts resume uploads (PDF)
- Collects structured user input:
  - Name
  - Email
  - Location
  - Interests
  - Availability
  - Experience level
  - Consent
- Submits all data to the backend via `POST /api/upload`

**Important rules:**

- The frontend does NOT store sensitive data permanently
- The frontend does NOT contain API keys or secrets
- The only backend URL it knows is `API_URL`

This layer is treated as **untrusted** from a security perspective.

---

### 2. Backend API Layer (FastAPI)

**Location:** `/backend/app/main.py`  
**Port:** `8000` (internal)  

**Responsibilities:**

- Accepts HTTP requests from the frontend
- Validates input
- Enforces required fields
- Routes data into the service layer
- Returns a clean status message to the user

This is the **brainstem** of Libelle.

It does not:
- Store long-term data
- Render UI
- Expose secrets

It does:
- Control flow
- Handle failures
- Protect the rest of the system

---

### 3. Service Layer

**Location:** `/backend/app/services/`

This is where real work happens.

Current services include:

- `drive_service.py` — uploads and organizes PDFs
- `sheets_service.py` — writes structured data to rows
- `parser_service.py` — extracts meaning from documents

Each service is modular by design.

They can be:
- Upgraded independently
- Replaced later (e.g. moving from Google to Postgres)
- Unit tested in isolation

This is where contributors will spend most of their time.

---

### 4. Storage Layer (Google Drive + Google Sheets)

**Why Google for now?**

Not because it’s best.

But because it is:
- Accessible
- Transparent
- Familiar to non-technical collaborators
- Easy to inspect and export
- Good enough for v1

**What is stored:**

In Google Drive:
- Original PDF resumes (organized by date / batch)

In Google Sheets:
- Structured volunteer data
- Submission ID
- Timestamps
- Workflows and tags
- Future matching status

Later, this may migrate to:

- PostgreSQL
- On-device database (Pathfinder Node)
- Encrypted decentralized storage

But that is a **phase 2 decision**.

---

## Request Lifecycle (Chronological)

When a volunteer submits their form:

1. Frontend validates required fields
2. User hits submit
3. Browser sends `multipart/form-data` to `/api/upload`
4. FastAPI accepts the file + form fields
5. PDF is uploaded to Google Drive
6. A new row is created in Google Sheets
7. Resume is parsed for structured data
8. Structured data is appended to the same row
9. Frontend receives confirmation message

If something fails mid-process:

- The error is logged
- The user receives a useful message
- No partial corruption occurs

This is intentional.

---

## Modularity Guarantees

Libelle is designed so that:

- The frontend could be replaced entirely
- The backend could move to a new server
- Google could be swapped for Postgres
- Parsing could use AI or rule-based logic

And the system would **still work structurally**.

This is critical for:

- Longevity
- Open-source contribution
- Ethical control
- Disaster recovery

---

## What This Document Does NOT Cover

This document intentionally excludes:

- Raspberry Pi setup
- systemd configuration
- Cloudflare tunnels
- SSH / Tailscale setup
- Physical node networking

Those belong in:

`docs/deployment.md`  
and  
`libelle-infra-private/`

This separation is part of the security model.

---

## Visual Summary (Mental Model)

Think of Libelle like this:

**Frontend = The Skin**  
**Backend = The Brainstem**  
**Services = The Organs**  
**Storage = The Memory**  
**Deployment = The Skeleton**

Each can grow or be replaced without killing the organism.

That is the design goal.
