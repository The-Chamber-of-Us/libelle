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
* **Google Drive:** Uses OAuth user consent (initiated via `GET /authorize` and completed via `GET /oauth2callback`) to create `token.json`.
* **Google Sheets:** Uses a service account credential file. This does *not* use `/authorize`.

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
3. **CRITICAL STEP:** Add Authorized Redirect URI: `http://127.0.0.1:8000/oauth2callback`
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
# Drive OAuth (token created after /authorize)
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

1. Open `http://127.0.0.1:8000/authorize` in your browser.
2. The endpoint will return a JSON response containing an `auth_url`. *(It does not automatically redirect).*
3. Copy the returned `auth_url` and paste it into your browser.
4. Complete the Google consent flow.
5. On success, the backend will save `token.json` to the path configured by `TOKEN_FILE`.

> **Important Clarification:** `/authorize` connects your backend to Google Drive via OAuth user auth. It does **not** grant Sheets access. Sheets writes work entirely through the service account credential configured via `GOOGLE_CREDENTIALS`.

### 12) Token Expiry Warning (Testing Mode)
If your Google OAuth consent screen in GCP is set to "Testing", your local `token.json` may stop working after about 7 days.

* **What this looks like:** Drive operations suddenly fail with `invalid_grant` or 401 errors.
* **Quick local fix:** Delete `token.json`, visit `GET /authorize` again, and complete the consent flow to regenerate it.

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
