# Libelle

Libelle is an open-source, volunteer-powered platform that helps people apply their skills where they matter most.  
Built by The Chamber of Us (TCUS), it supports ethical collaboration and real-world impact in ways traditional systems often fail to enable.

---

## What Libelle Does

Libelle is designed to:

- Collect and organize volunteer and contributor information in a secure, structured way
- Match people’s skills, interests, and availability to real-world, mission-driven projects
- Support transparent, ethical, and human-centered collaboration
- Run on lightweight, sovereign infrastructure, including low-cost hardware like Raspberry Pi

This repository is the **public monorepo** for Libelle. It contains the application code, architecture, and documentation needed to run, extend, and contribute to the platform.

Sensitive credentials and production secrets are not stored here.

---

## Repository Structure

```text
libelle/
├── backend/              # FastAPI backend for intake, parsing, and data handling
├── frontend/             # Frontend UI (React)
├── infrastructure/        # Example configs (templates only, no secrets)
│   ├── nginx/
│   ├── systemd/
│   └── cloudflare/
├── diagrams/             # Architecture and flow diagrams
├── docs/                 # Guides, system design, and contributor notes
├── scripts/              # Utility scripts for setup and maintenance
├── .gitignore
└── README.md
```
## Tech Stack

**Backend**
- Python 3.11+
- FastAPI
- Uvicorn
- Google Drive + Sheets APIs
- Modular resume / document parsing

**Frontend**
- React
- Tailwind
- Form + file upload handling

**Infrastructure**
- Raspberry Pi (Pathfinder Node)
- Cloudflare Tunnel (public ingress)
- Tailscale (secure admin access)
- NGINX (reverse proxy)
- systemd (service management)

---

## ⚠️ Security Model

This is a public repository by design. Therefore:

- No credentials are committed here
- No API keys or tokens are stored here
- All examples in `/infrastructure` are templates only
- Production configuration lives in a **private infrastructure repo**

If you are deploying to a server or Pi, you must create:
 ```bash
/etc/libelle/libelle.env
  ```
- And pass sensitive values there, including:
```bash
GOOGLE_SERVICE_ACCOUNT_JSON=...
GOOGLE_SHEET_ID=...
DRIVE_ROOT_FOLDER_ID=...
```
---

## Getting Started (Local Dev)

### Backend Google setup (required for real end-to-end testing)

Libelle uses:
- Drive OAuth (via `/authorize` → creates `token.json`)
- Sheets Service Account (share your test sheet with the service account email)

Follow the step-by-step guide here:
- [`docs/local-dev-backend-google-setup.md`](https://github.com/The-Chamber-of-Us/libelle/blob/main/docs/local-dev-backend-google-setup.md)

Then copy:
- `backend/.env.example` → `backend/.env`
and fill in your own IDs and local credential filenames (never commit secrets).

**Backend**
```bash
cd backend
cp .env.example .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
- Runs at: http://127.0.0.1:8000

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
- Runs at: http://localhost:3000

### Frontend ↔ Backend API routing (no env vars)

For the MVP, the frontend should call relative endpoints:
- `/api/upload`
- `/api/health`

Local dev uses a Vite proxy (`/api` → `http://127.0.0.1:8000`).

Production uses NGINX to proxy `/api/*` to the FastAPI service on the Pi.

## Production Deployment (Summary)

On the Pathfinder Node (Raspberry Pi):
- Backend runs as a systemd service
- Frontend is served via NGINX
- Cloudflare Tunnel exposes HTTPS
- Tailscale provides secure SSH

Example service file lives in:
 ```text
/libelle/infrastructure/systemd/libelle-backend.service.template
 ```
Do not copy secrets into the repo.

## Contributing

Libelle is built by volunteers across engineering, design, data, and research.

Ways to contribute:
- Improve the parsing logic
- Expand the matching algorithm
- Refine UX flows
- Improve documentation
- Add new modules

Start by exploring:
- /backend
- /docs
- /diagrams
- GitHub Issues

General contributions via GitHub Issues and Pull Requests are welcome.

To participate in TCUS’s operational network or access live systems and data, you must first join **The Chamber of Us** as a volunteer.

---

### About TCUS

**[The Chamber of Us](https://www.thechamberofus.org)** is a 501(c)(3) nonprofit technology organization building **Pathfinder** — an open, ethical, AI-augmented standard to help align people, projects, and capital with a sustainable future (SSP1).

We build open-source tools that enable effective, data-driven, and ethical global coordination.

Read the [Pathfinder White Paper](https://www.thechamberofus.org/pathfinder-white-paper)

---

### How to Join TCUS / Libelle

Request access by opening a GitHub issue titled:

**`Request to join TCUS / Libelle`**

Once approved, you will receive:

- A TCUS volunteer agreement
- Access to our internal Slack workspace
- Contributor onboarding instructions

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

You are free to use, modify, and distribute this software under the terms of that license.

If you run this software as a network service, you must make any modifications to the source
code available to users of that service.

---

## A Final Note

Libelle is not just a piece of software.

It is an experiment in:
- Different ways of working
- Different ways of belonging
- Different ways of building systems

If you’re here, you’re part of that experiment.

**Welcome.**


