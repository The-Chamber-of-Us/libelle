# Libelle

Libelle is an open-source volunteer intake and coordination platform built by The Chamber of Us (TCUS).

It helps mission-driven organizations collect volunteer information, preserve structured records, review candidate skills, and coordinate next steps through an internal dashboard.

Libelle is not just a resume parser. It is an early workflow system for turning volunteer interest into trusted, reviewable, and actionable organizational knowledge.

## Current Status

**Current release:** Libelle v0.3.0, “Trustworthy Volunteer Intake”

Libelle v0.3.0 is complete in protected staging.

v0.3.0 focused on one core problem:

> How can TCUS receive volunteer interest, store it safely, parse useful signals, and give internal reviewers a reliable dashboard for follow-up?

This version supports the full internal review loop: public intake, resume upload, structured storage, parser/resolver output, reviewer dashboard, status/notes writeback, actor attribution, and staging deployment behind Cloudflare Access.

This release is designed for internal TCUS use first. It is not yet a general-purpose public SaaS product or full volunteer marketplace.

Production promotion is intentionally deferred until the v0.4 trusted-intake hardening cycle.

## What Libelle Does Today

Libelle v0.3 supports:

- Public volunteer intake through a web form
- Optional resume upload
- Structured submission storage
- PDF resume text extraction and parsing
- Skill and profile signal resolution
- Internal reviewer dashboard
- Inbox workflow for review status, notes, and follow-up
- Parser Results inspection for understanding raw and resolved extraction output
- Resume access through backend-mediated endpoints
- Basic intake rate limiting and load-smoke testing
- Current-state operational records for reviewer workflow actions

The public intake form remains accessible to volunteers. The internal dashboard is intended to be protected behind Cloudflare Access or an equivalent internal access gate.

## What Libelle Is Becoming

Libelle is being developed as a lightweight workflow engine for small institutions that need more than a form, but less than a heavy enterprise volunteer-management system.

The long-term direction is to help organizations understand:

- who has offered to help
- what skills and interests they bring
- what projects or needs they may fit
- what follow-up has already happened
- what opportunities may emerge later

The goal is not only “match a person to a task today.” The goal is to help an organization remember human potential over time and connect people to meaningful work when the right opportunity appears.

## Repository Structure

```text
libelle/
├── backend/            # FastAPI backend for intake, parsing, resolver, dashboard APIs, Drive/Sheets integration
├── frontend/           # React + Tailwind frontend for public intake and internal dashboard
├── infrastructure/     # Templates for Nginx, Systemd, Cloudflare, and deployment support
├── diagrams/           # System architecture and data-flow diagrams
├── docs/               # Technical guides, release notes, and contributor documentation
└── scripts/            # Utility scripts, smoke tests, and maintenance helpers
```

## Tech Stack

### Backend

- Python 3.11+
- FastAPI / Uvicorn
- Google Sheets API
- Google Drive API
- Resume PDF text extraction
- Parser and resolver modules
- Backend-mediated internal resume access

### Frontend

- React
- TypeScript
- Tailwind CSS
- Vite

### Infrastructure

- Cloudflare Tunnel / Cloudflare Access
- NGINX
- Systemd
- Google Drive / Sheets integration

Pathfinder Node / Raspberry Pi deployment remains part of the broader TCUS infrastructure exploration, but v0.3 is primarily focused on making the volunteer intake and reviewer workflow trustworthy.

## Security and Environment

This is a public repository. No credentials, tokens, or live secrets are stored here.

Production secrets should live outside the repository and outside the web root.

