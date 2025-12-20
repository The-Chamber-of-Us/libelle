# Libelle Backend: Local Setup Guide

## Overview

Libelle is the volunteer-matching engine for The Chamber of Us. This repository contains the FastAPI backend responsible for accepting volunteer applications and running the resume parser.

This local setup guide helps you run the backend on your own machine and test the end-to-end intake flow. Since Libelle is an early-stage MVP, we use Google Drive and Google Sheets as our primary infrastructure. That gives us fast iteration, clear auditability, and a “low-code database” that non-technical teammates can view and work with.

## The Architecture

When you trigger the intake flow locally (using Swagger), the backend coordinates three actions:

### 1) Application Intake (Form + PDF)
Accepts the volunteer’s form fields (name, email, location, interests, etc.) and a PDF resume upload (use your own test PDF).

### 2) Storage + Logging (Drive + Sheets)
Uploads the PDF resume to a Google Drive folder you control, then creates a new row in a Google Sheet (a lightweight MVP database) that records the submitted form fields and links them to the uploaded Drive file.

### 3) Parsing
Runs a background task to extract key resume signals (skills, experience, etc.) and writes those parsed fields back into the same Sheet row.


## Part 1 - Setting Up Your Google Infrastructure

Before touching the code, you’ll set up your **Database** (a Google Sheet) and your **Storage** (Google Drive). This gives the backend a place to write **one row per application** and a folder to upload **PDF resumes** into.

We’ll do everything inside **your own Google account Drive** for now (easy + safe).

---

#### Note: You'll use the Template Sheet below:

This folder contains the official template sheet with the correct schema for parsed results you should copy into your own Drive:

**Libelle Template Folder (Drive):**  
https://drive.google.com/drive/folders/1YSqZOb0_djpbXIrJ23oIOlpDT4sucmD4?dmr=1&ec=wgc-drive-globalnav-goto

**Template Sheet (inside the folder):**  
https://docs.google.com/spreadsheets/d/1gJXay7VH0-VDkXRy_qK0e3jHHjdJgkrpuVr-xBV-tMw/edit?usp=drive_link

---

### 1) Create Your “Storage” Folder (Google Drive)

The backend needs a destination folder to save uploaded PDF resumes.

1. Open Google Drive.
2. Create a new folder named something like: `Libelle-Dev-Uploads`
3. Open the folder and copy the **Folder ID** from the URL.

Here’s a *complete* example URL (including extra query params), like the one you’ll see when you copy/paste from the browser:

Example URL:  
`https://drive.google.com/drive/folders/1SAlMmdunKexPvD-HTlfCR3aZvOyBzcuY?dmr=1&ec=wgc-drive-globalnav-goto`

In that full URL, the **Folder ID** is the part after `/folders/` and before the `?`:  
`1SAlMmdunKexPvD-HTlfCR3aZvOyBzcuY`

Hold on to your **Folder ID** — you’ll paste it into your `.env` file later as `DRIVE_ROOT_FOLDER_ID`.

---

### 2) Create Your “Database” (Google Sheet)

Remember, to avoid header/column mismatch issues, start from our template.

1. Open the template folder:  
   https://drive.google.com/drive/folders/1YSqZOb0_djpbXIrJ23oIOlpDT4sucmD4?dmr=1&ec=wgc-drive-globalnav-goto
2. Right-click the template Sheet → **Make a copy** (into your own Drive).
3. Open your copied sheet and copy the **Sheet ID** from the URL.

Complete example URL (including query params), like what you’ll see when sharing/copying:

Example URL:  
`https://docs.google.com/spreadsheets/d/1gJXay7VH0-VDkXRy_qK0e3jHHjdJgkrpuVr-xBV-tMw/edit?usp=drive_link`

In that full URL, the **Sheet ID** is the part after `/d/` and before `/edit`:  
`1gJXay7VH0-VDkXRy_qK0e3jHHjdJgkrpuVr-xBV-tMw`

Hold on to your **Sheet ID** — you’ll paste it into your `.env` file later as `GOOGLE_SHEET_ID`.

4. Confirm the tab name at the bottom is exactly: `applicantsInfo`  
   (Case-sensitive — this must match the backend env var `SHEET_NAME`.)

