# Libelle Backend: Local Setup Guide

## Overview
Libelle is the volunteer intake and processing backend for The Chamber of Us. This local setup guide helps you run the backend on your own machine and test the end-to-end intake flow.

*(For API contract details and routing rules, refer to `docs/api-spec.md`).*

Since Libelle is an early-stage MVP, we use Google Drive and Google Sheets as our primary infrastructure. That gives us fast iteration, clear auditability, and a "low-code database" that non-technical teammates can view and work with. 

This guide focuses on getting local end-to-end testing working safely.

---

## The Architecture
When you trigger the intake flow locally, the backend coordinates three actions:

1. **Application Intake:** Accepts volunteer form fields and an optional PDF resume upload.
2. **Storage and Logging:** Uploads the PDF resume to Google Drive, then creates a row in a Google Sheet linking the form submission to the uploaded file.
3. **Parsing:** Runs a background task to extract key resume signals and writes parsed output back into the sheet.

### Important Auth Model
Libelle uses two separate Google auth patterns:
* **Google Drive:** Uses OAuth user consent (bootstrapped by the operator CLI) to create `token.json`.
* **Google Sheets:** Uses a service account credential file. This does not use Drive OAuth.

---

## Part 1: Setting Up Your Google Infrastructure
Before touching the code, you’ll set up your **Database** (a Google Sheet) and your **Storage** (Google Drive). We’ll do everything inside **your own Google account** for now (easy + safe).

### 1) Create Your “Storage” Folder (Google Drive)
The backend needs a destination folder to save uploaded PDF resumes.

1. Open Google Drive.
2. Create a new folder named something like: `Libelle-Dev-Uploads`
3. Open the folder and copy the **Folder ID** from the URL.

*(Example URL: `https://drive.google.com/drive/folders/1SAlMmdunKexPvD-HTlfCR3aZvOyBzcuY?dmr=1...`)*
* The **Folder ID** is the part after `/folders/` and before the `?`: `1SAlMmdunKexPvD-HTlfCR3aZvOyBzcuY`

Hold on to your **Folder ID** — you’ll paste it into your `.env` file later as `DRIVE_ROOT_FOLDER_ID`.

### 2) Create Your “Database” (Google Sheet)
To avoid header/column mismatch issues, start from our template.

1. Open the [Libelle Template Folder](https://drive.google.com/drive/folders/1YSqZOb0_djpbXIrJ23oIOlpDT4sucmD4?dmr=1&ec=wgc-drive-globalnav-goto).
2. Right-click the Template Sheet → **Make a copy** (into your own Drive).
3. Open your copied sheet and copy the **Sheet ID** from the URL.

*(Example URL: `https://docs.google.com/spreadsheets/d/1gJXay7VH0-VDkXRy_qK0e3jHHjdJgkrpuVr-xBV-tMw/edit...`)*
* The **Sheet ID** is the part after `/d/` and before `/edit`: `1gJXay7VH0-VDkXRy_qK0e3jHHjdJgkrpuVr-xBV-tMw`

Hold on to your **Sheet ID** — you’ll paste it into your `.env` file later as `GOOGLE_SHEET_ID`.
* **Confirm the tab name** at the bottom is exactly: `applicantsInfo` (Case-sensitive).

### 3) Google Cloud Project & APIs
1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (example: `libelle-local-dev`).
3. Enable APIs:
   * Google Drive API
   * Google Sheets API

### 4A) Create OAuth Client ID (Drive)
1. Navigate to APIs & Services → Credentials → **Create Credentials** → OAuth client ID.
2. Application type: **Web application**.
3. **CRITICAL STEP:** Add Authorized Redirect URI: `http://127.0.0.1:8765/oauth2callback`
   *(Warning: If this does not exactly match, the consent flow will fail).*
4. Download the JSON and rename it to: `org_oauth_client.json`

### 4B) Create Service Account + Key (Sheets)
1. Navigate to IAM & Admin → Service Accounts → **Create Service Account**.
2. Create a JSON key for it (Keys → Add Key → Create new key → JSON).
3. Download the JSON and rename it to: `org_credentials.json`
4. Copy the service account email (ends in `...gserviceaccount.com`).

### 5) Share your sheet with the Service Account (Required)
1. Open your copied Google Sheet template.
2. Click Share.
3. Add the service account email as **Editor**.
*(If you skip this, sheet writes will fail with a 403 error).*

---

## Part 2: Get the Backend Running Locally

### 6) Clone the Repo
In Terminal:
```bash
cd ~
git clone [https://github.com/The-Chamber-of-Us/libelle.git](https://github.com/The-Chamber-of-Us/libelle.git)
cd libelle/backend
```
### 7) Add Credentials
Move (or copy) your two JSON files into the `backend/` folder:
* `org_oauth_client.json`
* `org_credentials.json`

### 8) Python Environment Setup
From inside `libelle/backend`:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 9) Create your local `.env`
Still in `libelle/backend`, create your `.env` file (replace the PASTE values with your actual IDs):