Typical production variables include:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEET_ID`
- `DRIVE_ROOT_FOLDER_ID`
- OAuth-related configuration for Google Drive access
- dashboard/internal access configuration

The public volunteer intake route should remain publicly reachable.

The internal dashboard and dashboard write APIs should be protected through Cloudflare Access or the configured internal access path.

## Auth and Access Model

Libelle uses different access models for different parts of the system.

### Public volunteer intake

The public intake form is intentionally accessible to volunteers.

### Internal dashboard

The reviewer dashboard is an internal tool. In deployed environments, it should be gated by Cloudflare Access or an equivalent access-control mechanism.

Internal write actions, such as status updates and reviewer notes, require a derived internal actor identity.

### Google integration

Libelle uses Google services for storage and operational workflows:

- Google Sheets stores structured submission and workflow records.
- Google Drive stores uploaded resume PDFs.
- Backend services mediate access to these resources.
- The frontend should not call Google Sheets or Drive directly.

## Getting Started: Local Development

### Backend

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel 
pip install -r requirements.txt
uvicorn main:app --reload
```
> Note: if PyMuPDF fails to install on a newer macOS or Python environment, do not fight local C/C++ build tooling first. Check the current dependency guidance in `docs/deployment/staging_deployment.md` or open an issue. The staging environment has successfully used a newer PyMuPDF version where older pins failed to install.

Backend runs at:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

Note: the health endpoint is `/health`, not `/api/health`.

For real end-to-end local testing with Google Drive and Sheets, follow the local Google setup guide in `docs/`.

### Windows virtual environment activation

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

On Windows Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at:

```text
http://localhost:3000
```

## Local Development Notes

Some dashboard write actions require internal actor identity. In deployed environments, that identity is expected to come from Cloudflare Access or the configured internal access layer.

In local development, missing actor identity may cause `401` responses for actions such as:

- workflow status updates
- reviewer notes saves
- other internal ops write actions

If this happens, check the local dashboard auth/testing documentation before assuming the frontend action is broken.

## v0.3 Scope

Libelle v0.3 is focused on trustworthy internal intake operations.

Core v0.3 themes:

- reliable public volunteer intake
- optional resume upload
- safer resume storage and backend-mediated access
- parser and resolver visibility
- internal reviewer workflow
- dashboard tabs for Inbox, Parser Results, Ops, and Errors
- actor-aware ops write behavior
- basic rate limiting
- non-production smoke/load testing
- clearer deployment security assumptions

Out of scope for v0.3:

- public volunteer accounts
- custom login system
- role-based permissions matrix
- full volunteer marketplace behavior
- automated project assignment
- AI-driven autonomous matching
- production-grade observability suite
- broad parser rewrite

## Documentation

Useful docs include:

- Local backend Google setup
- API specification
- AI in Libelle staged approach
- Deployment and infrastructure notes
- Benchmark and parser evaluation notes

See the `docs/` directory for the current documentation set.

## Contributing

We welcome contributions across engineering, design, research, documentation, and operations.

Good contribution areas include:

- improving reviewer dashboard usability
- strengthening parser and resolver benchmarks
- improving local setup documentation
- hardening deployment and access-control documentation
- improving public intake trust and clarity
- creating bounded research spikes for parser or workflow improvements

Please work from a GitHub issue when possible. Libelle is moving through staged releases, so narrow, well-scoped PRs are preferred.

Before making changes to parser behavior, resolver behavior, dashboard data models, auth assumptions, or Google storage structure, please open or claim an issue so the change can be reviewed against the current release scope.

To participate in TCUS operations or request access to live systems, open an issue titled:

```text
Request to join TCUS / Libelle
```

## About TCUS

The Chamber of Us is a 501(c)(3) nonprofit building Pathfinder, an open and ethical standard for aligning people, projects, and capital with a sustainable future.

Libelle is one part of that larger effort: a practical system for helping skilled people contribute to meaningful work through trusted, human-centered coordination.

## License

Libelle is licensed under the GNU Affero General Public License v3.0.

If you run this software as a network service, you must make your modifications available to your users.

## Closing Note

Libelle is an experiment in different ways of working, belonging, and building.

It is also becoming a real internal tool: one that helps TCUS receive volunteer interest, preserve human context, and turn scattered offers of help into coordinated action.

Welcome to the mission.