---
### 3) Google Cloud project + credentials
1. Open Google Cloud Console: https://console.cloud.google.com/
2. Create a project (example: `libelle-local-dev`)
3. Enable APIs:
   - Google Drive API
   - Google Sheets API
  
---

### 4A) Create OAuth Client ID (Drive)
1. APIs & Services → Credentials → **Create Credentials** → OAuth client ID
2. Application type: **web app**
3. Download the JSON
4. Rename it to: `org_oauth_client.json`
5. Add a Local Redirect URI: http://127.0.0.1:8000/oauth2callback while in the Client screen.

### 4B) Create Service Account + key (Sheets)
1. IAM & Admin → Service Accounts → **Create Service Account**
2. Create a JSON key for it (Keys → Add Key → Create new key → JSON)
3. Download the JSON
4. Rename it to: `org_credentials.json`
5. Copy the service account email (ends in `...gserviceaccount.com`)

---

### 5) Share your sheet with the service account in your Google Drive (required)
1. Open your copied Google Sheet template
2. Click Share
3. Add the service account email as **Editor**

If you skip this, sheet writes will fail with 403.

---

### ✅ Output you should have so far:
- Drive folder ID (`DRIVE_ROOT_FOLDER_ID`)
- Sheet ID (`GOOGLE_SHEET_ID`)
- `org_oauth_client.json` (OAuth client for Drive)
- `org_credentials.json` (service account key for Sheets)
- Your copied sheet template shared with the service account email as Editor

---

## Part 2 — Get the Backend Running Locally

### 6) Clone the repo (one-time)
In Terminal:

```bash
cd ~
git clone https://github.com/The-Chamber-of-Us/libelle.git
cd libelle/backend
```

Quick sanity check:
```bash

ls -la
# you should see: main.py, requirements.txt, sheets_sync.py, drive_sync.py, etc.
```
---

### 7) Put your two JSON files into `libelle/backend/`

Move (or copy) these into the `backend/` folder:

- `org_oauth_client.json` (OAuth client for Drive)
- `org_credentials.json` (service account key for Sheets)

Verify:

```bash
ls -la org_oauth_client.json org_credentials.json
```

---

### 8) Create a Python venv + install dependencies

From inside libelle/backend:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python --version
pip install --upgrade pip
pip install -r requirements.txt
```
---

### 9) Create your local .env

Still in libelle/backend:
```bash


cat > .env <<'EOF'
# Drive OAuth (token created after /authorize)
GOOGLE_OAUTH_CLIENT=org_oauth_client.json
TOKEN_FILE=token.json
DRIVE_ROOT_FOLDER_ID=PASTE_YOUR_FOLDER_ID

# Sheets (service account)
GOOGLE_SHEET_ID=PASTE_YOUR_SHEET_ID
SHEET_NAME=applicantsInfo

# Service account key file (local dev)
GOOGLE_CREDENTIALS=org_credentials.json
EOF
```

Verify:
```bash

sed -n '1,120p' .env
```

### 10) Run the backend
```bash

uvicorn main:app --reload --env-file .env
```



## Step 11: Authorize Drive access (generates token.json)

Open:
http://127.0.0.1:8000/authorize

Complete the Google consent flow.
If successful, the backend will save:
token.json

Important clarification

	•	/authorize connects your local server to Google Drive (OAuth).
	•	Sheets access is not granted by /authorize. Sheets writes work via the Service Account configured in your .env.

## Step 12: Test End-to-End

**Prerequisites:**
Ensure you have the following ready before testing:
* [ ] `token.json` created (via `/authorize`).
* [ ] `DRIVE_ROOT_FOLDER_ID` set in `.env`.
* [ ] `GOOGLE_SHEET_ID` set in `.env` and shared with the Service Account.

**Easiest way to test:**

1.  Open **Swagger UI**: `http://127.0.0.1:8000/docs`
2.  Expand `POST /api/upload` → click **Try it out**.
3.  Fill in the fields with dummy data:
    * **file:** A PDF resume (<= 5MB)
    * **full_name:** Test Volunteer
    * **email:** test@example.com
    * **location:** Localhost
    * **interests:** Coding, Testing
    * **availability:** 5-10 hours/week
    * **experience_level:** Junior
    * **consent:** `true`
4.  Click **Execute**.

You should see:
- The PDF uploaded into your Drive folder
- A new row appended in your test sheet
- A success JSON response from the API