```env
# Drive OAuth (token created by the bootstrap CLI)
GOOGLE_OAUTH_CLIENT=org_oauth_client.json
TOKEN_FILE=token.json
DRIVE_ROOT_FOLDER_ID=PASTE_YOUR_FOLDER_ID

# Sheets (service account)
GOOGLE_SHEET_ID=PASTE_YOUR_SHEET_ID

# Service account key file (local dev)
GOOGLE_CREDENTIALS=org_credentials.json
```

### 10) Run the Backend

```bash
uvicorn main:app --reload --env-file .env
```
* **Runs at:** `http://127.0.0.1:8000`
* **Health check:** `http://127.0.0.1:8000/health` *(Note: The endpoint is `/health`, not `/api/health`)*.

---

## Part 3: Authorize Drive Access & Token Expiry

### 11) Generate `token.json`
To authorize the backend to upload to Drive, you must generate a token:

Run from `backend/` in your activated Python environment:

```bash
python bootstrap_google_oauth.py
```

Open the printed Google consent URL in a browser on the same machine and complete
consent within five minutes. The CLI temporarily listens only on `127.0.0.1:8765`,
validates single-use OAuth state before exchanging the code, and atomically writes
owner-only credentials to `TOKEN_FILE`. Failed or expired attempts preserve the
existing file; restart the CLI to retry. The listener closes when the command ends.
The application server does not need to be running.

Use `--port` only with a matching Google OAuth client redirect URI. The CLI reads
`GOOGLE_OAUTH_CLIENT` and `TOKEN_FILE` from the same configuration as the backend.
Run it only from a trusted operator account. For a headless deployment, bootstrap
on a trusted workstation using the intended environment's Google client and account,
then securely provision the token to that environment's `TOKEN_FILE` with owner-only
permissions and ownership matching the backend/worker service account. Keep tokens
out of Git and logs. Do not proxy the loopback listener through nginx or a tunnel.
Stop backend/worker processes during token replacement to avoid concurrent refresh
writes, then restart them. Bootstrap credentials are not required on the production
host for normal Drive access; it only needs the provisioned token.

`/authorize` and `/oauth2callback` are absent from the application in every mode.
Remove old public callback URIs from the Google client configuration. This workflow
grants backend Drive access only; Sheets still uses `GOOGLE_CREDENTIALS`.

### 12) Token Expiry Warning (Testing Mode)
If your Google OAuth consent screen in GCP is set to "Testing", your local `token.json` may stop working after about 7 days.

* **What this looks like:** Drive operations suddenly fail with `invalid_grant` or 401 errors.
* **Quick local fix:** Rerun `python bootstrap_google_oauth.py` and complete consent. Keep the existing token until replacement succeeds.

---

## Part 4: Test End-to-End

**Prerequisites Check:**
* [ ] `token.json` created.
* [ ] `DRIVE_ROOT_FOLDER_ID` set in `.env`.
* [ ] `GOOGLE_SHEET_ID` set in `.env` and shared with the Service Account email.

**Test Steps:**
1. Open **Swagger UI**: `http://127.0.0.1:8000/docs`
2. Expand `POST /api/upload` → click **Try it out**.
3. Fill in the fields with dummy data. Attach a small PDF test file. Ensure `consent` is `true`.
4. Click **Execute**.

**Expected Result:**
* The PDF uploads into your Drive folder.
* A new row is appended in your test sheet.
* A success `200 OK` JSON response is returned from the API.
