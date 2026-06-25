# Libelle

Libelle is an open-source, volunteer-powered platform that helps people apply their skills where they matter most. 
Built by **[The Chamber of Us (TCUS)](https://www.thechamberofus.org/)**, it supports ethical collaboration and real-world impact in ways traditional systems often fail to enable.

---

## What Libelle Does
Libelle is designed to:
* **Collect and organize** volunteer information in a secure, structured way.
* **Match skills, interests, and availability** to mission-driven projects.
* **Support transparent, ethical collaboration** using human-centered design.
* **Run on sovereign infrastructure**, including low-cost hardware like Raspberry Pi (Pathfinder Nodes).

---

## Repository Structure
```text
libelle/
├── backend/            # FastAPI backend (Intake, Drive/Sheets integration)
├── frontend/           # Frontend UI (React + Tailwind)
├── infrastructure/     # Templates for Nginx, Systemd, and Cloudflare
├── diagrams/           # System architecture and data flow
├── docs/               # Technical guides and contributor notes
└── scripts/            # Utility scripts for setup and maintenance
```
## Tech Stack

### Backend
* Python 3.11+ (FastAPI / Uvicorn)
* Google Drive & Sheets APIs
* Modular Document Parsing

### Frontend
* React / Tailwind CSS
* Vite (Build tool)

### Infrastructure
* Raspberry Pi (Pathfinder Node v0.1)
* Cloudflare Tunnel & Zero Trust (Secure ingress and route protection)
* NGINX (Reverse proxy & static serving)
* Systemd (Service persistence)

## ⚠️ Security & Environment
This is a public repository. No credentials, tokens, or live secrets are stored here.

### Production Configuration
On a live Pathfinder Node, production secrets are stored securely outside the web root (e.g. `/etc/libelle/libelle.env`). Required variables include:

* **GOOGLE_SERVICE_ACCOUNT_JSON:** Path to the service account JSON file used for Google Sheets access (e.g. org_credentials.json).
* **GOOGLE_SHEET_ID:** The ID of the master volunteer sheet.
* **DRIVE_ROOT_FOLDER_ID:** The ID of the Drive folder for PDF uploads.
* **APP_REDIRECT_URI:** The public OAuth callback (e.g. `https://libelle.io/oauth2callback`).

## Google Auth Model
Libelle utilizes a dual-authentication system to navigate Google's permission constraints:

* **Google Sheets (Service Account):** Used for appending metadata. Configured via a service account credential file referenced by GOOGLE_CREDENTIALS.
* **Google Drive (User OAuth):** Used for PDF uploads to Gmail-owned folders. Requires a `token.json` generated via the backend setup endpoints.

## Setup / Admin Endpoints
In production, these endpoints may be protected upstream by Cloudflare Zero Trust:

* **GET /authorize:** Initiates the Google consent flow.
* **GET /oauth2callback:** Completes the flow and saves the local `token.json`.

## Getting Started (Local Dev)

### 1. Backend Setup
```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
Runs at: http://127.0.0.1:8000
Health Check: http://127.0.0.1:8000/health (Note: Endpoint is NOT /api/health)
For real end-to-end local testing with Drive and Sheets, follow the local Google setup guide before running the backend linked below. 

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Runs at: http://localhost:3000

## Documentation

[Local Backend Google Setup](https://github.com/The-Chamber-of-Us/libelle/blob/main/docs/local-dev-backend-google-setup.md)

[Local Dashboard Write Testing](https://github.com/The-Chamber-of-Us/libelle/blob/main/docs/local-dev-dashboard-writes.md)

[API Specification](https://github.com/The-Chamber-of-Us/libelle/blob/main/docs/api-spec.md)

## Contributing
We welcome contributions across engineering, design, and research!
Ways to contribute:

* Refine the resume parsing logic in /backend.
* Improve the volunteer matching algorithm.
* Harden the infrastructure templates in /infrastructure.
* To access live systems or participate in TCUS operations, please open an issue titled "Request to join TCUS / Libelle" to begin the onboarding process.

## About TCUS
The Chamber of Us is a 501(c)(3) nonprofit building **Pathfinder** — an open, ethical, AI-augmented standard to align people, projects, and capital with a sustainable future.
[Read the Pathfinder White Paper](https://www.thechamberofus.org/pathfinder-white-paper)

## License
Licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. If you run this software as a network service, you must make your modifications available to your users.

*Libelle is an experiment in different ways of working, belonging, and building. Welcome to the mission.*
