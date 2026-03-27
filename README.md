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
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm start
```

---

## Contributing

We welcome contributions from developers, designers, and organizers!
- **Bug Reports & Feature Requests:** Please open an [Issue](https://github.com/The-Chamber-of-Us/libelle/issues).
- **Pull Requests:** Small, focused PRs are preferred. Please ensure your code follows the existing style and includes comments where necessary.
- **Discussion:** Join our community efforts via [The Chamber of Us](https://thechamberofus.com).

---

## License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.