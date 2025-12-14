# Local Dev Google Setup: Drive OAuth + Sheets Service Account

This guide explains how to run Libelle’s backend locally using your own Google account and a test sheet.

### 🔑 Overview: Two Auth Models
Libelle currently uses two distinct Google authentication models:

1.  **Google Drive (Uploads):** Uses **OAuth** (Desktop App flow) and stores a local `token.json`.
2.  **Google Sheets (Writes):** Uses a **Service Account** and requires sharing the test sheet with the service account email.

> **⚠️ Security Warning**
> **Nothing in this setup should be committed to the repository.**
> All JSON keys, tokens, and `.env` files must remain local.

---

## Prerequisites

* **Python 3.11+**
* **Backend dependencies installed** (`pip install -r requirements.txt`)
* **A personal or test Google account**
* [Access to Google Cloud Console](https://console.cloud.google.com/apis/library/cloudaicompanion.googleapis.com)
---

## Step 1: Create a Google Cloud Project

1.  Navigate to the **Google Cloud Console**.
2.  Create a new project (e.g., `libelle-local-dev`).
3.  **Enable the following APIs** via "APIs & Services" > "Library":
    * Google Drive API
    * Google Sheets API

---

## Step 2: Drive OAuth (Desktop App)

1.  In Google Cloud Console, go to **APIs & Services** → **Credentials**.
2.  Click **Create Credentials** → **OAuth client ID**.
3.  **Application type:** Select `Desktop app`.
4.  Download the resulting JSON file.
5.  Save it locally in the `backend/` directory as:
    `org_oauth_client.json`

> **Note:** This file is used to generate your user token. It must be gitignored.

---

## Step 3: Create a Drive Folder for Uploads

1.  In your personal **Google Drive**, create a folder for uploads (e.g., "Libelle Dev Uploads").
2.  Open the folder and copy the **Folder ID** from the URL bar.

Example URL:  
`https://drive.google.com/drive/folders/DRIVE_ROOT_FOLDER_ID_HERE`

## Step 4: Sheets Service Account
1) In Google Cloud Console, go to **IAM & Admin → Service Accounts**  
2) Create a service account, for example `libelle-sheets-writer`  
3) Create a key for it:
- Key type: **JSON**  
- Download the JSON key file

You now have a service account email that looks like:  
`something@your-project.iam.gserviceaccount.com`

## Step 5: Create a test Google Sheet

### ✅ Use the Libelle Sheet Template (recommended)
To avoid header / column mismatch issues, copy the official Libelle template first:

Template folder (Sheet + README):  
https://drive.google.com/drive/folders/1YSqZOb0_djpbXIrJ23oIOlpDT4sucmD4?usp=sharing

After you copy it, use the **new** sheet’s ID for `GOOGLE_SHEET_ID`.
1) Create a Google Sheet in your Drive, for example “Libelle Dev Applicants”  
2) Add a sheet tab named `applicantsInfo` (or choose your own and set `SHEET_NAME`)  
3) Share the sheet with the service account email as **Editor**  
4) Copy the sheet ID from the URL

Example URL:  
`https://docs.google.com/spreadsheets/d/GOOGLE_SHEET_ID_HERE/edit`

## Step 6: Create your local backend `.env`
In `backend/`, create a `.env` file (this is gitignored).

### Required env vars

#### Drive OAuth (used by /authorize to generate token.json)
- `GOOGLE_OAUTH_CLIENT=org_oauth_client.json`
- `TOKEN_FILE=token.json`
- `DRIVE_ROOT_FOLDER_ID=your_drive_folder_id_here`

#### Sheets Service Account (required for writing rows to Sheets)
- `GOOGLE_SHEET_ID=your_sheet_id_here`
- `SHEET_NAME=applicantsInfo`

### Sheets credentials, choose one method

**Method A (recommended for local dev): file-based service account JSON**
- `GOOGLE_CREDENTIALS=org_credentials.json`

**Method B: environment variable JSON**
- `GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}`

**Notes**
- If you use Method A, rename your downloaded service account key file to `org_credentials.json` and store it in `backend/` locally.
- Do not commit `org_credentials.json`.

### Example `.env`

```env
GOOGLE_OAUTH_CLIENT=org_oauth_client.json
TOKEN_FILE=token.json
DRIVE_ROOT_FOLDER_ID=PASTE_FOLDER_ID

GOOGLE_SHEET_ID=PASTE_SHEET_ID
SHEET_NAME=applicantsInfo
GOOGLE_CREDENTIALS=org_credentials.json
```

## Step 7: Run the backend

From backend/:
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend should be live at:
http://127.0.0.1:8000

## Step 8: Authorize Drive access (generates token.json)

Open:
http://127.0.0.1:8000/authorize

Complete the Google consent flow.
If successful, the backend will save:
token.json

Important clarification
	•	/authorize connects your local server to Google Drive (OAuth).
	•	Sheets access is not granted by /authorize. Sheets writes work via the Service Account configured in your .env.

## Step 9: Test end-to-end

Once you have:
	•	token.json created
	•	DRIVE_ROOT_FOLDER_ID set
	•	GOOGLE_SHEET_ID set and shared with the service account

Then POST a PDF to:
POST http://127.0.0.1:8000/api/upload

# You should see:
	•	file uploaded into your Drive folder
	•	a new row appended in your test sheet
	•	a success JSON response from the API
